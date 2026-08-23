import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('ValueCell_MT5/backend/.env')
DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT type, time
    FROM llhhbosdata_xauusd
    WHERE time >= '2020-01-01' AND time < '2020-02-01' AND timeframe = 'M15'
          AND (type = 'BOS' OR type = 'CHOCH')
    ORDER BY time ASC
""")
structures = cur.fetchall()

cur.execute("""
    SELECT ticket, type, entry_time
    FROM backtest_results_xauusd
    WHERE entry_time >= '2020-01-01' AND entry_time < '2020-02-01'
    ORDER BY entry_time ASC
""")
db_trades = cur.fetchall()

print(f"Total BOS/CHOCH structures in Jan 2020: {len(structures)}")
print(f"Total DB trades in Jan 2020: {len(db_trades)}")

# Simulate deduplication with bucket (Math.round(ts / 900) * 900)
seen_buckets = {}
for t in db_trades:
    ticket, t_type, entry_time = t
    ts = int(entry_time.timestamp())
    bucket = round(ts / 900) * 900
    key = f"{t_type}_{bucket}"
    seen_buckets[key] = f"DB Trade #{ticket} at {entry_time}"

# Now simulate local candidate check
local_added = []
for s in structures:
    s_type, s_time = s
    event_sec = int(s_time.timestamp())
    candidate_entry_time = event_sec + 900
    bucket = round(candidate_entry_time / 900) * 900
    
    # Check if existing DB trade exists in this bucket
    # Assuming Bullish/Bearish
    for t_type in ['BUY', 'SELL']:
        key = f"{t_type}_{bucket}"
        if key in seen_buckets:
            # Already covered by DB trade!
            pass
        else:
            # New local candidate
            pass

print("\nAll DB Trade Buckets:")
for k, v in sorted(seen_buckets.items()):
    print(f"Bucket: {k} -> {v}")
