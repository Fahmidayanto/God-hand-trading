import pandas as pd

df_m15 = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv')

# Event: CHoCH Bullish at 1732.84 on 2020.06.18 12:00:00
# Entry Time: 2020.06.18 12:15:00
# Let's find candle indices around 2020.06.18 12:15:00

idx_1215 = df_m15[df_m15['Time'] == '2020.06.18 12:15:00'].index[0]
c_1215 = df_m15.iloc[idx_1215]     # Index m15Index (entry bar)
c_1200 = df_m15.iloc[idx_1215 - 1] # Index m15Index - 1 (m15Candle: bar[1] newly closed bar with CHoCH breakout)
c_1145 = df_m15.iloc[idx_1215 - 2] # Index m15Index - 2 (previousCandle: bar[2] previous closed bar)

print(f"Bar[2] (11:45): Time={c_1145['Time']}, Close={c_1145['Close']}, EMA200={c_1145['EMA200']:.5f}")
print(f"Bar[1] (12:00): Time={c_1200['Time']}, Close={c_1200['Close']}, EMA200={c_1200['EMA200']:.5f}")
print(f"Bar[0] (12:15): Time={c_1215['Time']}, Open={c_1215['Open']}, Close={c_1215['Close']}, EMA200={c_1215['EMA200']:.5f}")

slope = c_1200['EMA200'] - c_1145['EMA200']
print(f"\nSlope Bar[1] vs Bar[2] = {c_1200['EMA200']:.5f} - {c_1145['EMA200']:.5f} = {slope:.5f}")
print(f"Is Slope Trending UP? (slope > 0): {slope > 0}")
