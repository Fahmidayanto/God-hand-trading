import pandas as pd
df = pd.read_csv('ValueCell_MT5/python/valuecell/models/saved/filter_latest/dataset_v9_unconstrained.csv')
print("Columns:", df.columns.tolist())
if 'actual_outcome' in df.columns:
    print("Outcome values:", df['actual_outcome'].value_counts())
if 'actual_net_profit' in df.columns:
    print("Actual net profit stats:", df['actual_net_profit'].describe())
