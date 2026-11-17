"""Entry point: `uvicorn shop_api.main:app --port 8001`.

The mock database is rebuilt on every start so the demo always shows the same orders
relative to today. Env: SHOP_DB_PATH (default ./shop.db), SHOP_TODAY (optional ISO date).
"""
import os
from datetime import date
from pathlib import Path

from shop_api.app import create_app
from shop_api.db import connect, init_schema
from shop_api.seed import seed

_db_path = Path(os.environ.get("SHOP_DB_PATH", "./shop.db"))
_today = date.fromisoformat(os.environ["SHOP_TODAY"]) if os.environ.get("SHOP_TODAY") else date.today()

_db_path.unlink(missing_ok=True)
_conn = connect(str(_db_path))
init_schema(_conn)
seed(_conn, today=_today)
_conn.commit()
_conn.close()

app = create_app(str(_db_path), today=_today)
