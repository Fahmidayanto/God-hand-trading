import pandas as pd

df_struct = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2026-08-21.csv')
df_candles.columns = [c.strip() for c in df_candles.columns]
for col in ['Open', 'High', 'Low', 'Close']:
    df_candles[col] = pd.to_numeric(df_candles[col], errors='coerce')

df_candles['UnixTime'] = pd.to_datetime(df_candles['Time'], format='%Y.%m.%d %H:%M:%S').astype('int64') // 10**9
df_struct['UnixTime'] = pd.to_datetime(df_struct['Time'], format='%Y.%m.%d %H:%M:%S').astype('int64') // 10**9

sub_struct = df_struct[(df_struct['Time'] >= '2026.01.07 00:00:00') & (df_struct['Time'] <= '2026.01.08 08:00:00')]
structures = sub_struct.to_dict('records')
candles = df_candles.to_dict('records')

def lower_bound(target_time):
    lo, hi = 0, len(candles)
    while lo < hi:
        mid = (lo + hi) // 2
        if candles[mid]['UnixTime'] < target_time:
            lo = mid + 1
        else:
            hi = mid
    return lo

def find_peak_valley_formation_time(price, stype, event_time):
    is_high = stype in ('HH', 'LH')
    start_idx = lower_bound(event_time)
    if start_idx < len(candles) and candles[start_idx]['UnixTime'] == event_time:
        val = candles[start_idx]['High'] if is_high else candles[start_idx]['Low']
        if abs(val - price) <= 0.08:
            return event_time
            
    for i in range(start_idx, max(-1, start_idx - 400), -1):
        if i < len(candles):
            val = candles[i]['High'] if is_high else candles[i]['Low']
            if abs(val - price) <= 0.08:
                return candles[i]['UnixTime']
    return event_time

# Playhead at Jan 8 2026 08:00:00
playhead_time = int(pd.to_datetime('2026.01.08 08:00:00', format='%Y.%m.%d %H:%M:%S').timestamp())

lines_to_draw = []
for s in structures:
    stype = str(s['Type']).upper()
    sprice = float(s['Price']) if pd.notnull(s['Price']) else 0
    stime = s['UnixTime']
    
    if stime > playhead_time:
        continue
        
    if stype in ('HH', 'LL', 'LH', 'HL'):
        start_time = find_peak_valley_formation_time(sprice, stype, stime)
        if start_time > playhead_time:
            continue
            
        start_idx = lower_bound(start_time + 1)
        max_idx = min(start_idx + 20, len(candles))
        end_time = playhead_time
        broke = False
        for i in range(start_idx, max_idx):
            c = candles[i]
            if c['UnixTime'] > playhead_time:
                break
            crossed = c['Close'] > sprice if stype in ('HH', 'LH') else c['Close'] < sprice
            if crossed:
                end_time = c['UnixTime']
                broke = True
                break
        if not broke and max_idx > start_idx:
            end_time = min(candles[max_idx - 1]['UnixTime'], playhead_time)
            
        if start_time < end_time:
            lines_to_draw.append({
                'label': f"{stype} [M15] {sprice:.2f}",
                'price': sprice,
                'startTime': start_time,
                'endTime': end_time,
                'type': stype,
                'startTimeStr': str(pd.to_datetime(start_time, unit='s')),
                'endTimeStr': str(pd.to_datetime(end_time, unit='s'))
            })

print("=== RAW LINES JAN 7-8 ===")
for l in lines_to_draw:
    print(f"RAW: {l['label']:16s} | Start: {l['startTimeStr']} | End: {l['endTimeStr']}")

filtered = []
sorted_lines = sorted(lines_to_draw, key=lambda x: x['startTime'])
for line in sorted_lines:
    is_hh = line['label'].startswith('HH') or line['label'].startswith('LH')
    is_ll = line['label'].startswith('LL') or line['label'].startswith('HL')
    
    if is_hh:
        dup = next((ex for ex in filtered if (ex['label'].startswith('HH') or ex['label'].startswith('LH')) and abs(ex['price'] - line['price']) <= 0.08), None)
        if dup:
            continue
            
        overlapping = next((ex for ex in filtered if (ex['label'].startswith('HH') or ex['label'].startswith('LH')) and (line['startTime'] <= ex['endTime'] and line['endTime'] >= ex['startTime'])), None)
        if overlapping:
            if line['price'] <= overlapping['price']:
                continue
            else:
                idx = filtered.index(overlapping)
                filtered[idx] = line
                continue
    elif is_ll:
        dup = next((ex for ex in filtered if (ex['label'].startswith('LL') or ex['label'].startswith('HL')) and abs(ex['price'] - line['price']) <= 0.08), None)
        if dup:
            continue
            
        overlapping = next((ex for ex in filtered if (ex['label'].startswith('LL') or ex['label'].startswith('HL')) and (line['startTime'] <= ex['endTime'] and line['endTime'] >= ex['startTime'])), None)
        if overlapping:
            if line['price'] >= overlapping['price']:
                continue
            else:
                idx = filtered.index(overlapping)
                filtered[idx] = line
                continue
                
    filtered.append(line)

print("\n=== FILTERED LINES JAN 7-8 ===")
for f in filtered:
    print(f"FILTERED: {f['label']:16s} | Start: {f['startTimeStr']} | End: {f['endTimeStr']}")
