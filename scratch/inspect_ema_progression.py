import pandas as pd

df_m15 = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2020-12-30.csv')
sub = df_m15[(df_m15['Time'] >= '2020.06.18 06:00:00') & (df_m15['Time'] <= '2020.06.18 13:00:00')].copy()
sub['EMA_Diff'] = sub['EMA200'].diff()
sub['Slope_Direction'] = sub['EMA_Diff'].apply(lambda x: 'UP (+)' if x > 0 else ('DOWN (-)' if x < 0 else 'FLAT (0)'))
print(sub[['Time', 'Open', 'High', 'Low', 'Close', 'EMA200', 'EMA_Diff', 'Slope_Direction']].to_string())
