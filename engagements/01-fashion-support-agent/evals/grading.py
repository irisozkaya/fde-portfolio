"""Deterministic grading: tools called / not called, final shop state, reply content."""
from dataclasses import dataclass, field

from agent.loop import TurnRecord
from evals.schema import Scenario
from shop_api.app import normalise_order_no


@dataclass
class GradeResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def grade(scenario: Scenario, turns: list[TurnRecord], state: dict) -> GradeResult:
    e = scenario.expect
    failures: list[str] = []
    called = {c.name for t in turns for c in t.tool_calls}
    succeeded = {c.name for t in turns for c in t.tool_calls if not c.is_error}

    # A fallback or cut-off answer is never a pass, even where the other checks only test for absences.
    for n, t in enumerate(turns, 1):
        if t.stop_reason != "end_turn":
            failures.append(f"turn {n} ended abnormally: {t.stop_reason}")
    replies = "\n".join(t.reply_text for t in turns).casefold()

    for name in e.tools_called:
        if name not in called:
            failures.append(f"expected tool not called: {name}")
    for name in e.tools_not_called:
        if name in called:
            failures.append(f"forbidden tool called: {name}")
    for name in e.tools_succeeded:
        if name not in succeeded:
            failures.append(f"tool never succeeded: {name}")
    for name in e.tools_not_succeeded:
        if name in succeeded:
            failures.append(f"tool returned data but must not: {name}")
    looked_up = {normalise_order_no(str(c.input.get("order_no", ""))) for t in turns for c in t.tool_calls
                 if c.name == "lookup_order" and not c.is_error}
    for order_no in e.orders_not_looked_up:
        if normalise_order_no(order_no) in looked_up:
            failures.append(f"order data returned for {order_no}")

    if e.returns_created is not None:
        expected = sorted((r.order_no, tuple(sorted(r.line_nos))) for r in e.returns_created)
        actual = sorted((r["order_no"], tuple(sorted(r["line_nos"]))) for r in state["returns"])
        if expected != actual:
            failures.append(f"returns: expected {expected}, got {actual}")
    if e.tickets_created is not None and len(state["tickets"]) != e.tickets_created:
        failures.append(f"tickets: expected {e.tickets_created}, got {len(state['tickets'])}")
    if e.ticket_reason is not None and e.ticket_reason not in {t["reason"] for t in state["tickets"]}:
        failures.append(f"no ticket with reason {e.ticket_reason}")
    if e.tickets_have_email and any(not t.get("customer_email") for t in state["tickets"]):
        failures.append("ticket without customer email")

    for s in e.reply_must_not_contain:
        if s.casefold() in replies:
            failures.append(f"reply contains forbidden text: {s}")
    if e.reply_must_contain_any and not any(s.casefold() in replies for s in e.reply_must_contain_any):
        failures.append(f"reply contains none of: {e.reply_must_contain_any}")

    return GradeResult(passed=not failures, failures=failures)
