import os

BASE = r"d:\Project\Project MT5"

for v in [10, 11]:
    filepath = os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2023-12-29.csv")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        
        header = lines[0].split(',')
        is_v11 = len(header) > 20
        
        rejected = []
        for line in lines[1:]:
            parts = line.split(',')
            status = parts[19].strip() if is_v11 else parts[18].strip()
            reason = parts[20].strip() if is_v11 else parts[19].strip()
            if status == 'REJECTED':
                rejected.append(reason)
        
        from collections import Counter
        print(f"\n--- V{v} 2023 Rejections ({len(rejected)} total) ---")
        for reason, count in Counter(rejected).items():
            print(f"  {reason}: {count}")
