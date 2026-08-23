import pandas as pd
import glob

files = glob.glob('Backtest_result/*LLHH*.csv') + glob.glob('Other/Backtest_result_all/*/*LLHH*.csv')
print("Searching for CHoCH at ~1732.84 in all structure files:")
for f in files:
    try:
        df = pd.read_csv(f, skiprows=1)
        # Match CHoCH
        sub = df[(df['Type'].str.contains('CHoCH|CHOCH', na=False)) & (abs(df['Price'] - 1732.84) < 0.1)]
        if len(sub) > 0:
            print(f"\nFound in {f}:")
            print(sub[['Type', 'Direction/Action', 'Price', 'Time', 'Status']])
    except Exception as e:
        pass
