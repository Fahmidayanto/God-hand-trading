import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("backend")))
from dotenv import load_dotenv
load_dotenv("backend/.env")
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("PGHOST"), dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"), password=os.getenv("PGPASSWORD"),
    sslmode=os.getenv("PGSSLMODE","require"), connect_timeout=10
)
cur = conn.cursor()

alters = [
    "ALTER TABLE backtest_results_xauusd ALTER COLUMN close_reason TYPE VARCHAR(255)",
    "ALTER TABLE backtest_results_xauusd ALTER COLUMN entry_structure TYPE VARCHAR(255)",
    "ALTER TABLE backtest_results_xauusd ALTER COLUMN close_type TYPE VARCHAR(255)",
    "ALTER TABLE backtest_results_xauusd ALTER COLUMN reject_reason TYPE VARCHAR(255)",
    "ALTER TABLE backtest_results_xauusd ALTER COLUMN body_ratio_mode TYPE VARCHAR(255)",
]

for stmt in alters:
    col = stmt.split("COLUMN")[1].strip().split()[0]
    try:
        cur.execute(stmt)
        conn.commit()
        print(f"  OK {col} -> VARCHAR(255)")
    except Exception as e:
        print(f"  ERR {col}: {e}")
        conn.rollback()

cur.execute("DELETE FROM csv_load_log WHERE status = %s OR filename LIKE %s", ("error", "Backtest_Results%"))
deleted = cur.rowcount
conn.commit()
print(f"  OK Deleted {deleted} rows dari csv_load_log (force retry)")

cur.close()
conn.close()
print("Selesai. Watcher retry dalam 5 detik.")
