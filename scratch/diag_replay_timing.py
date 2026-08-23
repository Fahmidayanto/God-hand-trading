"""Read-only timing diagnosis for /trading/replay queries."""
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
    print(f"{label:55s} {dt:9.1f} ms  rows={len(rows)}")
    return rows


with get_db_conn() as conn:
    with conn.cursor() as cur:
        # Cold vs warm connection note printed by caller order

        # 1) Candles: worst case = full table scan via API default? Use full range
        timed(cur, "candles M15 FULL RANGE",
              "SELECT time, open, high, low, close, volume, ema200, spread "
              "FROM marketdata_xauusd_m15 WHERE time >= %s AND time < %s ORDER BY time ASC",
              ("1900-01-01", "2100-01-01"))

        # 2) Structures full
        timed(cur, "structures FULL RANGE M15",
              "SELECT type, direction_action, price, time, timeframe, status, previous_price, previous_time "
              "FROM llhhbosdata_xauusd WHERE time >= %s AND time < %s AND timeframe = %s ORDER BY time ASC",
              ("1900-01-01", "2100-01-01", "M15"))

        # 3) Trades full
        timed(cur, "trades FULL RANGE",
              "SELECT ticket, type, status, reject_reason, entry_price, exit_price, sl, tp, "
              "net_profit, session, entry_time, exit_time, lot_size, spread_cost, commission, swap "
              "FROM backtest_results_xauusd WHERE entry_time >= %s AND entry_time < %s ORDER BY entry_time ASC",
              ("1900-01-01", "2100-01-01"))

        # 4) Available months (runs EVERY load)
        timed(cur, "available_months (DISTINCT extract, no filter)",
              "SELECT DISTINCT EXTRACT(YEAR FROM time)::int AS y, EXTRACT(MONTH FROM time)::int AS m "
              "FROM marketdata_xauusd_m15 ORDER BY y, m")

        # 4b) again warm
        timed(cur, "available_months (repeat/warm)",
              "SELECT DISTINCT EXTRACT(YEAR FROM time)::int AS y, EXTRACT(MONTH FROM time)::int AS m "
              "FROM marketdata_xauusd_m15 ORDER BY y, m")

        # Plan for months query
        cur.execute("EXPLAIN (ANALYZE, BUFFERS) "
                    "SELECT DISTINCT EXTRACT(YEAR FROM time)::int AS y, EXTRACT(MONTH FROM time)::int AS m "
                    "FROM marketdata_xauusd_m15 ORDER BY y, m")
        print("\n--- EXPLAIN available_months ---")
        for r in cur.fetchall():
            print(r[0])

        # Data distribution
        print("\n--- rows per year-month (m15) ---")
        cur.execute("""
            SELECT date_trunc('month', MIN(time))::date, COUNT(*)
            FROM marketdata_xauusd_m15 GROUP BY 1 ORDER BY 1
        """)
        # cheaper grouped version below
        cur.execute("""
            SELECT EXTRACT(YEAR FROM time)::int y, EXTRACT(MONTH FROM time)::int m, COUNT(*)
            FROM marketdata_xauusd_m15 GROUP BY 1,2 ORDER BY 1,2
        """)
        for y, m, c in cur.fetchall():
            print(f"{y}-{m:02d}: {c}")

        # Table size on disk (transfer proxy)
        cur.execute("""
            SELECT relname, pg_size_pretty(pg_total_relation_size(c.oid))
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND relname IN
            ('marketdata_xauusd_m15','llhhbosdata_xauusd','backtest_results_xauusd')
            ORDER BY pg_total_relation_size(c.oid) DESC
        """)
        print("\n--- table sizes ---")
        for r in cur.fetchall():
            print(f"{r[0]}: {r[1]}")
