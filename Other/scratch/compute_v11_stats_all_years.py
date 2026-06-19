
import os

BASE = r"d:\Project\Project MT5"
yr_files = {
    2020: "Backtest_Results_XAUUSD_2020-12-30.csv",
    2021: "Backtest_Results_XAUUSD_2021-12-30.csv",
    2022: "Backtest_Results_XAUUSD_2022-12-30.csv",
    2023: "Backtest_Results_XAUUSD_2023-12-29.csv",
    2024: "Backtest_Results_XAUUSD_2024-12-30.csv",
    2025: "Backtest_Results_XAUUSD_2025-12-30.csv"
}

def parse_v11_csv(year):
    filepath = os.path.join(BASE, "backtest_v11", yr_files[year])
    if not os.path.exists(filepath):
        # try to find any file starting with year
        dir_path = os.path.join(BASE, "backtest_v11")
        matching = [f for f in os.listdir(dir_path) if f.startswith(f"Backtest_Results_XAUUSD_{year}")]
        if matching:
            filepath = os.path.join(dir_path, matching[0])
        else:
            return None
            
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip().splitlines()
    if not content:
        return None
        
    trades = []
    for line in content[1:]:
        if not line.strip():
            continue
        parts = line.split(',')
        try:
            net_profit = float(parts[11])
        except:
            net_profit = 0.0
        status = parts[19].strip() if len(parts) > 19 else ''
        trades.append({'net_profit': net_profit, 'status': status})
    return trades

for yr in sorted(yr_files.keys()):
    trades = parse_v11_csv(yr)
    if trades is not None:
        exec_trades = [t for t in trades if t['status'] == 'EXECUTED']
        rejected = [t for t in trades if t['status'] == 'REJECTED']
        wins = [t for t in exec_trades if t['net_profit'] > 0]
        losses = [t for t in exec_trades if t['net_profit'] <= 0]
        total_profit = sum(t['net_profit'] for t in exec_trades)
        win_rate = len(wins) / len(exec_trades) * 100 if exec_trades else 0.0
        print(f"Year {yr}: Executed={len(exec_trades)}, Rejected={len(rejected)}, Wins={len(wins)}, Losses={len(losses)}, WinRate={win_rate:.2f}%, Profit=${total_profit:.2f}")
    else:
        print(f"Year {yr}: No file found")
