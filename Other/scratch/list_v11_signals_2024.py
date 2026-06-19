import os

BASE = r"d:\Project\Project MT5"

filepath = os.path.join(BASE, "backtest_v11", "Backtest_Results_XAUUSD_2024-12-30.csv")
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.read().strip().splitlines()

print("Signal index, Entry Time, Type, V11 Session, Status:")
for idx, line in enumerate(lines[1:], 1):
    parts = line.split(',')
    trade_type = parts[2].strip()
    session_raw = parts[12].strip()
    entry_time = parts[14].strip()[:16]
    status = parts[19].strip()
    print(f"  {idx} | {entry_time} | {trade_type} | {session_raw} | {status}")
