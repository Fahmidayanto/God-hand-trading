from types import SimpleNamespace

import pandas as pd

from valuecell.agents.ml_prediction_agent import MLPredictionAgent


def test_v5_nullable_simulation_values_use_numeric_defaults():
    agent = MLPredictionAgent.__new__(MLPredictionAgent)
    agent.feature_engineer = SimpleNamespace(
        extract_features=lambda **_: {"atr_14": 5.0, "body_ratio": 0.5}
    )
    current_time = pd.Timestamp("2026-07-13 02:00:00")
    market_data = {
        "current_bar": {"time": current_time, "close": 3350.0},
        "m15_history": pd.DataFrame(
            [{"time": current_time, "high": 3351.0, "low": 3349.0,
              "close": 3350.0, "spread": None}]
        ),
        "spread": None,
        "init_risk_points": None,
        "init_reward_points": None,
        "session": "Asia",
    }

    features = agent._extract_v5_features(market_data, 3350.0, "BUY")

    assert features["spread_pct"] == (0.15 / 3350.0) * 100.0
    assert features["spread_to_atr_ratio"] == 0.15 / 5.0
    assert features["init_risk_points"] == 300.0
    assert features["init_risk_pct"] == (300.0 / 3350.0) * 100.0
