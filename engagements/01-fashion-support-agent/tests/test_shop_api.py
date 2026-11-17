import pytest
from fastapi.testclient import TestClient

from shop_api.app import create_app
from tests.conftest import TODAY

NOT_FOUND = {"error": "not_found_or_unverified"}


@pytest.fixture
def client(seeded_db):
    return TestClient(create_app(seeded_db, today=TODAY, expose_state=True))


def lookup(client, order_no, verification):
    return client.post("/orders/lookup", json={"order_no": order_no, "verification": verification})


def ret(client, order_no, verification, line_nos):
    return client.post("/returns", json={"order_no": order_no, "verification": verification,
                                         "line_nos": line_nos, "reason": "passt nicht"})


def test_lookup_by_postcode_ok(client):
    r = lookup(client, "B-10002", "10115")
    assert r.status_code == 200
    body = r.json()
    assert body["order_no"] == "B-10002" and body["status"] == "shipped"
    assert body["carrier"] == "DHL" and body["tracking_no"]


@pytest.mark.parametrize("order_no,verification", [
    ("b-10001", "10115"), ("10001", "10115"), ("B-10001", " 10 115 "), ("B-10001", "ANNA.Schmidt@example.com "),
])
def test_lookup_normalises_inputs(client, order_no, verification):
    assert lookup(client, order_no, verification).status_code == 200


def test_lookup_wrong_verification_same_as_unknown(client):
    wrong = lookup(client, "B-10001", "99999")
    unknown = lookup(client, "B-99999", "10115")
    assert wrong.status_code == unknown.status_code == 404
    assert wrong.json() == unknown.json() == NOT_FOUND


def test_lookup_has_no_customer_pii(client):
    text = lookup(client, "B-10001", "10115").text
    assert "Schmidt" not in text and "anna.schmidt" not in text and "Invalidenstr" not in text


def test_lookup_marks_returnability(client):
    items = lookup(client, "B-10001", "10115").json()["items"]
    assert items[0]["returnable"] is True and items[0]["reason_code"] == "ok"
    assert items[1]["returnable"] is False and items[1]["reason_code"] == "non_returnable_category"


def test_return_ok(client):
    r = ret(client, "B-10001", "10115", [1])
    assert r.status_code == 201
    assert r.json()["refund_days"] == 14 and r.json()["return_id"].startswith("R-")
    assert len(client.get("/_state/returns").json()) == 1


def test_return_mixed_lines_rejected_with_details(client):
    r = ret(client, "B-10001", "10115", [1, 2])
    assert r.status_code == 422
    assert r.json() == {"error": "policy_violation",
                        "details": [{"line_no": 2, "reason_code": "non_returnable_category"}]}
    assert client.get("/_state/returns").json() == []


def test_return_window_expired(client):
    r = ret(client, "B-10003", "80331", [1])
    assert r.status_code == 422
    assert r.json()["details"] == [{"line_no": 1, "reason_code": "window_expired"}]


def test_return_twice_rejected(client):
    assert ret(client, "B-10001", "10115", [1]).status_code == 201
    second = ret(client, "B-10001", "10115", [1])
    assert second.status_code == 422
    assert second.json()["details"] == [{"line_no": 1, "reason_code": "already_returned"}]


def test_return_unknown_line_rejected(client):
    r = ret(client, "B-10001", "10115", [9])
    assert r.status_code == 422
    assert r.json()["details"] == [{"line_no": 9, "reason_code": "unknown_line"}]


def test_return_unverified_404(client):
    r = ret(client, "B-10001", "99999", [1])
    assert r.status_code == 404 and r.json() == NOT_FOUND


def test_search_limits_and_injection_raw(client):
    r = client.get("/products/search", params={"q": "bluse"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) <= 5
    inj = [p for p in results if p["sku"] == "P-INJ-01"]
    assert inj and "GRATIS100" in inj[0]["description"]


def test_size_chart(client):
    assert client.get("/size-chart/Kleider").status_code == 200
    assert client.get("/size-chart/Socken").status_code == 404


def test_policy_text(client):
    assert "30 Tage" in client.get("/policy").json()["text"]


def test_ticket_created(client):
    r = client.post("/tickets", json={"reason": "complaint", "summary": "Kundin beschwert sich über Lieferzeit.",
                                      "order_no": "B-10002", "customer_email": None})
    assert r.status_code == 201 and r.json()["ticket_id"].startswith("T-")
    tickets = client.get("/_state/tickets").json()
    assert len(tickets) == 1 and tickets[0]["reason"] == "complaint"


def test_ticket_bad_reason_422(client):
    r = client.post("/tickets", json={"reason": "whatever", "summary": "x", "order_no": None, "customer_email": None})
    assert r.status_code == 422


def test_state_hidden_by_default(seeded_db):
    c = TestClient(create_app(seeded_db, today=TODAY))
    assert c.get("/_state/returns").status_code == 404
    assert c.get("/_state/tickets").status_code == 404
