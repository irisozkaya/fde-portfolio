from datetime import date, timedelta

from shop_api.db import connect, init_schema
from shop_api.fixtures import FIXTURE_CUSTOMERS, INJECTION_SKU
from shop_api.seed import seed

TODAY = date(2026, 11, 17)


def _fresh(path):
    conn = connect(str(path))
    init_schema(conn)
    seed(conn, today=TODAY)
    conn.commit()
    return conn


def test_seed_is_deterministic(tmp_path):
    a = list(_fresh(tmp_path / "a.db").iterdump())
    b = list(_fresh(tmp_path / "b.db").iterdump())
    assert a == b


def test_fixture_orders(tmp_path):
    conn = _fresh(tmp_path / "s.db")
    statuses = {r["order_no"]: r["status"] for r in conn.execute(
        "SELECT order_no, status FROM orders WHERE order_no LIKE 'B-1000%'")}
    assert statuses == {
        "B-10001": "delivered", "B-10002": "shipped", "B-10003": "delivered", "B-10004": "paid",
        "B-10005": "delivered", "B-10006": "cancelled", "B-10007": "delivered",
    }
    delivered = conn.execute("SELECT delivered_at FROM orders WHERE order_no='B-10007'").fetchone()[0]
    assert date.fromisoformat(delivered) == TODAY - timedelta(days=30)
    cat = conn.execute(
        "SELECT p.category FROM order_items i JOIN products p ON p.sku=i.sku "
        "WHERE i.order_no='B-10001' AND i.line_no=2").fetchone()[0]
    assert cat == "Unterwäsche"


def test_injection_product(tmp_path):
    conn = _fresh(tmp_path / "s.db")
    desc = conn.execute("SELECT description FROM products WHERE sku=?", (INJECTION_SKU,)).fetchone()[0]
    assert "GRATIS100" in desc


def test_fixture_emails_use_example_domain():
    assert FIXTURE_CUSTOMERS and all(c["email"].endswith("@example.com") for c in FIXTURE_CUSTOMERS)
