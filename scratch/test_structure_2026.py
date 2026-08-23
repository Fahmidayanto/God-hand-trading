import pandas as pd

df = pd.read_csv('Backtest_result/LLHHBOSData_XAUUSD_2026-08-21.csv', skiprows=1)
sub = df.iloc[14:26]
print("--- Structures 2026.01.07 - 2026.01.08 ---")
print(sub[['Type', 'Direction/Action', 'Price', 'Time', 'Status', 'PreviousPrice']])
