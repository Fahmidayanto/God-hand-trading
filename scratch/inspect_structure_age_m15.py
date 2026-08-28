import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Load dataset
df = pd.read_csv('ValueCell_MT5/python/valuecell/models/saved/filter_latest/dataset_v9_unconstrained.csv')

# Let's inspect the actual trades in the dataset
print(f"Total dataset samples: {len(df)}")
print("Sample columns:", [c for c in df.columns if 'time' in c or 'bos' in c or 'distance' in c or 'age' in c or 'net_profit' in c])

# Let's check if we can inspect the raw MarketData M15 and SessionZone/Trades
# In dataset_v9, let's see how distance_to_last_hh_pips and distance_to_last_ll_pips relate to MFE/MAE
# And let's analyze a sample MarketData M15 file (e.g. 2024 or 2025 or 2026) to see actual swing age patterns
m15_sample = pd.read_csv('Backtest_result/MarketData_XAUUSD_M15_2024-12-30.csv')
print(f"\n2024 M15 bars: {len(m15_sample)}")
print("M15 sample columns:", m15_sample.columns.tolist())
