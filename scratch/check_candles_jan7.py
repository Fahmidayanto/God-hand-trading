import pandas as pd

df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2026-08-21.csv', header=None)
df_candles.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'TickVol', 'Spread', 'EMA200']

c_1715 = df_candles[df_candles['Time'] == '2026.01.07 17:15:00']
print("Candle at 17:15:")
print(c_1715)

c_0115 = df_candles[df_candles['Time'] == '2026.01.07 01:15:00']
print("\nCandle at 01:15 (Real Peak 4500.42):")
print(c_0115)

c_1845 = df_candles[df_candles['Time'] == '2026.01.07 18:45:00']
print("\nCandle at 18:45 (Real Peak 4468.29):")
print(c_1845)

c_0215 = df_candles[df_candles['Time'] == '2026.01.08 02:15:00']
print("\nCandle at 02:15 (Minor Peak 4466.37):")
print(c_0215)
