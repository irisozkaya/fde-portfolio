"""Deterministic grading: tools called / not called, final shop state, reply content."""
from dataclasses import dataclass, field

from agent.loop import TurnRecord
from evals.schema import Scenario


@dataclass
class GradeResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def grade(scenario: Scenario, turns: list[TurnRecord], state: dict) -> GradeResult:
    e = scenario.expect
    failures: list[str] = []
    called = {c.name for t in turns for c in t.tool_calls}
    replies = "\n".join(t.reply_text for t in turns).casefold()

    for name in e.tools_called:
        if name not in called:
            failures.append(f"expected tool not called: {name}")
    for name in e.tools_not_called:
        if name in called:
            failures.append(f"forbidden tool called: {name}")

    if e.returns_created is not None:
        expected = sorted((r.order_no, tuple(sorted(r.line_nos))) for r in e.returns_created)
        actual = sorted((r["order_no"], tuple(sorted(r["line_nos"]))) for r in state["returns"])
        if expected != actual:
            failures.append(f"returns: expected {expected}, got {actual}")
    if e.tickets_created is not None and len(state["tickets"]) != e.tickets_created:
        failures.append(f"tickets: expected {e.tickets_created}, got {len(state['tickets'])}")
    if e.ticket_reason is not None and e.ticket_reason not in {t["reason"] for t in state["tickets"]}:
        failures.append(f"no ticket with reason {e.ticket_reason}")

    for s in e.reply_must_not_contain:
        if s.casefold() in replies:
            failures.append(f"reply contains forbidden text: {s}")
    if e.reply_must_contain_any and not any(s.casefold() in replies for s in e.reply_must_contain_any):
        failures.append(f"reply contains none of: {e.reply_must_contain_any}")

    return GradeResult(passed=not failures, failures=failures)
