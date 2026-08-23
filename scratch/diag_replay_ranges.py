"""Read-only: measure replay candle query times for realistic date ranges."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend", ".env"))

from app.core.database import init_db_pool, get_db_conn  # noqa: E402

init_db_pool()


def timed(cur, label, sql, params=()):
    t0 = time.perf_counter()
    cur.execute(sql, params)
    rows = cur.fetchall()
    dt = (time.perf_counter() - t0) * 1000
    print(f"{label:48s} {dt:9.1f} ms  rows={len(rows)}")


RANGES = [
    ("1 bulan (2026-07)", ("2026-07-01", "2026-08-01")),
    ("3 bulan (2026-05..07)", ("2026-05-01", "2026-08-01")),
    ("1 tahun (2025)", ("2025-01-01", "2026-01-01")),
    ("full 2020-2026", ("2020-01-01", "2027-01-01")),
]

CANDLE_SQL = ("SELECT time, open, high, low, close, volume, ema200, spread "
              "FROM marketdata_xauusd_m15 WHERE time >= %s AND time < %s ORDER BY time ASC")

with get_db_conn() as conn:
    with conn.cursor() as cur:
        for label, (a, b) in RANGES:
            timed(cur, f"M15 candles {label}", CANDLE_SQL, (a, b))
