import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]
years = [2020, 2021, 2022, 2023, 2024, 2025]

def parse_csv(filepath, version):
    if not os.path.exists(filepath):
        return None
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

        try:
            entry_price = float(parts[3])
        except:
            entry_price = 0.0

        trade_type = parts[2].strip() if len(parts) > 2 else ''

        trades.append({
            'type': trade_type,
            'entry_price': entry_price,
            'net_profit': net_profit,
            'entry_time': entry_time,
            'status': status,
            'reject_reason': reject_reason,
            'exit_type': exit_type,
        })
    return trades

def compute_stats(trades):
    if trades is None:
        return None
    executed = [t for t in trades if t['status'] == 'EXECUTED']
    rejected = [t for t in trades if t['status'] == 'REJECTED']
    wins = [t for t in executed if t['net_profit'] > 0]
    losses = [t for t in executed if t['net_profit'] <= 0]
    total_profit = sum(t['net_profit'] for t in executed)
    win_rate = len(wins) / len(executed) * 100 if executed else 0
    return {
        'total': len(trades),
        'exec': len(executed),
        'rej': len(rejected),
        'wins': len(wins),
        'losses': len(losses),
        'total_profit': total_profit,
        'win_rate': win_rate,
    }

for yr in years:
    print(f"\n================ YEAR {yr} ================")
    print(f"{'Ver':<5} | {'Total':<6} | {'Exec':<6} | {'Rej':<6} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<8} | {'Profit':<10}")
    print("-" * 70)
    for v in versions:
        dir_path = os.path.join(BASE, f"backtest_v{v}")
        matching_files = []
        if os.path.exists(dir_path):
            matching_files = [f for f in os.listdir(dir_path) if f.startswith(f"Backtest_Results_XAUUSD_{yr}")]
        if matching_files:
            filepath = os.path.join(dir_path, matching_files[0])
            trades = parse_csv(filepath, v)
            s = compute_stats(trades)
            print(f"V{v:<4} | {s['total']:<6} | {s['exec']:<6} | {s['rej']:<6} | {s['wins']:<6} | {s['losses']:<6} | {s['win_rate']:>7.2f}% | ${s['total_profit']:>9.2f}")
        else:
            print(f"V{v:<4} | N/A")
