"""
Build Dataset v9 (News-Aware Unconstrained Dataset) - Vectorized Fast Version.
Integrates dataset_v5_unconstrained.csv (1942 samples) with 861 LanceDB economic calendar events.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from valuecell.knowledge.lance_db import LanceDBManager


def main() -> int:
    models_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    src_dataset_path = models_dir / "dataset_v5_unconstrained.csv"
    out_dataset_path = models_dir / "dataset_v9_unconstrained.csv"

    logger.info("Loading baseline dataset from: {}", src_dataset_path)
    df = pd.read_csv(src_dataset_path)
    logger.info("Loaded {} samples ({} - {})", len(df), df["year"].min(), df["year"].max())

    logger.info("Connecting to LanceDB to fetch economic events...")
    db = LanceDBManager()
    tbl = db.db.open_table("economic_calendar_events")
    events_df = tbl.search().to_pandas()
    logger.info("Loaded {} economic calendar events from LanceDB", len(events_df))

    # Parse timestamps to numpy datetime64
    event_times = pd.to_datetime(events_df["timestamp"], utc=True).values
    event_starts = pd.to_datetime(events_df["blackout_start"], utc=True).values
    event_ends = pd.to_datetime(events_df["blackout_end"], utc=True).values

    fomc_mask = events_df["category"] == "CENTRAL_BANK"
    fomc_times = pd.to_datetime(events_df.loc[fomc_mask, "timestamp"], utc=True).values
    fomc_dates = pd.to_datetime(events_df.loc[fomc_mask, "timestamp"], utc=True).dt.date.values

    entry_times = pd.to_datetime(df["entry_time"], utc=True).values
    entry_dates = pd.to_datetime(df["entry_time"], utc=True).dt.date.values

    n_samples = len(df)
    is_news_blackout = np.zeros(n_samples, dtype=np.float32)
    minutes_to_next_news = np.full(n_samples, 1440.0, dtype=np.float32)
    minutes_since_last_news = np.full(n_samples, 1440.0, dtype=np.float32)
    is_fomc_day = np.zeros(n_samples, dtype=np.float32)
    hours_to_next_fomc = np.full(n_samples, 168.0, dtype=np.float32)

    logger.info("Vectorized computation of news features for all samples...")

    # Sort event times for fast binary search
    sort_idx = np.argsort(event_times)
    event_times_sorted = event_times[sort_idx]
    event_starts_sorted = event_starts[sort_idx]
    event_ends_sorted = event_ends[sort_idx]

    fomc_sort_idx = np.argsort(fomc_times)
    fomc_times_sorted = fomc_times[fomc_sort_idx]

    for i in range(n_samples):
        e_t = entry_times[i]
        e_d = entry_dates[i]

        # 1. Blackout Check: binary search candidate events
        idx_cand = np.searchsorted(event_times_sorted, e_t)
        # Check window of +-10 events around candidate
        start_check = max(0, idx_cand - 5)
        end_check = min(len(event_times_sorted), idx_cand + 6)
        for k in range(start_check, end_check):
            if event_starts_sorted[k] <= e_t <= event_ends_sorted[k]:
                is_news_blackout[i] = 1.0
                break

        # 2. Minutes to next news
        if idx_cand < len(event_times_sorted):
            diff_sec = (event_times_sorted[idx_cand] - e_t) / np.timedelta64(1, "s")
            if diff_sec > 0:
                minutes_to_next_news[i] = min(1440.0, float(diff_sec / 60.0))

        # 3. Minutes since last news
        if idx_cand > 0:
            diff_prev = (e_t - event_times_sorted[idx_cand - 1]) / np.timedelta64(1, "s")
            if diff_prev > 0:
                minutes_since_last_news[i] = min(1440.0, float(diff_prev / 60.0))

        # 4. FOMC Day
        if e_d in fomc_dates:
            is_fomc_day[i] = 1.0

        # 5. Hours to next FOMC
        f_idx = np.searchsorted(fomc_times_sorted, e_t)
        if f_idx < len(fomc_times_sorted):
            f_diff_sec = (fomc_times_sorted[f_idx] - e_t) / np.timedelta64(1, "s")
            if f_diff_sec > 0:
                hours_to_next_fomc[i] = min(168.0, float(f_diff_sec / 3600.0))

    # Attach features
    df["is_news_blackout"] = is_news_blackout
    df["minutes_to_next_news"] = minutes_to_next_news
    df["minutes_since_last_news"] = minutes_since_last_news
    df["is_fomc_day"] = is_fomc_day
    df["hours_to_next_fomc"] = hours_to_next_fomc

    logger.info("News Features Summary:")
    logger.info("Blackout Entries Count: {} ({}%)", int(df["is_news_blackout"].sum()), round(df["is_news_blackout"].mean() * 100, 2))
    logger.info("FOMC Day Entries Count: {}", int(df["is_fomc_day"].sum()))

    df.to_csv(out_dataset_path, index=False)
    logger.info("✅ Dataset v9 saved to: {} (Total Columns: {})", out_dataset_path, len(df.columns))

    return 0


if __name__ == "__main__":
    sys.exit(main())
