
import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

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

SESSIONS_6 = ['Sydney_Tokyo_Overlap', 'Tokyo_London_Overlap', 'London', 'London_NewYork_Overlap', 'NewYork', 'Asia']

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
            'session_raw': session_raw,
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

# Build master signal keys
all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))
sorted_keys = sorted(list(all_keys))

# Assign session to each signal (V11 priority)
signal_sessions = {}
signal_raw_sessions = {}
for k in sorted_keys:
    assigned_session = None
    assigned_raw = None
    for v in reversed(versions):
        matches = [t for t in trades_by_v[v] if t['entry_time'] == k[0] and t['type'] == k[1]]
        if matches:
            assigned_session = matches[0]['session']
            assigned_raw = matches[0]['session_raw']
            break
    signal_sessions[k] = assigned_session
    signal_raw_sessions[k] = assigned_raw

# Print trades per session
for sess in SESSIONS_6:
    keys_in_sess = [k for k in sorted_keys if signal_sessions[k] == sess]
    print(f"\n{'='*70}")
    print(f"SESSION: {sess}  ({len(keys_in_sess)} signals)")
    print(f"{'='*70}")
    for k in keys_in_sess:
        entry_time, trade_type = k
        raw_sess = signal_raw_sessions[k]
        row = f"  {entry_time} {trade_type:4s} [raw={raw_sess}]"
        for v in versions:
            matches = [t for t in trades_by_v[v] if t['entry_time'] == entry_time and t['type'] == trade_type]
            if not matches:
                row += f"  V{v}:—"
            else:
                t = matches[0]
                if t['status'] == 'EXECUTED':
                    sym = 'WIN' if t['net_profit'] > 0 else 'LOS'
                    row += f"  V{v}:{sym}${t['net_profit']:.2f}"
                else:
                    rr = t['reject_reason'][:2] if t['reject_reason'] else 'RJ'
                    row += f"  V{v}:REJ({rr})"
        print(row)
