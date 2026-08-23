import pandas as pd

df = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
structures = df.to_dict('records')

# Filter algorithm
active_lines = []
for s in structures:
    s_type = str(s['Type']).upper()
    s_price = float(s['Price']) if pd.notnull(s['Price']) else 0
    s_time = str(s['Time'])
    
    if s_type in ('HH', 'LH'):
        # Check if there is an active HH/LH that hasn't been broken
        # If the new HH is lower than existing active HH, reject it
        # If new HH is higher, update existing HH
        replaced = False
        is_lower = False
        for ex in active_lines:
            if ex['type'] in ('HH', 'LH') and not ex.get('broken', False):
                if s_price <= ex['price']:
                    is_lower = True
                    break
                else:
                    ex['price'] = s_price
                    ex['time'] = s_time
                    replaced = True
                    break
        if is_lower:
            print(f"REJECTED Lower HH: {s_price} at {s_time} (Existing Active HH: {ex['price']})")
            continue
        if not replaced:
            active_lines.append({'type': s_type, 'price': s_price, 'time': s_time, 'broken': False})
            print(f"ACCEPTED New Highest HH: {s_price} at {s_time}")

    elif s_type in ('LL', 'HL'):
        replaced = False
        is_higher = False
        for ex in active_lines:
            if ex['type'] in ('LL', 'HL') and not ex.get('broken', False):
                if s_price >= ex['price']:
                    is_higher = True
                    break
                else:
                    ex['price'] = s_price
                    ex['time'] = s_time
                    replaced = True
                    break
        if is_higher:
            print(f"REJECTED Higher LL: {s_price} at {s_time} (Existing Active LL: {ex['price']})")
            continue
        if not replaced:
            active_lines.append({'type': s_type, 'price': s_price, 'time': s_time, 'broken': False})
            print(f"ACCEPTED New Lowest LL: {s_price} at {s_time}")
            
    elif s_type in ('BOS', 'CHOCH'):
        # Mark broken
        dir_str = str(s['Direction/Action']).upper()
        print(f"EVENT {s_type} {dir_str} at {s_price} ({s_time})")
        for ex in active_lines:
            if dir_str == 'BEARISH' and ex['type'] in ('LL', 'HL'):
                if abs(ex['price'] - s_price) <= 0.5:
                    ex['broken'] = True
            elif dir_str == 'BULLISH' and ex['type'] in ('HH', 'LH'):
                if abs(ex['price'] - s_price) <= 0.5:
                    ex['broken'] = True
