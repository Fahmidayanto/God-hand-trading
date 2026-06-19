import os

BASE = r"d:\Project\Project MT5"

summary_file = os.path.join(BASE, "backtest_v8", "Backtest_Summary_XAUUSD_2024-12-30.csv")
if os.path.exists(summary_file):
    with open(summary_file, 'r', encoding='utf-8') as f:
        print("2024 V8 Summary:")
        print(f.read().strip())
