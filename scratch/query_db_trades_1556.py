import psycopg2
import os
from dotenv import load_dotenv

# Load env
load_dotenv('ValueCell_MT5/backend/.env')
DATABASE_URL = os.getenv('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Query trades around 2020-01-16
cur.execute("""
    SELECT ticket, type, status, reject_reason, entry_price, exit_price, sl, tp,
           net_profit, session, entry_time, exit_time, lot_size
    FROM backtest_results_xauusd
    WHERE entry_time >= '2020-01-15' AND entry_time <= '2020-01-17'
    ORDER BY entry_time ASC, ticket ASC
""")
rows = cur.fetchall()
print(f"Total rows found: {len(rows)}")
for r in rows:
    print(r)

cur.close()
conn.close()
