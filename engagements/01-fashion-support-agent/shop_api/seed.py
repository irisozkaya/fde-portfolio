"""Deterministic synthetic data: hand-written fixtures first, then seeded random filler."""
import json
import random
import sqlite3
import unicodedata
from datetime import date, timedelta

from faker import Faker

from shop_api.fixtures import (CATEGORIES, FIXTURE_CUSTOMERS, FIXTURE_ORDERS, FIXTURE_PRODUCTS,
                               SIZE_CHARTS)

_TYPES = {
    "Kleider": ["Midikleid", "Maxikleid", "Wickelkleid", "Strickkleid", "Blusenkleid"],
    "Hosen": ["Jeans", "Stoffhose", "Culotte", "Cargohose", "Leinenhose"],
    "Oberteile": ["T-Shirt", "Bluse", "Hemd", "Cardigan", "Sweatshirt"],
    "Jacken": ["Blazer", "Trenchcoat", "Lederjacke", "Parka", "Jeansjacke"],
    "Unterwäsche": ["Slip", "Bralette", "Body", "Unterhemd"],
    "Bademode": ["Badeanzug", "Bikini", "Badeshorts"],
    "Schuhe": ["Loafer", "Stiefelette", "Sandale", "Sneaker", "Pumps"],
}
_ADJ = ["Klassischer", "Moderner", "Leichter", "Eleganter", "Lässiger", "Weicher"]
_MATERIALS = ["Baumwolle", "Viskose", "Wolle", "Leinen", "Polyester", "Leder", "Seide"]
_PAYMENTS = ["PayPal", "Kreditkarte", "Rechnung", "Klarna"]
_CARRIERS = ["DHL", "Hermes", "DPD"]


def _ascii(s: str) -> str:
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum() or ch == ".")


def _day(today: date, offset: int | None) -> str | None:
    return None if offset is None else (today + timedelta(days=offset)).isoformat()


def _insert_product(conn: sqlite3.Connection, p: dict) -> None:
    conn.execute(
        "INSERT INTO products (sku, name, category, price_eur, sizes, material, description, final_sale, personalised)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (p["sku"], p["name"], p["category"], p["price_eur"], json.dumps(p["sizes"], ensure_ascii=False),
         p["material"], p["description"], int(p.get("final_sale", False)), int(p.get("personalised", False))))


def _insert_order(conn: sqlite3.Connection, o: dict, today: date, prices: dict[str, float]) -> None:
    conn.execute(
        "INSERT INTO orders (order_no, customer_id, status, placed_at, shipped_at, delivered_at, carrier,"
        " tracking_no, payment_method) VALUES (?,?,?,?,?,?,?,?,?)",
        (o["order_no"], o["customer_id"], o["status"], _day(today, o["placed"]), _day(today, o["shipped"]),
         _day(today, o["delivered"]), o["carrier"], o["tracking_no"], o["payment_method"]))
    for line_no, (sku, size, qty) in enumerate(o["items"], start=1):
        conn.execute("INSERT INTO order_items (order_no, line_no, sku, size, qty, price_eur) VALUES (?,?,?,?,?,?)",
                     (o["order_no"], line_no, sku, size, qty, prices[sku]))


def seed(conn: sqlite3.Connection, *, today: date, rng_seed: int = 42) -> None:
    rng = random.Random(rng_seed)
    fake = Faker("de_DE")
    fake.seed_instance(rng_seed)

    for c in FIXTURE_CUSTOMERS:
        conn.execute("INSERT INTO customers (id, first_name, last_name, email, postcode, city, street)"
                     " VALUES (:id,:first_name,:last_name,:email,:postcode,:city,:street)", c)
    for p in FIXTURE_PRODUCTS:
        _insert_product(conn, p)

    # Filler customers (ids 4..33)
    for i in range(30):
        first, last = fake.first_name(), fake.last_name()
        conn.execute(
            "INSERT INTO customers (id, first_name, last_name, email, postcode, city, street) VALUES (?,?,?,?,?,?,?)",
            (4 + i, first, last, f"{_ascii(first)}.{_ascii(last)}{i}@example.com", fake.postcode(), fake.city(),
             fake.street_address()))

    # Filler products P-2001..P-2060
    filler_products = []
    for i in range(60):
        cat = CATEGORIES[i % len(CATEGORIES)]
        p = {"sku": f"P-{2001 + i}", "name": f"{rng.choice(_ADJ)} {rng.choice(_TYPES[cat])}", "category": cat,
             "price_eur": round(rng.uniform(19, 249), 2),
             "sizes": [row["size"] for row in SIZE_CHARTS[cat]], "material": rng.choice(_MATERIALS),
             "description": f"{rng.choice(_ADJ)} Schnitt aus {rng.choice(_MATERIALS)}.",
             "final_sale": rng.random() < 0.1}
        _insert_product(conn, p)
        filler_products.append(p)

    prices = {p["sku"]: p["price_eur"] for p in FIXTURE_PRODUCTS + filler_products}
    for o in FIXTURE_ORDERS:
        _insert_order(conn, o, today, prices)

    # Filler orders B-20001..B-20080 for filler customers only
    for i in range(80):
        status = rng.choice(["paid", "shipped", "delivered", "delivered", "delivered", "cancelled"])
        placed = -rng.randint(1, 90)
        shipped = placed + 1 if status in ("shipped", "delivered") else None
        delivered = min(placed + rng.randint(3, 6), 0) if status == "delivered" else None
        carrier = rng.choice(_CARRIERS) if shipped is not None else None
        items = []
        for _ in range(rng.randint(1, 3)):
            p = rng.choice(filler_products)
            items.append((p["sku"], rng.choice(p["sizes"]), 1))
        _insert_order(conn, {
            "order_no": f"B-{20001 + i}", "customer_id": 4 + rng.randrange(30), "status": status,
            "placed": placed, "shipped": shipped, "delivered": delivered, "carrier": carrier,
            "tracking_no": f"{rng.randrange(10**11, 10**12)}" if carrier else None,
            "payment_method": rng.choice(_PAYMENTS), "items": items}, today, prices)
