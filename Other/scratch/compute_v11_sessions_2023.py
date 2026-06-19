
import os

BASE = r"d:\Project\Project MT5"
V11_SESSION_MAP = {
    'Sydney_Tokyo_Overlap': 'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap': 'Tokyo_London_Overlap',
    'Sydney': 'Sydney_Tokyo_Overlap',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'NoSession': 'NoSession',
    'Asia': 'Asia',
}

filepath = os.path.join(BASE, "backtest_v11", "Backtest_Results_XAUUSD_2023-12-29.csv")
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.read().strip().splitlines()

header = lines[0].split(',')
trades = []
for line in lines[1:]:
    if not line.strip():
        continue
    parts = line.split(',')
    status = parts[19].strip() if len(parts) > 19 else ''
    if status != 'EXECUTED':
        continue
    session_raw = parts[12].strip() if len(parts) > 12 else ''
    session = V11_SESSION_MAP.get(session_raw, session_raw)
    try:
        net_profit = float(parts[11])
    except:
        net_profit = 0.0
    trades.append({'session': session, 'net_profit': net_profit})

session_stats = {}
for t in trades:
    s = t['session']
    if s not in session_stats:
        session_stats[s] = {'exec': 0, 'wins': 0, 'losses': 0, 'profit': 0.0}
    session_stats[s]['exec'] += 1
    if t['net_profit'] > 0:
        session_stats[s]['wins'] += 1
    else:
        session_stats[s]['losses'] += 1
    session_stats[s]['profit'] += t['net_profit']

print("=== V11 2023 SESSION STATS ===")
for s, stats in sorted(session_stats.items()):
    wr = stats['wins'] / stats['exec'] * 100 if stats['exec'] else 0.0
    print(f"Session: {s:<25} | Exec={stats['exec']} | Wins={stats['wins']} | Losses={stats['losses']} | WR={wr:.1f}% | Profit=${stats['profit']:.2f}")

total_exec = sum(stats['exec'] for stats in session_stats.values())
total_profit = sum(stats['profit'] for stats in session_stats.values())
print(f"TOTAL: Executed={total_exec} | Profit=${total_profit:.2f}")
