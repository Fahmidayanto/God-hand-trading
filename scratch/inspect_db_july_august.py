import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path("b:/Project MT5/ValueCell_MT5/backend")
python_dir = Path("b:/Project MT5/ValueCell_MT5/python")
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(python_dir))

from app.core.database import get_db_conn, init_db_pool
from valuecell.knowledge.lance_db import LanceDBManager

init_db_pool()

print("--- NEON DATABASE INSPECTION ---")
tables = [
    ("backtest_results_xauusd", "entry_time"),
    ("llhhbosdata_xauusd", "time"),
    ("marketdata_xauusd_m15", "time"),
    ("marketdata_xauusd_h1", "time"),
    ("marketdata_xauusd_h4", "time"),
    ("sessionzone_xauusd", "start_time"),
]

with get_db_conn() as conn:
    with conn.cursor() as cur:
        for t, col in tables:
            cur.execute(f"""
                SELECT COUNT(*), MIN({col}), MAX({col})
                FROM {t}
                WHERE {col} >= '2026-07-01' AND {col} <= '2026-08-31 23:59:59'
            """)
            row = cur.fetchone()
            print(f"Table {t} (2026-07 to 2026-08): Count={row[0]}, Min={row[1]}, Max={row[2]}")

        cur.execute("SELECT filename, rows_loaded, loaded_at FROM csv_load_log WHERE filename LIKE '%2026-08-19%'")
        rows = cur.fetchall()
        print("\nCSV Load Log (2026-08-19 files):")
        for r in rows:
            print(f"  {r[0]}: rows={r[1]}, loaded_at={r[2]}")

print("\n--- LANCEDB INSPECTION ---")
lancedb_path = python_dir / "valuecell" / "data" / "lancedb"
mgr = LanceDBManager(str(lancedb_path))
for name in mgr._table_names():
    tbl = mgr.db.open_table(name)
    count = tbl.count_rows()
    print(f"LanceDB Collection {name}: Total records = {count}")
    if count > 0:
        df = tbl.to_arrow().to_pandas()
        for dcol in ["timestamp", "time", "date", "entry_time", "start_time"]:
            if dcol in df.columns:
                print(f"  Column {dcol}: min={df[dcol].min()}, max={df[dcol].max()}")
