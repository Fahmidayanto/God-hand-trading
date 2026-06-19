import os

BASE = r"d:\Project\Project MT5"

for v in [10, 11]:
    filepath = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2024-12-30.csv")
    if os.path.exists(filepath):
        print(f"\n--- V{v} Sample ---")
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        print("Header:", lines[0])
        for line in lines[1:5]:
            print(line)
