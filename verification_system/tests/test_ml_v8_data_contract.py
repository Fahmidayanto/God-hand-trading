"""Data-contract and point-in-time tests for the v8 ML pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "ValueCell_MT5" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from train_ml_prediction_v5_unconstrained import (  # noqa: E402
    build_feature_matrix_v5,
    completed_rows_at_or_before,
    point_in_time_session_features,
)


def _market_frame(freq: str, periods: int = 8) -> pd.DataFrame:
    times = pd.date_range("2024-01-02 08:00:00", periods=periods, freq=freq)
    return pd.DataFrame({
        "time": times,
        "open": range(periods),
        "high": [value + 2 for value in range(periods)],
        "low": [value - 1 for value in range(periods)],
        "close": [value + 1 for value in range(periods)],
        "volume": [100] * periods,
    })


def test_completed_rows_excludes_open_h1_and_h4_candles() -> None:
    prediction_time = pd.Timestamp("2024-01-02 10:15:00")

    h1 = completed_rows_at_or_before(_market_frame("1h"), prediction_time, "1h", 20)
    h4 = completed_rows_at_or_before(_market_frame("4h"), prediction_time, "4h", 20)

    assert h1.iloc[-1]["time"] == pd.Timestamp("2024-01-02 09:00:00")
    assert h4.empty


def test_active_session_statistics_use_only_observed_m15_bars() -> None:
    sessions = pd.DataFrame({
        "start_time": [pd.Timestamp("2024-01-02 10:00:00")],
        "end_time": [pd.Timestamp("2024-01-02 14:00:00")],
        "Session": ["London"],
        "IsDST": ["NO"],
        "HighPrice": [2200.0],
        "LowPrice": [1900.0],
        "RangePoints": [30000.0],
    })
    m15 = pd.DataFrame({
        "time": [pd.Timestamp("2024-01-02 10:00:00"), pd.Timestamp("2024-01-02 10:15:00")],
        "open": [9.0, 10.0],
        "high": [11.0, 100.0],
        "low": [6.0, 1.0],
        "close": [10.0, 50.0],
        "volume": [100, 100],
    })
    prediction_time = pd.Timestamp("2024-01-02 10:15:00")

    features = point_in_time_session_features(
        sessions=sessions,
        m15=m15,
        when=prediction_time,
        entry_price=10.0,
        atr=2.0,
    )

    assert features["session_range_points"] == 500.0
    assert features["distance_to_session_high_atr"] == 0.5
    assert features["distance_to_session_low_atr"] == 2.0


def test_feature_matrix_excludes_targets_and_realized_outcomes() -> None:
    dataset = pd.DataFrame({
        "signal": ["BUY", "SELL"],
        "session_name": ["London", "NewYork"],
        "session_is_dst": ["NO", "NO"],
        "session_zone_name": ["London", "NewYork"],
        "session_zone_is_dst": ["NO", "NO"],
        "entry_structure": ["BoS", "CHoCH"],
        "safe_feature": [1.0, 2.0],
        "mfe_target": [100.0, 200.0],
        "mae_target": [50.0, 75.0],
        "mfe_target_norm": [90.0, 180.0],
        "mae_target_norm": [45.0, 70.0],
        "actual_net_profit": [10.0, -5.0],
    })

    model_df, _, _ = build_feature_matrix_v5(dataset)

    forbidden = {
        "mfe_target",
        "mae_target",
        "mfe_target_norm",
        "mae_target_norm",
        "actual_net_profit",
    }
    assert forbidden.isdisjoint(model_df.columns)