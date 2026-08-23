import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("ValueCell_MT5/backend")))
from dotenv import load_dotenv
load_dotenv("ValueCell_MT5/backend/.env")
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("PGHOST"), dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"), password=os.getenv("PGPASSWORD"),
    sslmode=os.getenv("PGSSLMODE", "require"), connect_timeout=15
)
cur = conn.cursor()

checks = [
    ("backtest_results_xauusd", "entry_time, ticket, type"),
    ("llhhbosdata_xauusd", "time, timeframe, type, price"),
    ("marketdata_xauusd_m15", "time"),
    ("marketdata_xauusd_h1", "time"),
    ("marketdata_xauusd_h4", "time"),
    ("sessionzone_xauusd", "start_time, session"),
]

print("=== PENGECEKAN DUPLIKASI DI DATABASE ===")
for tbl, cols in checks:
    query = f"""
        SELECT {cols}, COUNT(*) 
        FROM {tbl} 
        GROUP BY {cols} 
        HAVING COUNT(*) > 1
    """
    cur.execute(query)
    dups = cur.fetchall()
    print(f"  {tbl:<25}: {len(dups)} baris duplikat (Status: {'BERSIH TANPA DUPLIKAT' if len(dups) == 0 else 'ADA DUPLIKAT'})")

cur.close()
conn.close()
