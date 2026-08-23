import csv
import os

path = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files\Backtest_Results_XAUUSD_2026-08-20.csv"
if not os.path.exists(path):
    path = r"C:\Users\fahmi\Downloads\Backtest_Results_XAUUSD_2026-08-20.csv"

with open(path, "r", encoding="utf-8", errors="ignore") as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")
for r in rows[:10]:
    print(f"Ticket: {r.get('Ticket')} | Lot: {r.get('LotSize')} | Spread_Cost: {r.get('Spread_Cost')} | Commission: {r.get('Commission')} | Swap: {r.get('Swap')} | Profit: {r.get('Profit')} | Net_Profit: {r.get('Net_Profit')}")
