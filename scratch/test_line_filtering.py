import pandas as pd

df = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
structures = df.to_dict('records')

# Simulate linesToDraw filtering for HH/LL
lines_to_draw = []
# Assume events up to 2026.01.08 08:00:00 (after BoS Bearish 4423.48)
events = [s for s in structures if str(s['Time']) <= '2026.01.08 08:00:00']

# Let's inspect raw HH events:
hh_events = [s for s in events if str(s['Type']).upper() in ('HH', 'LH')]
print("Raw HH events in window:")
for h in hh_events:
    print(f"Type: {h['Type']}, Price: {h['Price']}, Time: {h['Time']}")

# Filtering logic:
filtered_hh = []
for h in hh_events:
    h_price = float(h['Price'])
    h_time = str(h['Time'])
    
    # Check if there is an active HH from the same cycle
    # If a previous HH in the current cycle is higher, discard this lower HH
    # If this HH is higher than a previous unbroken HH, replace it
    superseded = False
    is_lower = False
    for ex in filtered_hh:
        # Check if they belong to same cycle (e.g. unbroken)
        if h_price <= ex['price']:
            is_lower = True
            break
        else:
            # higher peak replaces older lower peak
            ex['price'] = h_price
            ex['time'] = h_time
            superseded = True
            break
            
    if is_lower:
        print(f"-> Discarded lower HH {h_price} at {h_time} (Kept {ex['price']})")
        continue
    if not superseded:
        filtered_hh.append({'price': h_price, 'time': h_time})
        print(f"-> Added HH {h_price} at {h_time}")

print("\nFinal Filtered HH lines to display:")
for f in filtered_hh:
    print(f)
