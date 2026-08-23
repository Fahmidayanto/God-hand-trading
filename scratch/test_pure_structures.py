import psycopg2
import os
import datetime
from dotenv import load_dotenv

load_dotenv('ValueCell_MT5/backend/.env')
DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get structures for Jan 2020
cur.execute("""
    SELECT type, direction_action, price, time, timeframe, status, previous_price, previous_time
    FROM llhhbosdata_xauusd
    WHERE time >= '2020-01-01' AND time < '2020-02-01' AND timeframe = 'M15'
    ORDER BY time ASC
""")
structures = cur.fetchall()

# Find all CHoCH and BoS events
bos_choch = [s for s in structures if s[0] in ('BOS', 'CHOCH', 'BoS', 'CHoCH')]
print(f"Total BOS/CHOCH events in Jan 2020: {len(bos_choch)}")
for idx, s in enumerate(bos_choch):
    entry_time = s[3] + datetime.timedelta(minutes=15)
    print(f"#{idx+1}: {s[0]} {s[1]} at {s[3]} (Price: {s[2]}) -> Candidate Entry at {entry_time}")

cur.close()
conn.close()
