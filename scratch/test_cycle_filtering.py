import pandas as pd

df = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
structures = df.to_dict('records')

# Find all events
events = [s for s in structures if str(s['Time']) <= '2026.01.08 08:00:00']

# Group by structure breakout cycle
cycle_events = []
current_cycle = []

for s in events:
    s_type = str(s['Type']).upper()
    current_cycle.append(s)
    if s_type in ('BOS', 'CHOCH'):
        cycle_events.append(current_cycle)
        current_cycle = []
if current_cycle:
    cycle_events.append(current_cycle)

print(f"Total cycles in window: {len(cycle_events)}")
for c_idx, cycle in enumerate(cycle_events):
    print(f"\n--- Cycle {c_idx+1} ---")
    highest_hh = None
    lowest_ll = None
    breakout = None
    for item in cycle:
        t = str(item['Type']).upper()
        p = float(item['Price']) if pd.notnull(item['Price']) else 0
        tm = str(item['Time'])
        if t in ('HH', 'LH'):
            if highest_hh is None or p > highest_hh['price']:
                highest_hh = {'price': p, 'time': tm}
            else:
                print(f"  [DISCARD LOWER HH] {p} at {tm} (< Highest {highest_hh['price']})")
        elif t in ('LL', 'HL'):
            if lowest_ll is None or p < lowest_ll['price']:
                lowest_ll = {'price': p, 'time': tm}
            else:
                print(f"  [DISCARD HIGHER LL] {p} at {tm} (> Lowest {lowest_ll['price']})")
        elif t in ('BOS', 'CHOCH'):
            breakout = f"{t} {item['Direction/Action']} {p} at {tm}"
    
    if highest_hh:
        print(f"  -> ACTIVE HIGHEST HH: {highest_hh['price']} at {highest_hh['time']}")
    if lowest_ll:
        print(f"  -> ACTIVE LOWEST LL: {lowest_ll['price']} at {lowest_ll['time']}")
    if breakout:
        print(f"  -> BREAKOUT: {breakout}")
