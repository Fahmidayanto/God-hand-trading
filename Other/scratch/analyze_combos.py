import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

V11_SESSION_MAP = {
    'Sydney_Tokyo_Overlap': 'Asia',
    'Tokyo_London_Overlap': 'London',
    'Sydney': 'Asia',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'NoSession': 'NoSession',
    'Asia': 'Asia',
}

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

        if is_v11:
            session_raw = parts[12].strip() if len(parts) > 12 else ''
            session = V11_SESSION_MAP.get(session_raw, session_raw)
            entry_time = parts[14].strip()[:16] if len(parts) > 14 else ''
            status = parts[19].strip() if len(parts) > 19 else ''
            reject_reason = parts[20].strip() if len(parts) > 20 else ''
            exit_type = parts[21].strip() if len(parts) > 21 else ''
        else:
            session = parts[12].strip() if len(parts) > 12 else ''
            entry_time = parts[13].strip()[:16] if len(parts) > 13 else ''
            status = parts[18].strip() if len(parts) > 18 else ''
            reject_reason = parts[19].strip() if len(parts) > 19 else ''
            exit_type = 'N/A'

        try:
            net_profit = float(parts[11])
        except:
            net_profit = 0.0

        try:
            entry_price = float(parts[3])
        except:
            entry_price = 0.0

        trade_type = parts[2].strip() if len(parts) > 2 else ''

        trades.append({
            'type': trade_type,
            'entry_price': entry_price,
            'net_profit': net_profit,
            'entry_time': entry_time,
            'status': status,
            'reject_reason': reject_reason,
            'exit_type': exit_type,
        })
    return trades

trades_by_v = {}
for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2024-12-30.csv")
    trades_by_v[v] = parse_csv(csv_file, v)

executed_by_v = {}
for v in versions:
    executed_by_v[v] = { (t['entry_time'], t['type']): t for t in trades_by_v[v] if t['status'] == 'EXECUTED' }

all_keys = set()
for v in versions:
    all_keys.update(executed_by_v[v].keys())

print(f"Total unique executed trade keys: {len(all_keys)}")

# Let's count presence of each key across versions
from collections import Counter
presence_counts = {}
for k in all_keys:
    present_in = tuple(v for v in versions if k in executed_by_v[v])
    presence_counts[k] = present_in

# Count occurrences of each combination
combo_counts = Counter(presence_counts.values())

print("\n--- Trade Combinations (Executed) ---")
for combo, count in sorted(combo_counts.items(), key=lambda x: -x[1]):
    print(f"Versions {combo}: {count} trades")

print("\n--- Detailed Stats for V11 execution ---")
v11_keys = [k for k in all_keys if 11 in presence_counts[k]]
print(f"Total executed in V11: {len(v11_keys)}")
for k in v11_keys:
    t = executed_by_v[11][k]
    vers = presence_counts[k]
    print(f"  - {k[0]} {k[1]} at {t['entry_price']}: profit={t['net_profit']} | present in versions={vers}")
