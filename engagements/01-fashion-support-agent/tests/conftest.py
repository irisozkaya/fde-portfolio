from datetime import date

import pytest

TODAY = date(2026, 11, 17)


@pytest.fixture
def seeded_db(tmp_path):
    from shop_api.db import connect, init_schema
    from shop_api.seed import seed

    path = str(tmp_path / "shop.db")
    conn = connect(path)
    init_schema(conn)
    seed(conn, today=TODAY)
    conn.commit()
    conn.close()
    return path
