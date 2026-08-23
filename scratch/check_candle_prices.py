import sqlite3

db_path = r"b:\Project MT5\ValueCell_MT5\backend\trading.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
    SELECT time, open, high, low, close, spread FROM marketdata_xauusd_m15 
    WHERE time >= 1767645600 AND time <= 1767674400 
    ORDER BY time ASC
""")
rows = cur.fetchall()

print("Candles around 2026-01-06 (Unix -> Time -> O H L C Spread):")
for r in rows:
    from datetime import datetime
    dt = datetime.utcfromtimestamp(r[0])
    print(f"Unix: {r[0]} | UTC: {dt} | Open: {r[1]} | High: {r[2]} | Low: {r[3]} | Close: {r[4]} | Spread: {r[5]}")

conn.close()
