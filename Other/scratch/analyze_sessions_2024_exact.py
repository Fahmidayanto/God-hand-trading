import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

# We will use the exact session names from the CSV files without mapping
SESSIONS_6 = [
    'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap',
    'London',
    'London_NewYork_Overlap',
    'NewYork',
    'Asia'
]

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

        # We keep the raw session value
        session = parts[12].strip()
        
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

        trade_type = parts[2].strip()

        trades.append({
            'type': trade_type,
            'net_profit': net_profit,
            'session': session,
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

print("=== RAW SESSION STATS 2024 ===")
for sess in SESSIONS_6:
    print(f"\n--- {sess} ---")
    print(f"{'Metrik':<12} | {'V7':>10} | {'V8':>10} | {'V9':>10} | {'V10':>10} | {'V11':>10}")
    print("-" * 75)
    
    row_exec = f"{'Executed':<12}"
    row_wins = f"{'WIN':<12}"
    row_loss = f"{'LOSS':<12}"
    row_wr   = f"{'Win Rate':<12}"
    row_profit = f"{'Net Profit':<12}"
    
    for v in versions:
        trades = [t for t in trades_by_v[v] if t['session'] == sess]
        exec_trades = [t for t in trades if t['status'] == 'EXECUTED']
        wins = [t for t in exec_trades if t['net_profit'] > 0]
        losses = [t for t in exec_trades if t['net_profit'] <= 0]
        total_profit = sum(t['net_profit'] for t in exec_trades)
        win_rate = len(wins) / len(exec_trades) * 100 if exec_trades else 0.0
        
        row_exec   += f" | {len(exec_trades):>10}"
        row_wins   += f" | {len(wins):>10}"
        row_loss   += f" | {len(losses):>10}"
        row_wr     += f" | {win_rate:>9.1f}%" if exec_trades else " |       —  "
        row_profit += f" | ${total_profit:>9.2f}"
        
    print(row_exec)
    print(row_wins)
    print(row_loss)
    print(row_wr)
    print(row_profit)

# Check if there is any other session in the raw files
print("\n--- ALL RAW SESSION STRINGS IN CSV FOR 2024 ---")
for v in versions:
    distinct_sessions = set(t['session'] for t in trades_by_v[v])
    print(f"V{v}: {distinct_sessions}")
