import pandas as pd

df_m15 = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv')
df_h1 = pd.read_csv('Backtest_result/MarketData_XAUUSD_H1_2020-12-30.csv')
df_h4 = pd.read_csv('Backtest_result/MarketData_XAUUSD_H4_2020-12-30.csv')

# Find candles around 2020.06.18 12:00:00 - 12:15:00
print("--- M15 Candles around 2020.06.18 12:00 ---")
m15_sub = df_m15[(df_m15['Time'] >= '2020.06.18 11:00:00') & (df_m15['Time'] <= '2020.06.18 13:00:00')]
print(m15_sub[['Time', 'Open', 'High', 'Low', 'Close', 'EMA200']].to_string())

print("\n--- H1 Candles around 2020.06.18 12:00 ---")
h1_sub = df_h1[(df_h1['Time'] >= '2020.06.18 08:00:00') & (df_h1['Time'] <= '2020.06.18 15:00:00')]
print(h1_sub[['Time', 'Open', 'High', 'Low', 'Close', 'EMA200']].to_string())

print("\n--- H4 Candles around 2020.06.18 12:00 ---")
h4_sub = df_h4[(df_h4['Time'] >= '2020.06.17 00:00:00') & (df_h4['Time'] <= '2020.06.19 00:00:00')]
print(h4_sub[['Time', 'Open', 'High', 'Low', 'Close', 'EMA200']].to_string())
