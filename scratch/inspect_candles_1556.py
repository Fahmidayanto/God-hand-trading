import pandas as pd

df_m15 = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv')
c1 = df_m15[df_m15['Time'] == '2020.01.13 15:45:00']
c2 = df_m15[df_m15['Time'] == '2020.01.14 03:15:00']
print("Candle 2020.01.13 15:45:")
print(c1.to_string())
print("\nCandle 2020.01.14 03:15:")
print(c2.to_string())

# Also let's check candles between 13 Jan 15:00 and 14 Jan 05:00
print("\nCandles around 13 Jan 15:00 - 14 Jan 05:00:")
sub = df_m15[(df_m15['Time'] >= '2020.01.13 15:00:00') & (df_m15['Time'] <= '2020.01.14 05:00:00')]
print(sub[['Time', 'Open', 'High', 'Low', 'Close']].to_string())
