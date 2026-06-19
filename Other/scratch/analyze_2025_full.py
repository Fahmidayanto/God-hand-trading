import os
import re

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

# Session mapping for the 6 standard sessions
SESSION_MAPPING = {
    'Sydney_Tokyo_Overlap': 'Sydney_Tokyo_Overlap',
    'Sydney': 'Sydney_Tokyo_Overlap',
    'NoSession': 'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap': 'Tokyo_London_Overlap',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'Asia': 'Asia'
}

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
        try: net_profit = float(parts[11])
        except: net_profit = 0.0
        try: entry_price = float(parts[3])
        except: entry_price = 0.0
        try: sl = float(parts[5])
        except: sl = 0.0
        try: tp = float(parts[6])
        except: tp = 0.0
        trade_type = parts[2].strip()
        trades.append({
            'type': trade_type, 'entry_price': entry_price, 'sl': sl, 'tp': tp,
            'net_profit': net_profit, 'session': session, 'session_raw': session_raw,
            'entry_time': entry_time, 'status': status,
            'reject_reason': reject_reason, 'exit_type': exit_type,
        })
    return trades

def get_summary(version):
    summary_file = os.path.join(BASE, f"backtest_v{version}", "Backtest_Summary_XAUUSD_2025-12-30.csv")
    if os.path.exists(summary_file):
        with open(summary_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split(',')
            return {'max_dd': float(parts[6]), 'profit_factor': float(parts[7])}
    return {'max_dd': 0.0, 'profit_factor': 0.0}

# Parse existing 2025.md to extract Analisa per signal
def parse_old_analisa(md_path):
    analisa_map = {}
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    in_log = False
    for line in lines:
        line_s = line.strip()
        if '11.0b Signal Log' in line_s:
            in_log = True
            continue
        if in_log and '11.0c' in line_s:
            in_log = False
            break
        if in_log and line_s.startswith('|'):
            parts = [p.strip() for p in line_s.split('|')]
            if len(parts) < 12 or not parts[1] or parts[1] == '#' or parts[1].startswith('---'):
                continue
            try:
                int(parts[1])
            except:
                continue
            entry_time = parts[2]
            trade_type = parts[3]
            catatan = parts[10] if len(parts) > 10 else ''
            analisa = parts[11] if len(parts) > 11 else ''
            key = (entry_time, trade_type)
            analisa_map[key] = {'catatan': catatan, 'analisa': analisa}
    return analisa_map

# Parse all data
trades_by_v = {}
for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2025-12-30.csv")
    trades_by_v[v] = parse_csv(csv_file, v)

# Get summary stats
summaries = {v: get_summary(v) for v in versions}

# Find all unique signal keys
all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))
sorted_keys = sorted(list(all_keys))

# Build lookup dict for each version
lookup = {}
for v in versions:
    lookup[v] = {}
    for t in trades_by_v[v]:
        k = (t['entry_time'], t['type'])
        if k not in lookup[v]:
            lookup[v][k] = t

# Assign sessions (V11 preferred, then V10, V9, etc.)
signal_sessions = {}
for k in sorted_keys:
    for v in reversed(versions):
        if k in lookup[v]:
            signal_sessions[k] = lookup[v][k]['session']
            break

# Get entry price, sl, tp
def get_entry_info(k):
    for v in versions:
        if k in lookup[v] and lookup[v][k]['status'] == 'EXECUTED':
            t = lookup[v][k]
            return t['entry_price'], t['sl'], t['tp']
    # If all rejected, get from any version
    for v in versions:
        if k in lookup[v]:
            t = lookup[v][k]
            return t['entry_price'], t['sl'], t['tp']
    return 0.0, 0.0, 0.0

# Get status string for each version for a given signal key
def get_v_status(v, k):
    if k not in lookup[v]:
        return '—', 0.0
    t = lookup[v][k]
    if t['status'] == 'EXECUTED':
        if t['net_profit'] > 0:
            return '✅', t['net_profit']
        else:
            return '❌', t['net_profit']
    else:
        rr = t['reject_reason']
        if 'H1' in rr:
            return '🚫 H1', 0.0
        elif 'H4' in rr:
            return '🚫 H4', 0.0
        elif 'Body Ratio' in rr or 'BR' in rr:
            return '🚫 BR', 0.0
        elif 'Session' in rr:
            return '🚫 Session', 0.0
        else:
            return f'🚫 {rr[:10]}', 0.0

# Parse old analisa
old_md = os.path.join(BASE, "Dokumen", "2025.md")
old_analisa = parse_old_analisa(old_md)
print(f"Parsed {len(old_analisa)} analisa entries from old 2025.md")

# Overall metrics per version
metrics = {}
for v in versions:
    trades = trades_by_v[v]
    executed = [t for t in trades if t['status'] == 'EXECUTED']
    rejected = [t for t in trades if t['status'] != 'EXECUTED']
    wins = [t for t in executed if t['net_profit'] > 0]
    losses = [t for t in executed if t['net_profit'] <= 0]
    win_rate = len(wins) / len(executed) * 100 if executed else 0.0
    net_profit = sum(t['net_profit'] for t in executed)
    # sum from summary for consistency
    summ = summaries[v]
    metrics[v] = {
        'total': len(trades), 'exec': len(executed), 'rej': len(rejected),
        'wins': len(wins), 'losses': len(losses), 'win_rate': win_rate,
        'net_profit': net_profit, 'max_dd': summ['max_dd'], 'pf': summ['profit_factor']
    }

# Rejection breakdown
reject_breakdown = {}
for v in versions:
    breakdown = {}
    for t in trades_by_v[v]:
        if t['status'] != 'EXECUTED':
            rr = t['reject_reason']
            breakdown[rr] = breakdown.get(rr, 0) + 1
    reject_breakdown[v] = breakdown

# Session stats
session_stats = {}
for sess in SESSIONS_6:
    session_stats[sess] = {}
    for v in versions:
        v_exec = [t for t in trades_by_v[v] if t['session'] == sess and t['status'] == 'EXECUTED']
        wins = [t for t in v_exec if t['net_profit'] > 0]
        losses = [t for t in v_exec if t['net_profit'] <= 0]
        win_rate = len(wins) / len(v_exec) * 100 if v_exec else 0.0
        net_profit = sum(t['net_profit'] for t in v_exec)
        session_stats[sess][v] = {
            'exec': len(v_exec), 'wins': len(wins), 'losses': len(losses),
            'win_rate': win_rate, 'net_profit': net_profit
        }

print("\n=== SIGNAL COUNT BY SESSION ===")
for sess in SESSIONS_6:
    # Count unique signals in this session
    keys_in_sess = [k for k in sorted_keys if signal_sessions[k] == sess]
    print(f"{sess}: {len(keys_in_sess)} unique signals")

print("\n=== SESSION STATS ===")
for sess in SESSIONS_6:
    print(f"\n{sess}:")
    for v in versions:
        s = session_stats[sess][v]
        print(f"  V{v}: Exec={s['exec']}, WIN={s['wins']}, LOSS={s['losses']}, WR={s['win_rate']:.1f}%, Net=${s['net_profit']:.2f}")

print("\n=== OVERALL METRICS ===")
for v in versions:
    m = metrics[v]
    print(f"V{v}: Signals={m['total']} | Exec={m['exec']} | Rej={m['rej']} | W={m['wins']} | L={m['losses']} | WR={m['win_rate']:.2f}% | Net=${m['net_profit']:.2f} | MaxDD=${m['max_dd']:.2f} | PF={m['pf']:.2f}")

print("\n=== REJECTION BREAKDOWN ===")
for v in versions:
    print(f"V{v}: {reject_breakdown[v]}")
