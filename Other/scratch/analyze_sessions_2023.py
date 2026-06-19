import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

V11_SESSION_MAP = {
    'Sydney_Tokyo_Overlap': 'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap': 'Tokyo_London_Overlap',
    'Sydney': 'Sydney_Tokyo_Overlap',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'NoSession': 'NoSession',
    'Asia': 'Sydney_Tokyo_Overlap',
}

# The sessions in 2023.md are named:
# - Sydney_Tokyo_Overlap
# - Tokyo_London_Overlap
# - London
# - London_NewYork_Overlap
# - NewYork
# - NoSession
# Wait! Let's check session names in V7-V10 CSV for 2023.
# In V7-V10, sessions are labeled: London, London_NewYork_Overlap, Sydney_Tokyo_Overlap, NewYork, NoSession, Tokyo_London_Overlap

SESSIONS_2023 = ['Sydney_Tokyo_Overlap', 'Tokyo_London_Overlap', 'London', 'London_NewYork_Overlap', 'NewYork', 'NoSession']

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

        trade_type = parts[2].strip() if len(parts) > 2 else ''

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
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2023-12-29.csv")
    trades_by_v[v] = parse_csv(csv_file, v)

for sess in SESSIONS_2023:
    print(f"\n================ SESSION {sess} ================")
    print(f"{'Ver':<5} | {'Signals':<7} | {'Executed':<8} | {'Rejected':<8} | {'Wins':<5} | {'Losses':<6} | {'Win Rate':<8} | {'Profit':<10}")
    print("-" * 75)
    for v in versions:
        trades = [t for t in trades_by_v[v] if t['session'] == sess]
        executed = [t for t in trades if t['status'] == 'EXECUTED']
        rejected = [t for t in trades if t['status'] == 'REJECTED']
        wins = [t for t in executed if t['net_profit'] > 0]
        losses = [t for t in executed if t['net_profit'] <= 0]
        total_profit = sum(t['net_profit'] for t in executed)
        win_rate = len(wins) / len(executed) * 100 if executed else 0.0
        print(f"V{v:<4} | {len(trades):<7} | {len(executed):<8} | {len(rejected):<8} | {len(wins):<5} | {len(losses):<6} | {win_rate:>7.2f}% | ${total_profit:>9.2f}")
