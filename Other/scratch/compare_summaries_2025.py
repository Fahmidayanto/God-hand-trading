import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

for v in versions:
    summary_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Summary_XAUUSD_2025-12-30.csv")
    if os.path.exists(summary_file):
        with open(summary_file, 'r', encoding='utf-8') as f:
            print(f"V{v} Summary:")
            print(f.read().strip())
    else:
        print(f"V{v} Summary file does NOT exist: {summary_file}")
