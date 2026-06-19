import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

trades_by_v = {}
for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2024-12-30.csv")
    trades = []
    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        header = lines[0].split(',')
        is_v11 = len(header) > 20
        for line in lines[1:]:
            parts = line.split(',')
            status = parts[19].strip() if is_v11 else parts[18].strip()
            if status == 'EXECUTED':
                trade_type = parts[2].strip()
                entry_price = parts[3].strip()
                net_profit = float(parts[11].strip())
                session = parts[12].strip()
                entry_time = parts[14].strip() if is_v11 else parts[13].strip()
                trades.append({
                    'entry_time': entry_time[:16],
                    'type': trade_type,
                    'entry_price': entry_price,
                    'net_profit': net_profit,
                    'session': session
                })
    trades_by_v[v] = trades

# Let's align them by (entry_time, type)
all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))

print("Index | Entry Time | Type | V7 Sess | V8 Sess | V9 Sess | V10 Sess | V11 Sess | V11 Net")
print("-" * 105)
for idx, k in enumerate(sorted(all_keys), 1):
    sess_vals = {}
    for v in versions:
        match = [t for t in trades_by_v[v] if t['entry_time'] == k[0] and t['type'] == k[1]]
        if match:
            sess_vals[v] = f"{match[0]['session']}({match[0]['net_profit']:.1f})"
        else:
            sess_vals[v] = "—"
    
    print(f"{idx:<5} | {k[0]} | {k[1]:<4} | {sess_vals[7]:<12} | {sess_vals[8]:<12} | {sess_vals[9]:<12} | {sess_vals[10]:<12} | {sess_vals[11]:<12}")
