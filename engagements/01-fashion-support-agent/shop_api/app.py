"""Fadenwerk's shop API (mock). Verification and the return policy are enforced here, not in the agent."""
import json
import re
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shop_api.db import connect
from shop_api.fixtures import SIZE_CHARTS
from shop_api.policy import POLICY_TEXT_DE, REFUND_DAYS, check_return

NOT_FOUND = {"error": "not_found_or_unverified"}
TicketReason = Literal["complaint", "legal", "payment_dispute", "out_of_scope", "customer_request", "other"]


class LookupRequest(BaseModel):
    order_no: str
    verification: str


class ReturnRequest(BaseModel):
    order_no: str
    verification: str
    line_nos: list[int] = Field(min_length=1)
    reason: str


class TicketRequest(BaseModel):
    reason: TicketReason
    summary: str = Field(min_length=1)
    order_no: str | None = None
    customer_email: str | None = None


def normalise_order_no(raw: str) -> str:
    s = raw.strip().upper()
    m = re.fullmatch(r"(?:B-?)?(\d+)", s)
    return f"B-{m.group(1)}" if m else s


def normalise_verification(raw: str) -> str:
    return "".join(raw.split()).lower()


def create_app(db_path: str, *, today: date | None = None, expose_state: bool = False) -> FastAPI:
    app = FastAPI(title="Fadenwerk Shop API (mock)")

    def get_conn():
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _today() -> date:
        return today or date.today()

    def verified_order(conn, order_no: str, verification: str):
        row = conn.execute(
            "SELECT o.*, c.postcode, c.email FROM orders o JOIN customers c ON c.id = o.customer_id "
            "WHERE o.order_no = ?", (normalise_order_no(order_no),)).fetchone()
        v = normalise_verification(verification)
        if row is None or v not in (row["postcode"], row["email"].lower()):
            return None
        return row

    def returned_lines(conn, order_no: str) -> set[int]:
        lines: set[int] = set()
        for r in conn.execute("SELECT line_nos FROM returns WHERE order_no = ?", (order_no,)):
            lines.update(json.loads(r["line_nos"]))
        return lines

    def order_items(conn, order) -> list[dict]:
        done = returned_lines(conn, order["order_no"])
        delivered = date.fromisoformat(order["delivered_at"]) if order["delivered_at"] else None
        items = []
        for it in conn.execute(
                "SELECT i.*, p.name, p.category, p.final_sale, p.personalised FROM order_items i "
                "JOIN products p ON p.sku = i.sku WHERE i.order_no = ? ORDER BY i.line_no", (order["order_no"],)):
            decision = check_return(status=order["status"], delivered_at=delivered, category=it["category"],
                                    final_sale=bool(it["final_sale"]), personalised=bool(it["personalised"]),
                                    already_returned=it["line_no"] in done, today=_today())
            items.append({"line_no": it["line_no"], "sku": it["sku"], "name": it["name"],
                          "category": it["category"], "size": it["size"], "qty": it["qty"],
                          "price_eur": it["price_eur"], "returnable": decision.allowed,
                          "reason_code": decision.reason_code})
        return items

    @app.post("/orders/lookup")
    def lookup(req: LookupRequest, conn=Depends(get_conn)):
        order = verified_order(conn, req.order_no, req.verification)
        if order is None:
            return JSONResponse(NOT_FOUND, status_code=404)
        return {k: order[k] for k in ("order_no", "status", "placed_at", "shipped_at", "delivered_at",
                                      "carrier", "tracking_no")} | {"items": order_items(conn, order)}

    @app.post("/returns", status_code=201)
    def start_return(req: ReturnRequest, conn=Depends(get_conn)):
        order = verified_order(conn, req.order_no, req.verification)
        if order is None:
            return JSONResponse(NOT_FOUND, status_code=404)
        by_line = {it["line_no"]: it for it in order_items(conn, order)}
        requested = sorted(set(req.line_nos))
        violations = []
        for line_no in requested:
            item = by_line.get(line_no)
            if item is None:
                violations.append({"line_no": line_no, "reason_code": "unknown_line"})
            elif not item["returnable"]:
                violations.append({"line_no": line_no, "reason_code": item["reason_code"]})
        if violations:
            return JSONResponse({"error": "policy_violation", "details": violations}, status_code=422)
        count = conn.execute("SELECT COUNT(*) FROM returns").fetchone()[0]
        return_id = f"R-{count + 1:04d}"
        refund = round(sum(by_line[n]["price_eur"] * by_line[n]["qty"] for n in requested), 2)
        conn.execute("INSERT INTO returns (return_id, order_no, line_nos, reason, created_at, refund_eur)"
                     " VALUES (?,?,?,?,?,?)",
                     (return_id, order["order_no"], json.dumps(requested), req.reason, _today().isoformat(), refund))
        conn.commit()
        return {"return_id": return_id, "refund_eur": refund, "refund_days": REFUND_DAYS}

    @app.get("/products/search")
    def search(q: str = "", category: str | None = None, size: str | None = None, conn=Depends(get_conn)):
        needle = q.casefold().strip()
        hits = []
        for p in conn.execute("SELECT * FROM products"):
            sizes = json.loads(p["sizes"])
            haystack = " ".join([p["name"], p["description"], p["category"], p["material"]]).casefold()
            if needle and needle not in haystack:
                continue
            if category and p["category"].casefold() != category.casefold():
                continue
            if size and size.casefold() not in [s.casefold() for s in sizes]:
                continue
            hits.append(p)
        # Hand-curated catalogue (P-1xxx, P-INJ) before generated filler (P-2xxx); name matches first.
        hits.sort(key=lambda p: (p["sku"].startswith("P-2"), needle not in p["name"].casefold(), p["sku"]))
        return [{"sku": p["sku"], "name": p["name"], "category": p["category"], "price_eur": p["price_eur"],
                 "sizes": json.loads(p["sizes"]), "material": p["material"], "description": p["description"]}
                for p in hits[:5]]

    @app.get("/size-chart/{category}")
    def size_chart(category: str):
        for name, rows in SIZE_CHARTS.items():
            if name.casefold() == category.casefold():
                return {"category": name, "rows": rows}
        return JSONResponse({"error": "unknown_category", "known": list(SIZE_CHARTS)}, status_code=404)

    @app.get("/policy")
    def policy():
        return {"text": POLICY_TEXT_DE}

    @app.post("/tickets", status_code=201)
    def create_ticket(req: TicketRequest, conn=Depends(get_conn)):
        count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        ticket_id = f"T-{count + 1:04d}"
        conn.execute("INSERT INTO tickets (ticket_id, created_at, reason, summary, order_no, customer_email)"
                     " VALUES (?,?,?,?,?,?)",
                     (ticket_id, _today().isoformat(), req.reason, req.summary,
                      normalise_order_no(req.order_no) if req.order_no else None, req.customer_email))
        conn.commit()
        return {"ticket_id": ticket_id}

    if expose_state:
        @app.get("/_state/returns")
        def state_returns(conn=Depends(get_conn)):
            return [dict(r) | {"line_nos": json.loads(r["line_nos"])}
                    for r in conn.execute("SELECT * FROM returns ORDER BY return_id")]

        @app.get("/_state/tickets")
        def state_tickets(conn=Depends(get_conn)):
            return [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY ticket_id")]

    return app
