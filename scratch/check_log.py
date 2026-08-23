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
cur.execute("SELECT filename, rows_loaded, status FROM csv_load_log WHERE filename LIKE 'Backtest%' ORDER BY filename")
for row in cur.fetchall():
    print(f"  {row[1]:>5} rows | {row[2]:10} | {row[0]}")
cur.close()
conn.close()
