import pandas as pd
import pytest

from valuecell.knowledge.historical_market_features import (
    build_market_feature_frame,
    extract_historical_market_features,
)


def test_extract_historical_market_features_uses_completed_market_context():
    times = pd.date_range("2026-08-27 06:00:00", periods=20, freq="15min")
    m15 = pd.DataFrame({
        "Time": times,
        "Open": [100.0] * 20,
        "High": [106.0] * 20,
        "Low": [96.0] * 20,
        "Close": [104.0] * 20,
        "Volume": list(range(100, 120)),
        "Spread": [20] * 20,
        "EMA200": [98.0] * 20,
    })
    h1 = pd.DataFrame({
        "Time": [pd.Timestamp("2026-08-27 10:00:00")],
        "EMA200": [96.0],
    })
    h4 = pd.DataFrame({
        "Time": [pd.Timestamp("2026-08-27 08:00:00")],
        "EMA200": [92.0],
    })

    features = extract_historical_market_features(
        event_time=pd.Timestamp("2026-08-27 10:45:00"),
        structure_price=104.0,
        entry_price=105.0,
        m15=build_market_feature_frame(m15),
        h1=build_market_feature_frame(h1),
        h4=build_market_feature_frame(h4),
    )

    assert features["atr"] == pytest.approx(10.0)
    assert features["body_ratio"] == pytest.approx(0.4)
    assert features["range_atr_ratio"] == pytest.approx(1.0)
    assert features["ema200_h1_distance_scaled"] == pytest.approx(0.8)
    assert features["ema200_h4_distance_scaled"] == pytest.approx(1.2)
    assert features["spread_atr_ratio"] == pytest.approx(0.02)
    assert features["volume_ratio"] == pytest.approx(119.0 / 109.5)
    assert features["trigger_distance_atr"] == pytest.approx(0.1)


def test_extract_historical_market_features_keeps_unavailable_values_nullable():
    m15 = pd.DataFrame({
        "Time": [pd.Timestamp("2026-08-27 10:45:00")],
        "Open": [100.0],
        "High": [101.0],
        "Low": [99.0],
        "Close": [100.5],
        "Volume": [100],
        "Spread": [20],
        "EMA200": [98.0],
    })

    features = extract_historical_market_features(
        event_time=pd.Timestamp("2026-08-27 10:45:00"),
        structure_price=100.5,
        entry_price=None,
        m15=build_market_feature_frame(m15),
        h1=pd.DataFrame(),
        h4=pd.DataFrame(),
    )

    assert features == {
        "atr": None,
        "body_ratio": pytest.approx(0.25),
        "range_atr_ratio": None,
        "ema200_h1_distance_scaled": None,
        "ema200_h4_distance_scaled": None,
        "spread_atr_ratio": None,
        "volume_ratio": None,
        "trigger_distance_atr": None,
    }