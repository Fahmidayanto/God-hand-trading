import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv('ValueCell_MT5/backend/.env')
DATABASE_URL = os.getenv('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get M15 structures for Jan 2020
cur.execute("""
    SELECT type, direction_action, price, time, timeframe, status, previous_price, previous_time
    FROM llhhbosdata_xauusd
    WHERE time >= '2020-01-01' AND time < '2020-02-01' AND timeframe = 'M15'
    ORDER BY time ASC
""")
structures = cur.fetchall()

# Get trades from backtest_results_xauusd
cur.execute("""
    SELECT ticket, type, status, reject_reason, entry_price, exit_price, sl, tp,
           net_profit, session, entry_time, exit_time, lot_size
    FROM backtest_results_xauusd
    WHERE entry_time >= '2020-01-01' AND entry_time < '2020-02-01'
    ORDER BY entry_time ASC
""")
trades = cur.fetchall()

print(f"Total structures in DB: {len(structures)}")
print(f"Total trades in DB: {len(trades)}")

# Print structures around 2020-01-15 to 2020-01-16
print("\n--- Structures 15-16 Jan ---")
for s in structures:
    if '2020-01-15' in str(s[3]) or '2020-01-16' in str(s[3]):
        print(s)

# Print trades around 2020-01-15 to 2020-01-16
print("\n--- DB Trades 15-16 Jan ---")
for t in trades:
    if '2020-01-15' in str(t[10]) or '2020-01-16' in str(t[10]):
        print(t)

cur.close()
conn.close()
