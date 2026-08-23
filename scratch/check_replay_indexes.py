"""Read-only check: indexes & row counts for replay tables."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend", ".env"))

from app.core.database import init_db_pool, get_db_conn  # noqa: E402

TABLES = [
    "marketdata_xauusd_m15",
    "marketdata_xauusd_h1",
    "marketdata_xauusd_h4",
    "llhhbosdata_xauusd",
    "backtest_results_xauusd",
]

init_db_pool()

with get_db_conn() as conn:
    with conn.cursor() as cur:
        print("=== INDEXES ===")
        cur.execute(
            """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = ANY(%s)
            ORDER BY tablename, indexname
            """,
            (TABLES,),
        )
        for tbl, idx, definition in cur.fetchall():
            print(f"[{tbl}] {idx}: {definition}")

        print("\n=== ROW COUNTS (approx) ===")
        for tbl in TABLES:
            cur.execute(f"SELECT reltuples::bigint FROM pg_class WHERE relname = %s", (tbl,))
            row = cur.fetchone()
            print(f"{tbl}: ~{row[0] if row else '?'} rows")
