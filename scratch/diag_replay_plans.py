"""Read-only: verify index usage plan for replay candle query."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend", ".env"))

from app.core.database import init_db_pool, get_db_conn  # noqa: E402

init_db_pool()

with get_db_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "EXPLAIN (ANALYZE, BUFFERS) "
            "SELECT time, open, high, low, close, volume, ema200, spread "
            "FROM marketdata_xauusd_m15 WHERE time >= %s AND time < %s ORDER BY time ASC",
            ("2026-05-01", "2026-08-01"),
        )
        print("--- PLAN candles (3 bulan) ---")
        for r in cur.fetchall():
            print(r[0])

        cur.execute(
            "EXPLAIN (ANALYZE, BUFFERS) "
            "SELECT type, direction_action, price, time, timeframe, status, previous_price, previous_time "
            "FROM llhhbosdata_xauusd WHERE time >= %s AND time < %s AND timeframe = %s ORDER BY time ASC",
            ("2020-01-01", "2027-01-01", "M15"),
        )
        print("\n--- PLAN structures (full) ---")
        for r in cur.fetchall():
            print(r[0])
