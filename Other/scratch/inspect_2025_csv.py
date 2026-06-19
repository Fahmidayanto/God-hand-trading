import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

for v in versions:
    csv_file = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2025-12-30.csv")
    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as f:
            header = f.readline().strip().split(',')
        print(f"V{v} Header: {header}")
        # Get unique raw session names
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        sessions = set()
        for line in lines[1:]:
            if line.strip():
                parts = line.split(',')
                sessions.add(parts[12].strip())
        print(f"V{v} Sessions: {sessions}")
    else:
        print(f"V{v} file does NOT exist: {csv_file}")
