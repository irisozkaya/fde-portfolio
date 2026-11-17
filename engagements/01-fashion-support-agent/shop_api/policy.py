"""Return policy of the fictional shop. The API enforces it; the agent only explains it."""
from dataclasses import dataclass
from datetime import date

RETURN_WINDOW_DAYS = 30
REFUND_DAYS = 14
NON_RETURNABLE_CATEGORIES = frozenset({"Unterwäsche", "Bademode"})

POLICY_TEXT_DE = """\
Rückgabe & Erstattung
- Sie können Artikel innerhalb von 30 Tagen ab Zustellung zurückgeben.
- Ausgeschlossen von der Rückgabe sind: Unterwäsche, Bademode, reduzierte Artikel aus dem Final Sale und personalisierte Artikel.
- Die Erstattung erfolgt auf das ursprüngliche Zahlungsmittel innerhalb von 14 Tagen nach Eingang der Rücksendung.
- Eine Rückgabe wird über den Kundenservice gestartet; Sie erhalten danach ein Rücksendeetikett per E-Mail.

Versand
- Bestellungen werden in der Regel innerhalb von 1–2 Werktagen versendet.
- Die Zustellung innerhalb Deutschlands dauert meist 2–4 Werktage.
- Sobald Ihre Bestellung versendet ist, erhalten Sie eine Sendungsnummer.
"""


@dataclass(frozen=True)
class ReturnDecision:
    allowed: bool
    reason_code: str


def check_return(*, status: str, delivered_at: date | None, category: str, final_sale: bool,
                 personalised: bool, already_returned: bool, today: date) -> ReturnDecision:
    if already_returned:
        return ReturnDecision(False, "already_returned")
    if status != "delivered" or delivered_at is None:
        return ReturnDecision(False, "not_delivered")
    if (today - delivered_at).days > RETURN_WINDOW_DAYS:
        return ReturnDecision(False, "window_expired")
    if category in NON_RETURNABLE_CATEGORIES:
        return ReturnDecision(False, "non_returnable_category")
    if final_sale:
        return ReturnDecision(False, "final_sale")
    if personalised:
        return ReturnDecision(False, "personalised")
    return ReturnDecision(True, "ok")
