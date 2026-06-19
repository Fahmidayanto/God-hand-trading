import os

BASE = r"d:\Project\Project MT5"

filepath = os.path.join(BASE, "backtest_v11", "Backtest_Results_XAUUSD_2024-12-30.csv")
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.read().strip().splitlines()

header = lines[0].split(',')
print("Header columns:")
for idx, col in enumerate(header):
    print(f"  {idx}: {col}")

print("\nExecuted trades in V11 (2024):")
for idx, line in enumerate(lines[1:], 1):
    parts = line.split(',')
    status = parts[19].strip()
    if status == 'EXECUTED':
        ticket = parts[0].strip()
        trade_type = parts[2].strip()
        entry_price = parts[3].strip()
        net_profit = parts[11].strip()
        session_raw = parts[12].strip()
        entry_time = parts[14].strip()
        exit_type = parts[21].strip()
        print(f"  - {entry_time} | {trade_type} | {entry_price} | {session_raw} | Profit: {net_profit} | Exit: {exit_type}")
