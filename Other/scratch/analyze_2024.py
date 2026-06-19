import csv, os

BASE = r"d:\Project\Project MT5"

V11_SESSION_MAP = {
    'Sydney_Tokyo_Overlap': 'Asia',
    'Tokyo_London_Overlap': 'London',
    'Sydney': 'Asia',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'NoSession': 'NoSession',
    'Asia': 'Asia',
}

SESSIONS = ['London', 'London_NewYork_Overlap', 'Asia', 'NoSession', 'NewYork']
SESSION_LABELS = {
    'London': 'London',
    'London_NewYork_Overlap': 'Overlap',
    'Asia': 'Asia',
    'NoSession': 'NoSession',
    'NewYork': 'NewYork',
}

def parse_csv(filepath, version):
    trades = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip().splitlines()

    header = content[0].split(',')
    # V7-V10 = 20 cols, V11 = 22 cols (extra: IsStretchy, ExitType)
    is_v11 = len(header) > 20

    for line in content[1:]:
        if not line.strip():
            continue
        parts = line.split(',')

        if is_v11:
            # col indices: 12=Session, 13=IsStretchy, 14=EntryTime, 19=Status, 20=Reject_Reason, 21=ExitType
            session_raw = parts[12].strip() if len(parts) > 12 else ''
            session = V11_SESSION_MAP.get(session_raw, session_raw)
            entry_time = parts[14].strip()[:16] if len(parts) > 14 else ''
            status = parts[19].strip() if len(parts) > 19 else ''
            reject_reason = parts[20].strip() if len(parts) > 20 else ''
            exit_type = parts[21].strip() if len(parts) > 21 else ''
        else:
            # col indices: 12=Session, 13=EntryTime, 18=Status, 19=Reject_Reason
            session = parts[12].strip() if len(parts) > 12 else ''
            entry_time = parts[13].strip()[:16] if len(parts) > 13 else ''
            status = parts[18].strip() if len(parts) > 18 else ''
            reject_reason = parts[19].strip() if len(parts) > 19 else ''
            exit_type = 'N/A'

        try:
            net_profit = float(parts[11])
        except:
            net_profit = 0.0

        try:
            entry_price = float(parts[3])
        except:
            entry_price = 0.0

        trade_type = parts[2].strip() if len(parts) > 2 else ''

        trades.append({
            'type': trade_type,
            'entry_price': entry_price,
            'net_profit': net_profit,
            'session': session,
            'entry_time': entry_time,
            'status': status,
            'reject_reason': reject_reason,
            'exit_type': exit_type,
        })
    return trades

def compute_stats(trades, session_filter=None):
    items = [t for t in trades if t['session'] == session_filter] if session_filter else trades
    executed = [t for t in items if t['status'] == 'EXECUTED']
    rejected = [t for t in items if t['status'] == 'REJECTED']
    wins = [t for t in executed if t['net_profit'] > 0]
    losses = [t for t in executed if t['net_profit'] <= 0]
    total_profit = sum(t['net_profit'] for t in executed)
    win_rate = len(wins) / len(executed) * 100 if executed else 0
    return {
        'exec': len(executed), 'rej': len(rejected),
        'wins': len(wins), 'losses': len(losses),
        'total_profit': total_profit, 'win_rate': win_rate,
    }

versions = [7, 8, 9, 10, 11]
all_trades = {}

for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2024-12-30.csv")
    all_trades[v] = parse_csv(csv_file, v)

# Debug V11
print("=== V11 DEBUG ===")
v11_ex = [t for t in all_trades[11] if t['status']=='EXECUTED']
v11_rej = [t for t in all_trades[11] if t['status']=='REJECTED']
print(f"V11 EXECUTED: {len(v11_ex)}, REJECTED: {len(v11_rej)}")
if v11_ex:
    print("First V11 exec sample:", v11_ex[0])

print("\n" + "="*60)
print("RINGKASAN PERFORMA 2024")
print("="*60)

metrics = {}
for v in versions:
    s = compute_stats(all_trades[v])
    total_sig = s['exec'] + s['rej']
    ppt = s['total_profit'] / s['exec'] if s['exec'] > 0 else 0
    metrics[v] = {**s, 'total_sig': total_sig, 'ppt': ppt}

print(f"{'Metrik':<28} | {'V7':>10} | {'V8':>10} | {'V9':>10} | {'V10':>10} | {'V11':>10}")
print("-"*80)
for key, label in [
    ('total_sig','Total Signals'), ('exec','EXECUTED Trades'),
    ('rej','REJECTED Signals'), ('wins','WIN'), ('losses','LOSS')]:
    vals = [metrics[v][key] for v in versions]
    print(f"{label:<28} | {vals[0]:>10} | {vals[1]:>10} | {vals[2]:>10} | {vals[3]:>10} | {vals[4]:>10}")

print(f"{'Win Rate':<28} | {metrics[7]['win_rate']:>9.2f}% | {metrics[8]['win_rate']:>9.2f}% | {metrics[9]['win_rate']:>9.2f}% | {metrics[10]['win_rate']:>9.2f}% | {metrics[11]['win_rate']:>9.2f}%")
print(f"{'Total Net Profit':<28} | ${metrics[7]['total_profit']:>9.2f} | ${metrics[8]['total_profit']:>9.2f} | ${metrics[9]['total_profit']:>9.2f} | ${metrics[10]['total_profit']:>9.2f} | ${metrics[11]['total_profit']:>9.2f}")
print(f"{'Profit per Trade':<28} | ${metrics[7]['ppt']:>9.2f} | ${metrics[8]['ppt']:>9.2f} | ${metrics[9]['ppt']:>9.2f} | ${metrics[10]['ppt']:>9.2f} | ${metrics[11]['ppt']:>9.2f}")

print("\n" + "="*60)
print("REJECTION BREAKDOWN 2024")
print("="*60)
for v in versions:
    rejected = [t for t in all_trades[v] if t['status'] == 'REJECTED']
    h1 = sum(1 for t in rejected if 'H1' in t['reject_reason'])
    h4 = sum(1 for t in rejected if 'H4' in t['reject_reason'])
    br = sum(1 for t in rejected if 'Body' in t['reject_reason'])
    total = len(rejected)
    total_sig = metrics[v]['total_sig']
    pct = total/total_sig*100 if total_sig > 0 else 0
    print(f"V{v}: {total} REJECTED ({pct:.1f}%) -- H1: {h1}, H4: {h4}, BR: {br}")

print("\n" + "="*60)
print("SESSION STATS 2024")
print("="*60)
sess_data = {}
for sess in SESSIONS:
    sess_data[sess] = {}
    for v in versions:
        sess_data[sess][v] = compute_stats(all_trades[v], sess)

for sess in SESSIONS:
    print(f"\n--- {SESSION_LABELS[sess]} ---")
    print(f"{'Metrik':<12} | {'V7':>8} | {'V8':>8} | {'V9':>8} | {'V10':>8} | {'V11':>8}")
    print("-"*65)
    for key, label in [('exec','Executed'), ('wins','WIN'), ('losses','LOSS')]:
        vals = [sess_data[sess][v][key] for v in versions]
        print(f"{label:<12} | {vals[0]:>8} | {vals[1]:>8} | {vals[2]:>8} | {vals[3]:>8} | {vals[4]:>8}")
    wrs = [f"{sess_data[sess][v]['win_rate']:.1f}%" for v in versions]
    print(f"{'Win Rate':<12} | {wrs[0]:>8} | {wrs[1]:>8} | {wrs[2]:>8} | {wrs[3]:>8} | {wrs[4]:>8}")
    profs = [f"${sess_data[sess][v]['total_profit']:.2f}" for v in versions]
    print(f"{'Net Profit':<12} | {profs[0]:>8} | {profs[1]:>8} | {profs[2]:>8} | {profs[3]:>8} | {profs[4]:>8}")

print("\n" + "="*60)
print("CROSS-SESSION SUMMARY (for table)")
print("="*60)
header = "| Session | V7 Exec | V7 WR | V7 Net | V8 Exec | V8 WR | V8 Net | V9 Exec | V9 WR | V9 Net | V10 Exec | V10 WR | V10 Net | V11 Exec | V11 WR | V11 Net |"
sep = "|---------|---------|-------|--------|---------|-------|--------|---------|-------|--------|----------|--------|---------|----------|--------|---------|"
print(header)
print(sep)

grand_total = {v: {'exec':0,'wins':0,'profit':0} for v in versions}
for sess in SESSIONS:
    row = f"| **{SESSION_LABELS[sess]}** |"
    for v in versions:
        s = sess_data[sess][v]
        grand_total[v]['exec'] += s['exec']
        grand_total[v]['wins'] += s['wins']
        grand_total[v]['profit'] += s['total_profit']
        row += f" {s['exec']} | {s['win_rate']:.1f}% | ${s['total_profit']:.2f} |"
    print(row)

# Total row
row = "| **TOTAL** |"
for v in versions:
    t = grand_total[v]
    wr = t['wins']/t['exec']*100 if t['exec'] else 0
    row += f" **{t['exec']}** | **{wr:.1f}%** | **${t['profit']:.2f}** |"
print(row)

print("\n" + "="*60)
print("RANKING 2024")
print("="*60)
profits = sorted([(v, metrics[v]['total_profit'], metrics[v]['win_rate'], metrics[v]['exec']) for v in versions], key=lambda x: -x[1])
for rank, (v, profit, wr, ex) in enumerate(profits, 1):
    print(f"  {rank}. V{v}: ${profit:.2f} | WR={wr:.2f}% | Exec={ex} | PPT=${profit/ex:.2f}")
