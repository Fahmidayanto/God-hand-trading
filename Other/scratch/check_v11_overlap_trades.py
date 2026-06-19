
import os

BASE = r"d:\Project\Project MT5"
filepath = os.path.join(BASE, "backtest_v11", "Backtest_Results_XAUUSD_2023-12-29.csv")

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.read().strip().splitlines()

print("=== V11 EXECUTED TRADES IN SYDNEY_TOKYO_OVERLAP ===")
for line in lines[1:]:
    if not line.strip():
        continue
    parts = line.split(',')
    status = parts[19].strip() if len(parts) > 19 else ''
    if status != 'EXECUTED':
        continue
    session = parts[12].strip() if len(parts) > 12 else ''
    if session in ('Sydney_Tokyo_Overlap', 'Sydney'):
        entry_time = parts[14].strip() if len(parts) > 14 else ''
        trade_type = parts[2].strip() if len(parts) > 2 else ''
        entry_price = parts[3].strip() if len(parts) > 3 else ''
        net_profit = parts[11].strip() if len(parts) > 11 else ''
        print(f"Time: {entry_time} | Type: {trade_type} | Entry: {entry_price} | Profit: {net_profit}")
