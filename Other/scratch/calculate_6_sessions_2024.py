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
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2024-12-30.csv")
    trades_by_v[v] = parse_csv(csv_file, v)

# Align all signals (Executed + Rejected) across versions
# We group by (EntryTime, Type)
all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))

sorted_keys = sorted(list(all_keys))
print(f"Total aligned signals: {len(sorted_keys)}")

# Assign a single session to each signal
signal_sessions = {}
for k in sorted_keys:
    # Find session from V11 first, then V10, V9, V8, V7
    assigned_session = None
    for v in reversed(versions):
        matches = [t for t in trades_by_v[v] if t['entry_time'] == k[0] and t['type'] == k[1]]
        if matches:
            assigned_session = matches[0]['session']
            break
    signal_sessions[k] = assigned_session

# Standard 6 Sessions
SESSIONS_6 = [
    'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap',
    'London',
    'London_NewYork_Overlap',
    'NewYork',
    'Asia'
]

# Calculate stats for each session
session_stats = {}
for sess in SESSIONS_6:
    session_stats[sess] = {}
    for v in versions:
        # Get executed trades in version v that belong to this session
        v_exec = []
        v_rej = []
        for t in trades_by_v[v]:
            k = (t['entry_time'], t['type'])
            if signal_sessions[k] == sess:
                if t['status'] == 'EXECUTED':
                    v_exec.append(t)
                else:
                    v_rej.append(t)
        
        wins = [t for t in v_exec if t['net_profit'] > 0]
        losses = [t for t in v_exec if t['net_profit'] <= 0]
        total_profit = sum(t['net_profit'] for t in v_exec)
        win_rate = len(wins) / len(v_exec) * 100 if v_exec else 0.0
        
        session_stats[sess][v] = {
            'exec': len(v_exec),
            'rej': len(v_rej),
            'wins': len(wins),
            'losses': len(losses),
            'total_profit': total_profit,
            'win_rate': win_rate
        }

print("\n=== GENERATING MARKDOWN TABLES FOR SESSIONS ===")
for sess in SESSIONS_6:
    print(f"\n#### {sess.upper()} SESSION — 2024")
    print(f"| Metrik | V7 | V8 | V9 | V10 | V11 |")
    print(f"|--------|----|----|----|-----|-----|")
    
    exec_row = "| Executed |"
    wins_row = "| WIN |"
    loss_row = "| LOSS |"
    wr_row   = "| Win Rate |"
    prof_row = "| Net Profit |"
    
    for v in versions:
        s = session_stats[sess][v]
        exec_row += f" **{s['exec']}** |"
        wins_row += f" **{s['wins']}** |"
        loss_row += f" **{s['losses']}** |"
        wr_row   += f" **{s['win_rate']:.1f}%** |" if s['exec'] else " **—** |"
        prof_row += f" **${s['total_profit']:.2f}** |"
        
    print(exec_row)
    print(wins_row)
    print(loss_row)
    print(wr_row)
    print(prof_row)

print("\n=== CROSS-SESSION SUMMARY TABLE ===")
header = "| Session | V7 Exec | V7 WR | V7 Net | V8 Exec | V8 WR | V8 Net | V9 Exec | V9 WR | V9 Net | V10 Exec | V10 WR | V10 Net | V11 Exec | V11 WR | V11 Net |"
sep = "|---------|---------|-------|--------|---------|-------|--------|---------|-------|--------|----------|--------|---------|----------|--------|---------|"
print(header)
print(sep)

for sess in SESSIONS_6:
    row = f"| **{sess}** |"
    for v in versions:
        s = session_stats[sess][v]
        wr_str = f"{s['win_rate']:.1f}%" if s['exec'] else "—"
        row += f" {s['exec']} | {wr_str} | ${s['total_profit']:.2f} |"
    print(row)

# Print total row
row_total = "| **TOTAL** |"
for v in versions:
    t_exec = sum(session_stats[sess][v]['exec'] for sess in SESSIONS_6)
    t_wins = sum(session_stats[sess][v]['wins'] for sess in SESSIONS_6)
    t_profit = sum(session_stats[sess][v]['total_profit'] for sess in SESSIONS_6)
    t_wr = t_wins / t_exec * 100 if t_exec else 0.0
    row_total += f" **{t_exec}** | **{t_wr:.1f}%** | **${t_profit:.2f}** |"
print(row_total)
