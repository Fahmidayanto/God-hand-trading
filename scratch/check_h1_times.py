import os, psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('ValueCell_MT5/backend/.env')
conn = psycopg2.connect(
    host=os.getenv('PGHOST'),
    database=os.getenv('PGDATABASE'),
    user=os.getenv('PGUSER'),
    password=os.getenv('PGPASSWORD'),
    sslmode='require'
)
with conn.cursor() as cur:
    cur.execute("SELECT date_trunc('day', time) as d, MIN(time) FROM marketdata_xauusd_h4 WHERE time >= '2026-09-01' GROUP BY date_trunc('day', time) ORDER BY d ASC LIMIT 5")
    print('H4 min time per day:', cur.fetchall())
    cur.execute("SELECT date_trunc('day', time) as d, MIN(time) FROM marketdata_xauusd_m15 WHERE time >= '2026-09-01' GROUP BY date_trunc('day', time) ORDER BY d ASC LIMIT 5")
    print('M15 min time per day:', cur.fetchall())
conn.close()
