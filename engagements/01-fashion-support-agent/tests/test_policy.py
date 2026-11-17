from datetime import date, timedelta

from shop_api.policy import ReturnDecision, check_return

TODAY = date(2026, 11, 17)


def d(days):
    return TODAY - timedelta(days=days)


BASE = dict(status="delivered", category="Kleider", final_sale=False,
            personalised=False, already_returned=False, today=TODAY)


def test_within_window():
    assert check_return(**BASE, delivered_at=d(10)) == ReturnDecision(True, "ok")


def test_day_30_allowed():
    assert check_return(**BASE, delivered_at=d(30)).allowed


def test_day_31_rejected():
    assert check_return(**BASE, delivered_at=d(31)) == ReturnDecision(False, "window_expired")


def test_not_delivered():
    assert check_return(**{**BASE, "status": "shipped"}, delivered_at=None).reason_code == "not_delivered"


def test_underwear():
    assert check_return(**{**BASE, "category": "Unterwäsche"}, delivered_at=d(3)).reason_code == "non_returnable_category"


def test_swimwear():
    assert check_return(**{**BASE, "category": "Bademode"}, delivered_at=d(3)).reason_code == "non_returnable_category"


def test_final_sale():
    assert check_return(**{**BASE, "final_sale": True}, delivered_at=d(3)).reason_code == "final_sale"


def test_personalised():
    assert check_return(**{**BASE, "personalised": True}, delivered_at=d(3)).reason_code == "personalised"


def test_already_returned():
    assert check_return(**{**BASE, "already_returned": True}, delivered_at=d(3)).reason_code == "already_returned"
