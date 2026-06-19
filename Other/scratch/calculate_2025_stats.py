import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

# Map session names to the 6 standard raw sessions
SESSION_MAPPING = {
    'Sydney_Tokyo_Overlap': 'Sydney_Tokyo_Overlap',
    'Sydney': 'Sydney_Tokyo_Overlap',
    'NoSession': 'Sydney_Tokyo_Overlap', # pre-London maps to Sydney-Tokyo overlap
    'Tokyo_London_Overlap': 'Tokyo_London_Overlap',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'Asia': 'Asia'
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

        session_raw = parts[12].strip()
        session = SESSION_MAPPING.get(session_raw, session_raw)
        
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
            'session': session,
            'entry_time': entry_time,
            'status': status,
            'reject_reason': reject_reason,
            'exit_type': exit_type,
        })
    return trades

trades_by_v = {}
for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2025-12-30.csv")
    trades_by_v[v] = parse_csv(csv_file, v)

# Find all keys
all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))
sorted_keys = sorted(list(all_keys))

# Assign sessions
signal_sessions = {}
for k in sorted_keys:
    assigned_session = None
    for v in reversed(versions):
        matches = [t for t in trades_by_v[v] if t['entry_time'] == k[0] and t['type'] == k[1]]
        if matches:
            assigned_session = matches[0]['session']
            break
    signal_sessions[k] = assigned_session

# Print overall summary metrics per version
print("=== OVERALL METRICS 2025 ===")
for v in versions:
    trades = trades_by_v[v]
    total_signals = len(trades)
    executed = [t for t in trades if t['status'] == 'EXECUTED']
    rejected = [t for t in trades if t['status'] != 'EXECUTED']
    wins = [t for t in executed if t['net_profit'] > 0]
    losses = [t for t in executed if t['net_profit'] <= 0]
    win_rate = len(wins) / len(executed) * 100 if executed else 0.0
    net_profit = sum(t['net_profit'] for t in executed)
    prof_per_trade = net_profit / len(executed) if executed else 0.0
    
    # Read summary file for max drawdown and profit factor
    summary_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Summary_XAUUSD_2025-12-30.csv")
    max_dd = 0.0
    prof_factor = 0.0
    if os.path.exists(summary_file):
        with open(summary_file, 'r', encoding='utf-8') as f:
            s_lines = f.read().strip().splitlines()
        if len(s_lines) > 1:
            s_parts = s_lines[1].split(',')
            try:
                max_dd = float(s_parts[6])
                prof_factor = float(s_parts[7])
            except Exception as e:
                pass
                
    print(f"V{v}: Signals={total_signals} | Exec={len(executed)} | Rej={len(rejected)} | Wins={len(wins)} | Losses={len(losses)} | WR={win_rate:.2f}% | Profit=${net_profit:.2f} | Profit/Trade=${prof_per_trade:.2f} | MaxDD=${max_dd:.2f} | PF={prof_factor:.2f}")

# Print rejection breakdowns
print("\n=== REJECTION BREAKDOWNS 2025 ===")
for v in versions:
    trades = trades_by_v[v]
    rejections = [t for t in trades if t['status'] != 'EXECUTED']
    reason_counts = {}
    for r in rejections:
        reason = r['reject_reason']
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    print(f"V{v}: Rejections total={len(rejections)} | {reason_counts}")
