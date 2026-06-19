import os
import re

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

def parse_csv(filepath, version):
    if not os.path.exists(filepath):
        return []
    trades = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip().splitlines()

    if not content:
        return []

    header = content[0].split(',')
    is_v11 = len(header) > 20

    for line in content[1:]:
        if not line.strip():
            continue
        parts = line.split(',')

        session_raw = parts[12].strip()
        
        if is_v11:
            entry_time = parts[14].strip()[:16]
            status = parts[19].strip()
            reject_reason = parts[20].strip()
            exit_type = parts[21].strip()
        else:
            entry_time = parts[13].strip()[:16]
            status = parts[18].strip()
            reject_reason = parts[19].strip()
            exit_type = 'N/A'

        try:
            net_profit = float(parts[11])
        except:
            net_profit = 0.0

        try:
            entry_price = float(parts[3])
        except:
            entry_price = 0.0

        try:
            sl = float(parts[5])
        except:
            sl = 0.0

        try:
            tp = float(parts[6])
        except:
            tp = 0.0

        trade_type = parts[2].strip()

        trades.append({
            'type': trade_type,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'net_profit': net_profit,
            'session': session_raw,
            'entry_time': entry_time,
            'status': status,
            'reject_reason': reject_reason,
            'exit_type': exit_type,
        })
    return trades

# Parse all versions
trades_by_v = {}
for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2025-12-30.csv")
    trades_by_v[v] = parse_csv(csv_file, v)

# Check signal keys count
for v in versions:
    print(f"V{v}: Total signals in CSV = {len(trades_by_v[v])}")

# Let's find union of all keys
all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))

print(f"Total unique keys across all versions: {len(all_keys)}")
