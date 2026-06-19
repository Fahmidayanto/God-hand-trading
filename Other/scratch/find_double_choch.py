import csv
from datetime import datetime

file_path = r"d:\Project\Project MT5\backtest_v7\LLHHBOSData_XAUUSD_2024-12-30.csv"

events = []
with open(file_path, 'r', encoding='utf-8') as f:
    # Skip first line if it's the title
    first_line = f.readline()
    reader = csv.reader(f)
    for row in reader:
        if not row or len(row) < 5:
            continue
        # Row format: Type,Direction/Action,Price,Time,Timeframe,Status,PreviousPrice,PreviousTime
        event_type, direction, price, time_str, timeframe = row[0], row[1], row[2], row[3], row[4]
        if timeframe == 'M15' and event_type in ('CHoCH', 'BoS'):
            events.append({
                'type': event_type,
                'direction': direction,
                'price': float(price) if price else 0.0,
                'time': time_str
            })

# Let's find sequence of CHoCH -> CHoCH -> BoS
# A double CHoCH occurs when we have two opposite CHoCHs before a BoS (or within a reasonable time window)
# Let's print out all CHoCH and BoS events sequentially to inspect the patterns
print("Sequential M15 CHoCH & BoS events in 2024:")
print("=" * 60)
for i in range(len(events)):
    ev = events[i]
    print(f"{ev['time']} | {ev['type']} {ev['direction']}")

print("\nScanning for Double CHoCH patterns:")
print("=" * 60)
# Let's define a Double CHoCH as: CHoCH (Type A) -> CHoCH (Type B) -> BoS (Type B)
# Let's walk through the events list
i = 0
while i < len(events) - 2:
    e1 = events[i]
    e2 = events[i+1]
    e3 = events[i+2]
    
    if e1['type'] == 'CHoCH' and e2['type'] == 'CHoCH' and e3['type'] == 'BoS':
        # Check if they are opposite directions
        if e1['direction'] != e2['direction']:
            # Double CHoCH!
            print(f"Double CHoCH found!")
            print(f"  1. {e1['type']} {e1['direction']} @ {e1['time']}")
            print(f"  2. {e2['type']} {e2['direction']} @ {e2['time']}")
            print(f"  3. Triggered Entry: {e3['type']} {e3['direction']} @ {e3['time']}")
            
            # Let's check the time difference between CHoCH 1 and CHoCH 2
            t1 = datetime.strptime(e1['time'], "%Y.%m.%d %H:%M:%S")
            t2 = datetime.strptime(e2['time'], "%Y.%m.%d %H:%M:%S")
            diff_hours = (t2 - t1).total_seconds() / 3600.0
            print(f"  Time between CHoCHs: {diff_hours:.1f} hours")
            print("-" * 50)
    i += 1
