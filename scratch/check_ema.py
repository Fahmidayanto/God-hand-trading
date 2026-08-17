import sys
import os

sys.path.insert(0, os.path.abspath("ValueCell_MT5/backend"))
from dotenv import load_dotenv
load_dotenv("ValueCell_MT5/backend/.env")

from app.core.database import init_db_pool, get_db_conn, is_pool_ready

init_db_pool()
if not is_pool_ready():
    print("Database pool not ready")
    sys.exit(1)

with get_db_conn() as conn:
    with conn.cursor() as cur:
        for tbl in ["marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"]:
            cur.execute(f"SELECT COUNT(*), COUNT(ema200), MIN(time), MAX(time) FROM {tbl}")
            total, ema_count, min_t, max_t = cur.fetchone()
            print(f"Table {tbl}: Total={total}, WithEMA200={ema_count}, Range={min_t} to {max_t}")
            cur.execute(f"SELECT time, close, ema200 FROM {tbl} WHERE time >= '2026-01-01' LIMIT 5")
            rows = cur.fetchall()
            print(f"Sample 2026 {tbl}:", rows)
