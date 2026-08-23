import pandas as pd

df_struct = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2026-08-21.csv')
# Columns might be Time, Open, High, Low, Close, etc.
# let's normalize column names
df_candles.columns = [c.strip() for c in df_candles.columns]
for col in ['Open', 'High', 'Low', 'Close']:
    df_candles[col] = pd.to_numeric(df_candles[col], errors='coerce')

sub_struct = df_struct[(df_struct['Time'] >= '2026.01.07 00:00:00') & (df_struct['Time'] <= '2026.01.08 12:00:00')]
print("=== Structure Events Jan 7-8 ===")
for idx, s in sub_struct.iterrows():
    print(f"{s['Type']:5s} | {str(s['Direction/Action']):10s} | {s['Price']} | {s['Time']} | Status: {s['Status']} | Prev: {s['PreviousPrice']}")

def find_formation_time(price, stype, event_time):
    is_high = stype in ('HH', 'LH')
    candles_before = df_candles[df_candles['Time'] <= event_time]
    for i in range(len(candles_before)-1, -1, -1):
        row = candles_before.iloc[i]
        val = float(row['High']) if is_high else float(row['Low'])
        if abs(val - price) <= 0.08:
            return row['Time']
    return event_time

print("\n=== Verified Formation Times ===")
for idx, s in sub_struct.iterrows():
    stype = str(s['Type']).upper()
    if stype in ('HH', 'LL', 'LH', 'HL'):
        price = float(s['Price'])
        evt_time = str(s['Time'])
        form_time = find_formation_time(price, stype, evt_time)
        print(f"Event: {stype:2s} {price:7.2f} at {evt_time} -> Real Peak/Valley Time: {form_time}")
