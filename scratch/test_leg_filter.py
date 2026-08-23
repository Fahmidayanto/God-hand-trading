import pandas as pd

df = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
structures = df.to_dict('records')

# In replay.tsx, we build linesToDraw:
# For HH/LL lines, we only want to keep the true highest HH and true lowest LL in any swing leg.
def filter_structure_lines(structures_list):
    # Sort by time
    # Maintain active swing levels
    filtered = []
    
    # We can filter out any HH that is lower than a preceding unbroken HH in the same leg
    # And filter out any LL that is higher than a preceding unbroken LL in the same leg
    last_choch_bos_time = 0
    current_leg_highest_hh = None
    current_leg_lowest_ll = None
    
    valid_structures = []
    for s in structures_list:
        stype = str(s['Type']).upper()
        sprice = float(s['Price']) if pd.notnull(s['Price']) else 0
        stime = str(s['Time'])
        
        if stype in ('BOS', 'CHOCH'):
            valid_structures.append(s)
            # Reset leg
            current_leg_highest_hh = None
            current_leg_lowest_ll = None
        elif stype in ('HH', 'LH'):
            if current_leg_highest_hh is None or sprice > current_leg_highest_hh['Price']:
                # If there was a lower HH in this leg, remove it and replace with higher
                if current_leg_highest_hh is not None:
                    valid_structures = [v for v in valid_structures if v is not current_leg_highest_hh]
                current_leg_highest_hh = s
                valid_structures.append(s)
            else:
                # Lower HH in same leg -> discard!
                print(f"Skipping lower HH: {sprice} at {stime} (Leg Highest: {current_leg_highest_hh['Price']})")
        elif stype in ('LL', 'HL'):
            if current_leg_lowest_ll is None or sprice < current_leg_lowest_ll['Price']:
                if current_leg_lowest_ll is not None:
                    valid_structures = [v for v in valid_structures if v is not current_leg_lowest_ll]
                current_leg_lowest_ll = s
                valid_structures.append(s)
            else:
                # Higher LL in same leg -> discard!
                print(f"Skipping higher LL: {sprice} at {stime} (Leg Lowest: {current_leg_lowest_ll['Price']})")
        else:
            valid_structures.append(s)
            
    return valid_structures

res = filter_structure_lines(structures[:30])
print("\n--- Filtered Structures ---")
for r in res:
    print(f"{r['Type']} {r['Direction/Action']} {r['Price']} at {r['Time']}")
