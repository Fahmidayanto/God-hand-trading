import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

for v in versions:
    filepath = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2023-12-29.csv")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        header = lines[0].split(',')
        is_v11 = len(header) > 20
        sessions = []
        for line in lines[1:]:
            parts = line.split(',')
            session_raw = parts[12].strip()
            sessions.append(session_raw)
        
        from collections import Counter
        print(f"\n--- V{v} 2023 Raw Session Count ---")
        for s, count in Counter(sessions).items():
            print(f"  {s}: {count}")
