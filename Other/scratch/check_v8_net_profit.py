import os

BASE = r"d:\Project\Project MT5"
filepath = os.path.join(BASE, "backtest_v8", "Backtest_Results_XAUUSD_2025-12-30.csv")

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.read().strip().splitlines()

header = lines[0].split(',')
print("Header:", header)

sum_profit = 0.0
sum_net_profit = 0.0
sum_swap = 0.0
sum_comm = 0.0

for line in lines[1:]:
    if not line.strip():
        continue
    parts = line.split(',')
    status = parts[18].strip()
    if status != 'EXECUTED':
        continue
    
    profit = float(parts[7])
    swap = float(parts[10])
    comm = float(parts[9])
    net_profit = float(parts[11])
    
    sum_profit += profit
    sum_net_profit += net_profit
    sum_swap += swap
    sum_comm += comm

print(f"Sum of Profit: {sum_profit:.2f}")
print(f"Sum of Swap: {sum_swap:.2f}")
print(f"Sum of Commission: {sum_comm:.2f}")
print(f"Sum of Net Profit: {sum_net_profit:.2f}")
print(f"Profit + Swap + Commission: {sum_profit + sum_swap + sum_comm:.2f}")
