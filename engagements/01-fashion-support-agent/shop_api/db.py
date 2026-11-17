"""SQLite storage for the mock shop."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    postcode TEXT NOT NULL,
    city TEXT NOT NULL,
    street TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price_eur REAL NOT NULL,
    sizes TEXT NOT NULL,            -- JSON list
    material TEXT NOT NULL,
    description TEXT NOT NULL,
    final_sale INTEGER NOT NULL DEFAULT 0,
    personalised INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
    order_no TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL,           -- paid | shipped | delivered | cancelled
    placed_at TEXT NOT NULL,
    shipped_at TEXT,
    delivered_at TEXT,
    carrier TEXT,
    tracking_no TEXT,
    payment_method TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    order_no TEXT NOT NULL REFERENCES orders(order_no),
    line_no INTEGER NOT NULL,
    sku TEXT NOT NULL REFERENCES products(sku),
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price_eur REAL NOT NULL,
    PRIMARY KEY (order_no, line_no)
);
CREATE TABLE IF NOT EXISTS returns (
    return_id TEXT PRIMARY KEY,
    order_no TEXT NOT NULL,
    line_nos TEXT NOT NULL,         -- JSON list
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    refund_eur REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    summary TEXT NOT NULL,
    order_no TEXT,
    customer_email TEXT
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
