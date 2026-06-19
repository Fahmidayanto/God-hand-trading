import csv
from datetime import datetime

struct_file = r"d:\Project\Project MT5\backtest_v7\LLHHBOSData_XAUUSD_2024-12-30.csv"
v11_file = r"d:\Project\Project MT5\backtest_v11\Backtest_Results_XAUUSD_2024-12-30.csv"

# 1. Parse M15 structure events
events = []
with open(struct_file, 'r', encoding='utf-8') as f:
    f.readline()  # Skip title
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

# 3. Match
results = []
for dc in double_chochs:
    matched = None
    for trade in v11_trades:
        dir_match = (dc['bos_dir'] == 'Bullish' and trade['type'] == 'BUY') or (dc['bos_dir'] == 'Bearish' and trade['type'] == 'SELL')
        time_diff = abs((dc['bos_time'] - trade['entry_time']).total_seconds())
        if time_diff < 3600 and dir_match:
            matched = trade
            break
    results.append({
        'double_choch': dc,
        'trade': matched
    })

# 4. Print results with sessions
print("Double CHoCH v11 Comparison with Sessions:")
print("=" * 120)
for r in results:
    dc = r['double_choch']
    trade = r['trade']
    
    session = trade['session'] if trade else "Unknown"
    
    if trade:
        status_str = trade['status']
        if status_str == 'EXECUTED':
            pnl = trade['net_profit']
            exit_t = trade['exit_type']
            if pnl > 0:
                outcome = f"WIN (+${pnl:.2f}) [Exit: {exit_t}]"
            else:
                outcome = f"LOSS (${pnl:.2f})"
        else:
            outcome = f"REJECTED ({trade['reject_reason']})"
    else:
        outcome = "NO SIGNAL MATCHED"
        
    print(f"{dc['bos_time'].strftime('%Y.%m.%d %H:%M')} | Session: {session:25} | BOS: {dc['bos_dir']:7} | Outcome: {outcome}")

print("=" * 120)
