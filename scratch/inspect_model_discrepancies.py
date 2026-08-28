import sys
import pandas as pd
import numpy as np
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
repo_root = Path(__file__).resolve().parents[1]
saved_dir = repo_root / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest"

for v in ["v5", "v9", "v11"]:
    df = pd.read_csv(saved_dir / f"dataset_{v}_unconstrained.csv")
    print(f"Dataset {v}: total={len(df)}")
    print(df["ea_status"].value_counts(dropna=False))
    print("-" * 50)
