import csv
from datetime import datetime
from collections import defaultdict

struct_file = r"d:\Project\Project MT5\backtest_v7\LLHHBOSData_XAUUSD_2024-12-30.csv"
v11_file = r"d:\Project\Project MT5\backtest_v11\Backtest_Results_XAUUSD_2024-12-30.csv"

# 1. Parse M15 structure events
events = []
with open(struct_file, 'r', encoding='utf-8') as f:
    f.readline()
    reader = csv.reader(f)
    for row in reader:
        if not row or len(row) < 5:
            continue
        event_type, direction, price, time_str, timeframe = row[0], row[1], row[2], row[3], row[4]
        if timeframe == 'M15' and event_type in ('CHoCH', 'BoS'):
            events.append({
                'type': event_type,
                'direction': direction,
                'price': float(price) if price else 0.0,
                'time': datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
            })

# Find Double CHoCH sequences
double_chochs = []
i = 0
while i < len(events) - 2:
    e1 = events[i]
    e2 = events[i+1]
    e3 = events[i+2]
    if e1['type'] == 'CHoCH' and e2['type'] == 'CHoCH' and e3['type'] == 'BoS':
        if e1['direction'] != e2['direction']:
            double_chochs.append({
                'choch1_time': e1['time'],
                'choch1_dir': e1['direction'],
                'choch2_time': e2['time'],
                'choch2_dir': e2['direction'],
                'bos_time': e3['time'],
                'bos_dir': e3['direction']
            })
    i += 1

# 2. Parse V11 backtest results
v11_trades = []
with open(v11_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        v11_trades.append({
            'ticket': int(row['Ticket']),
            'type': row['Type'],
            'entry_price': float(row['EntryPrice']),
            'net_profit': float(row['Net_Profit']),
            'session': row['Session'],
            'entry_time': datetime.strptime(row['EntryTime'], "%Y.%m.%d %H:%M:%S"),
            'status': row['Status'],
            'reject_reason': row['Reject_Reason'],
            'exit_type': row.get('ExitType', '')
        })

# 3. Match and Group
session_stats = defaultdict(lambda: {'total': 0, 'win': 0, 'loss': 0, 'rejected': 0, 'profit': 0.0})
hour_stats = defaultdict(lambda: {'total': 0, 'win': 0, 'loss': 0, 'rejected': 0, 'profit': 0.0})

# Keep track of details for reporting
session_details = defaultdict(list)

for dc in double_chochs:
    matched = None
    for trade in v11_trades:
        dir_match = (dc['bos_dir'] == 'Bullish' and trade['type'] == 'BUY') or (dc['bos_dir'] == 'Bearish' and trade['type'] == 'SELL')
        time_diff = abs((dc['bos_time'] - trade['entry_time']).total_seconds())
        if time_diff < 3600 and dir_match:
            matched = trade
            break
            
    # If not matched, we use the timestamp to approximate session/hour
    # Wait, MQL5 session classification in V11:
    # 04:45 -> Asia, 16:30 -> London_NewYork_Overlap, etc.
    # If matched, we get session from trade. If not, let's look at what MQL5 would classify it (or we can fallback)
    if matched:
        session = matched['session']
        status = matched['status']
        pnl = matched['net_profit'] if status == 'EXECUTED' else 0.0
        reason = matched['reject_reason'] if status == 'REJECTED' else "N/A"
    else:
        # Fallback approximation for session if not in trade log
        # (All 26 are actually in the trade log because MQL5 exports rejected ones too)
        session = "Unknown"
        status = "REJECTED"
        pnl = 0.0
        reason = "Filtered"
        
    hour = dc['bos_time'].hour
    hour_str = f"{hour:02d}:00"
    
    # Update Session stats
    session_stats[session]['total'] += 1
    if status == 'EXECUTED':
        if pnl > 0:
            session_stats[session]['win'] += 1
        else:
            session_stats[session]['loss'] += 1
        session_stats[session]['profit'] += pnl
    else:
        session_stats[session]['rejected'] += 1
        
    # Update Hour stats
    hour_stats[hour_str]['total'] += 1
    if status == 'EXECUTED':
        if pnl > 0:
            hour_stats[hour_str]['win'] += 1
        else:
            hour_stats[hour_str]['loss'] += 1
        hour_stats[hour_str]['profit'] += pnl
    else:
        hour_stats[hour_str]['rejected'] += 1

    session_details[session].append({
        'time': dc['bos_time'],
        'hour': hour_str,
        'bos_dir': dc['bos_dir'],
        'status': status,
        'pnl': pnl,
        'reason': reason if status == 'REJECTED' else (matched['exit_type'] if matched else '')
    })

print("Grouping by Session:")
print("=" * 90)
print(f"{'Session':30} | {'Total':5} | {'WIN':3} | {'LOSS':4} | {'REJ':3} | {'Profit':10} | {'Win Rate (Exec)'}")
print("-" * 90)
for sess, stats in sorted(session_stats.items(), key=lambda x: x[1]['profit'], reverse=True):
    wr = f"{stats['win'] / (stats['win'] + stats['loss']) * 100:.1f}%" if (stats['win'] + stats['loss']) > 0 else "0.0%"
    print(f"{sess:30} | {stats['total']:5d} | {stats['win']:3d} | {stats['loss']:4d} | {stats['rejected']:3d} | ${stats['profit']:9.2f} | {wr}")

print("\nGrouping by Hour:")
print("=" * 90)
print(f"{'Hour':10} | {'Total':5} | {'WIN':3} | {'LOSS':4} | {'REJ':3} | {'Profit':10} | {'Win Rate (Exec)'}")
print("-" * 90)
for hr, stats in sorted(hour_stats.items()):
    wr = f"{stats['win'] / (stats['win'] + stats['loss']) * 100:.1f}%" if (stats['win'] + stats['loss']) > 0 else "0.0%"
    print(f"{hr:10} | {stats['total']:5d} | {stats['win']:3d} | {stats['loss']:4d} | {stats['rejected']:3d} | ${stats['profit']:9.2f} | {wr}")

print("\nDetailed breakdown of grouped session trades:")
print("=" * 90)
for sess, trades in sorted(session_details.items()):
    print(f"\nSesi: {sess.upper()}")
    print("-" * 60)
    for t in sorted(trades, key=lambda x: x['time']):
        outcome = f"WIN (+${t['pnl']:.2f}) [{t['reason']}]" if t['status'] == 'EXECUTED' and t['pnl'] > 0 else (
            f"LOSS (${t['pnl']:.2f})" if t['status'] == 'EXECUTED' else f"REJECTED ({t['reason']})"
        )
        print(f"  - {t['time'].strftime('%Y.%m.%d %H:%M')} (Hour: {t['hour']}) | BOS: {t['bos_dir']:7} | {outcome}")
