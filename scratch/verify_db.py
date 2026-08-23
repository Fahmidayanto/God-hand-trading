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

tables = [
    "backtest_results_xauusd","llhhbosdata_xauusd",
    "marketdata_xauusd_m15","marketdata_xauusd_h1",
    "marketdata_xauusd_h4","sessionzone_xauusd","csv_load_log"
]

print("=== Row Count ===")
for t in tables:
    cur.execute("SELECT COUNT(*) FROM " + t)
    print(f"  {t}: {cur.fetchone()[0]} rows")

print()
print("=== Kolom backtest_results_xauusd ===")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'backtest_results_xauusd'
    ORDER BY ordinal_position
""")
for col, dtype in cur.fetchall():
    marker = " <-- BARU" if col in ("entry_structure","close_type") else ""
    print(f"  {col} ({dtype}){marker}")

cur.close()
conn.close()
