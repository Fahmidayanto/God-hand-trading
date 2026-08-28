import pandas as pd
df = pd.read_csv('ValueCell_MT5/python/valuecell/models/saved/filter_latest/dataset_v9_unconstrained.csv')
print(df['ea_status'].value_counts(dropna=False))
print("\nIf actual_net_profit != 0:")
taken = df[df['actual_net_profit'] != 0]
print(f"Total taken trades with non-zero profit: {len(taken)}")
print(taken['ea_status'].value_counts(dropna=False))
