"""Normalized market features for historical structure patterns."""

from typing import Any, Optional

import pandas as pd


MARKET_FEATURE_FIELDS = (
    "atr",
    "body_ratio",
    "range_atr_ratio",
    "ema200_h1_distance_scaled",
    "ema200_h4_distance_scaled",
    "spread_atr_ratio",
    "volume_ratio",
    "trigger_distance_atr",
)


def build_market_feature_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize columns and precompute rolling ATR and volume context."""
    if data.empty:
        return data.copy()

    frame = data.rename(columns={column: column.lower() for column in data.columns}).copy()
    frame["time"] = pd.to_datetime(frame["time"])
    frame = frame.sort_values("time").drop_duplicates("time", keep="last")

    required_ohlc = {"high", "low", "close"}
    if required_ohlc.issubset(frame.columns):
        previous_close = frame["close"].shift(1)
        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - previous_close).abs(),
                (frame["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        frame["atr_14"] = true_range.rolling(14, min_periods=14).mean()

    if "volume" in frame.columns:
        frame["volume_sma_20"] = frame["volume"].rolling(20, min_periods=20).mean()

    return frame.set_index("time", drop=False)


def _latest_row(frame: pd.DataFrame, event_time: pd.Timestamp) -> Optional[pd.Series]:
    if frame.empty:
        return None
    position = frame.index.searchsorted(event_time, side="right") - 1
    return None if position < 0 else frame.iloc[position]


def _number(value: Any) -> Optional[float]:
    return None if value is None or pd.isna(value) else float(value)


def extract_historical_market_features(
    *,
    event_time: pd.Timestamp,
    structure_price: float,
    entry_price: Optional[float],
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
) -> dict[str, Optional[float]]:
    """Extract nullable normalized features at one historical event time."""
    event_time = pd.Timestamp(event_time)
    m15_row = _latest_row(m15, event_time)
    h1_row = _latest_row(h1, event_time)
    h4_row = _latest_row(h4, event_time)

    features = dict.fromkeys(MARKET_FEATURE_FIELDS)
    if m15_row is None:
        return features

    open_price = _number(m15_row.get("open"))
    high_price = _number(m15_row.get("high"))
    low_price = _number(m15_row.get("low"))
    close_price = _number(m15_row.get("close"))
    atr = _number(m15_row.get("atr_14"))
    candle_range = (
        high_price - low_price
        if high_price is not None and low_price is not None and high_price > low_price
        else None
    )

    features["atr"] = atr
    if candle_range is not None and open_price is not None and close_price is not None:
        features["body_ratio"] = abs(close_price - open_price) / candle_range

    if atr is not None and atr > 0:
        if candle_range is not None:
            features["range_atr_ratio"] = candle_range / atr

        h1_ema = _number(h1_row.get("ema200")) if h1_row is not None else None
        h4_ema = _number(h4_row.get("ema200")) if h4_row is not None else None
        if h1_ema is not None:
            features["ema200_h1_distance_scaled"] = (structure_price - h1_ema) / atr
        if h4_ema is not None:
            features["ema200_h4_distance_scaled"] = (structure_price - h4_ema) / atr

        spread_points = _number(m15_row.get("spread"))
        if spread_points is not None:
            features["spread_atr_ratio"] = (spread_points / 100.0) / atr

        if entry_price is not None and not pd.isna(entry_price):
            features["trigger_distance_atr"] = abs(float(entry_price) - structure_price) / atr

    volume = _number(m15_row.get("volume"))
    volume_average = _number(m15_row.get("volume_sma_20"))
    if volume is not None and volume_average is not None and volume_average > 0:
        features["volume_ratio"] = volume / volume_average

    return features