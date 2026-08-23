import pandas as pd
import datetime

df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv').set_index('Time')
df_struct = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2020-12-30.csv', skiprows=1)

event_time = '2020.01.16 02:00:00'
level_price = 1556.09
is_bullish = True
target_types = ['HH', 'LH']

best_time = None
has_candle_match = False

matches = df_struct[(df_struct['Type'].isin(target_types)) & 
                    (abs(df_struct['Price'] - level_price) <= 0.08) & 
                    (df_struct['Time'] < event_time)]

for idx, item in matches.iterrows():
    item_time = item['Time']
    if item_time in df_candles.index:
        c = df_candles.loc[item_time]
        is_exact_peak = abs(c['High'] - level_price) <= 0.08 if is_bullish else abs(c['Low'] - level_price) <= 0.08
        if is_exact_peak:
            if not has_candle_match or (best_time is not None and item_time > best_time):
                best_time = item_time
                has_candle_match = True
        elif not has_candle_match:
            if best_time is None or item_time > best_time:
                best_time = item_time

print(f"Result formation time: {best_time}")
print(f"Has candle match: {has_candle_match}")
