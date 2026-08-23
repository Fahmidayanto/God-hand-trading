import pandas as pd

df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv')
df_struct = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2020-12-30.csv', skiprows=1)

# Event: CHoCH Bullish at 1556.09 on 2020.01.16 02:00:00
event_time = '2020.01.16 02:00:00'
level_price = 1556.09
is_bullish = True # breaking a swing high

# Method A: Search in df_struct with item.time > matchTime
matches = df_struct[(df_struct['Type'].isin(['HH', 'LH'])) & 
                    (abs(df_struct['Price'] - level_price) <= 0.08) & 
                    (df_struct['Time'] < event_time)]
print("Structure event matches:")
print(matches[['Type', 'Price', 'Time', 'Status']])

# Method B: Search in candles backwards from event_time to find the candle that formed the peak (high = 1556.09)
candles_before = df_candles[df_candles['Time'] < event_time]
# Search backwards
found_candle = None
for idx in range(len(candles_before) - 1, -1, -1):
    c = candles_before.iloc[idx]
    if is_bullish:
        if abs(c['High'] - level_price) <= 0.08:
            found_candle = c
            break
    else:
        if abs(c['Low'] - level_price) <= 0.08:
            found_candle = c
            break

print("\nMethod B (Candle Search Backwards):")
if found_candle is not None:
    print(f"Exact formation candle found: Time={found_candle['Time']}, High={found_candle['High']}, Low={found_candle['Low']}")
else:
    print("Not found in candles")
