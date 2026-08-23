import pandas as pd

df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv').set_index('Time')
df_struct = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2020-12-30.csv', skiprows=1)

event_time = '2020.01.16 02:00:00'
level_price = 1556.09
is_bullish = True

matches = df_struct[(df_struct['Type'].isin(['HH', 'LH'])) & 
                    (abs(df_struct['Price'] - level_price) <= 0.08) & 
                    (df_struct['Time'] < event_time)]

print("Checking which structure event timestamp has a matching candle peak:")
for idx, s in matches.iterrows():
    s_time = s['Time']
    if s_time in df_candles.index:
        c = df_candles.loc[s_time]
        diff_high = abs(c['High'] - level_price)
        print(f"Structure Event Time: {s_time}, Candle High: {c['High']}, Diff: {diff_high:.4f}, Valid Peak: {diff_high <= 0.08}")
    else:
        print(f"Structure Event Time: {s_time} not in candles")
