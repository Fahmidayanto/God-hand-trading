import pandas as pd
import datetime

df_struct = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2020-12-30.csv', skiprows=1)
df_candles = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv')

print("--- Structures around 13-16 Jan 2020 ---")
df_sub = df_struct[df_struct['Time'].astype(str).str.contains('2020.01.13|2020.01.14|2020.01.15|2020.01.16')]
print(df_sub[['Type', 'Direction/Action', 'Price', 'Time', 'Status', 'PreviousPrice', 'PreviousTime']].to_string())

# Find the CHoCH Bullish event
choch_event = df_struct[(df_struct['Type'] == 'CHoCH') & (df_struct['Price'] == 1556.09)]
print("\n--- CHoCH Event ---")
print(choch_event.to_string())

# What HH/LH swing high exists with price = 1556.09?
hh_events = df_struct[(df_struct['Type'].isin(['HH', 'LH'])) & (abs(df_struct['Price'] - 1556.09) <= 0.08)]
print("\n--- HH/LH Events matching 1556.09 ---")
print(hh_events.to_string())
