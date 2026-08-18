"""
Regime Detector - Trending / Ranging / Transitioning Classifier

Menggunakan ADX + Bollinger Band width + ATR percentile untuk klasifikasi
market regime. Penting karena SL/TP placement strategy BERBEDA per regime:

- Trending (strong): SL mengikuti trend, TP bisa lebih jauh (trail)
- Ranging: SL ketat di edge, TP di opposite edge (mean reversion)
- Transitioning: avoid atau SL sangat ketat (volatility burst)

Multi-timeframe confluence: regime H1+H4 harus align → confidence lebih tinggi.

Ponytail: stateless, time-anchored, pure pandas.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

import pandas as pd
from loguru import logger

# Suppress pandas UserWarning: "Discarding nonzero nanoseconds in conversion"
warnings.filterwarnings("ignore", message="Discarding nonzero nanoseconds in conversion")


# ── Constants ───────────────────────────────────────────────────────────────

DEFAULT_ADX_PERIOD = 14
DEFAULT_BB_PERIOD = 20
DEFAULT_BB_STD = 2.0
DEFAULT_ATR_PERIOD = 14
DEFAULT_ATR_LOOKBACK_PCT = 100   # Untuk percentile rank

# ADX threshold
ADX_STRONG_TREND = 25.0
ADX_WEAK_TREND = 20.0


# ── Enums & dataclasses ─────────────────────────────────────────────────────

class Regime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    TRANSITIONING = "transitioning"   # Volatility expanding, ADX rendah
    UNKNOWN = "unknown"


class VolatilityState(str, Enum):
    EXPANDING = "expanding"
    CONTRACTING = "contracting"
    NORMAL = "normal"
    UNKNOWN = "unknown"


@dataclass
class RegimeSnapshot:
    """Regime snapshot di satu timestamp."""
    as_of: datetime
    timeframe: str
    regime: Regime
    volatility: VolatilityState
    adx: float
    plus_di: float
    minus_di: float
    bb_width_pct: float        # BB width sebagai % dari mid price
    bb_width_percentile: float  # Percentile rank dalam lookback
    atr: float
    atr_percentile: float       # Percentile rank dalam lookback
    confidence: float           # 0-1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["regime"] = self.regime.value
        d["volatility"] = self.volatility.value
        return d


@dataclass
class MultiTimeframeRegime:
    """Regime untuk multiple timeframe (confluence)."""
    as_of: datetime
    snapshots: Dict[str, RegimeSnapshot]  # timeframe → snapshot
    overall_regime: Regime
    confluence: bool  # True jika H1 & H4 align
    recommendation: str  # Plain text untuk LLM context

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "snapshots": {tf: s.to_dict() for tf, s in self.snapshots.items()},
            "overall_regime": self.overall_regime.value,
            "confluence": self.confluence,
            "recommendation": self.recommendation,
        }


# ── ADX calculation ─────────────────────────────────────────────────────────

def _adx(
    df: pd.DataFrame,
    period: int = DEFAULT_ADX_PERIOD,
) -> tuple:
    """
    Hitung ADX, +DI, -DI standard.

    Returns: (adx_series, plus_di_series, minus_di_series)
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    # True Range
    tr = pd.concat(
        [
            (high - low),
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # +DM, -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = pd.Series(
        [up if (up > down and up > 0) else 0.0 for up, down in zip(up_move, down_move)],
        index=df.index,
    )
    minus_dm = pd.Series(
        [down if (down > up and down > 0) else 0.0 for up, down in zip(up_move, down_move)],
        index=df.index,
    )

    # Smoothed (Wilder)
    atr_smoothed = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_dm_smoothed = plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    minus_dm_smoothed = minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * plus_dm_smoothed / atr_smoothed
    minus_di = 100 * minus_dm_smoothed / atr_smoothed

    # ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    return adx, plus_di, minus_di


# ── Bollinger Band width ────────────────────────────────────────────────────

def _bb_width(df: pd.DataFrame, period: int = DEFAULT_BB_PERIOD, std: float = DEFAULT_BB_STD) -> pd.Series:
    """BB width = (upper - lower) / mid * 100."""
    close = df["close"].astype(float)
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std()
    upper = mid + std * sd
    lower = mid - std * sd
    return (upper - lower) / mid * 100


# ── ATR with percentile ─────────────────────────────────────────────────────

def _atr_series(df: pd.DataFrame, period: int = DEFAULT_ATR_PERIOD) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    tr = pd.concat(
        [
            (high - low),
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def _percentile_rank(series: pd.Series, lookback: int) -> float:
    """Percentile rank nilai terakhir dalam lookback window."""
    if len(series) < lookback:
        return 50.0
    window = series.iloc[-lookback:].dropna()
    if len(window) < 2:
        return 50.0
    current = window.iloc[-1]
    rank = (window < current).sum() / (len(window) - 1) * 100
    return float(rank)


# ── Core: classify regime per timeframe ─────────────────────────────────────

def classify_regime(
    df: pd.DataFrame,
    as_of_idx: Optional[int] = None,
    timeframe: str = "M15",
) -> RegimeSnapshot:
    """
    Klasifikasi regime time-anchored di as_of_idx.

    Returns RegimeSnapshot dengan regime + volatility state.
    """
    if df is None or len(df) < 50:
        logger.warning("Insufficient data for regime classification")
        return RegimeSnapshot(
            as_of=datetime.utcnow(),
            timeframe=timeframe,
            regime=Regime.UNKNOWN,
            volatility=VolatilityState.UNKNOWN,
            adx=0.0,
            plus_di=0.0,
            minus_di=0.0,
            bb_width_pct=0.0,
            bb_width_percentile=50.0,
            atr=0.0,
            atr_percentile=50.0,
            confidence=0.0,
        )

    if as_of_idx is None:
        as_of_idx = len(df) - 1

    as_of_time = pd.Timestamp(df["time"].iloc[as_of_idx])
    df_slice = df.iloc[: as_of_idx + 1]

    # Hitung indikator
    adx_s, plus_di_s, minus_di_s = _adx(df_slice)
    bb_w_s = _bb_width(df_slice)
    atr_s = _atr_series(df_slice)

    adx = float(adx_s.iloc[-1]) if not pd.isna(adx_s.iloc[-1]) else 0.0
    plus_di = float(plus_di_s.iloc[-1]) if not pd.isna(plus_di_s.iloc[-1]) else 0.0
    minus_di = float(minus_di_s.iloc[-1]) if not pd.isna(minus_di_s.iloc[-1]) else 0.0
    bb_width_pct = float(bb_w_s.iloc[-1]) if not pd.isna(bb_w_s.iloc[-1]) else 0.0
    atr = float(atr_s.iloc[-1]) if not pd.isna(atr_s.iloc[-1]) else 0.0

    bb_width_percentile = _percentile_rank(bb_w_s, DEFAULT_ATR_LOOKBACK_PCT)
    atr_percentile = _percentile_rank(atr_s, DEFAULT_ATR_LOOKBACK_PCT)

    # ── Regime classification ──
    regime = Regime.UNKNOWN
    confidence = 0.0

    if adx >= ADX_STRONG_TREND:
        if plus_di > minus_di:
            regime = Regime.TRENDING_UP
        else:
            regime = Regime.TRENDING_DOWN
        confidence = min(1.0, (adx - ADX_STRONG_TREND) / 20.0 + 0.7)
    elif adx >= ADX_WEAK_TREND:
        # Weak trend, butuh konfirmasi
        if plus_di > minus_di + 5:
            regime = Regime.TRENDING_UP
        elif minus_di > plus_di + 5:
            regime = Regime.TRENDING_DOWN
        else:
            regime = Regime.RANGING
        confidence = 0.5
    else:
        # ADX < 20 → ranging atau transitioning
        if bb_width_percentile > 70:
            # BB lebar tapi ADX rendah = transitioning (consolidation → expansion)
            regime = Regime.TRANSITIONING
            confidence = 0.6
        else:
            regime = Regime.RANGING
            confidence = 0.7

    # ── Volatility classification ──
    volatility = VolatilityState.UNKNOWN
    if atr_percentile > 75:
        volatility = VolatilityState.EXPANDING
    elif atr_percentile < 25:
        volatility = VolatilityState.CONTRACTING
    else:
        volatility = VolatilityState.NORMAL

    return RegimeSnapshot(
        as_of=as_of_time.to_pydatetime(),
        timeframe=timeframe,
        regime=regime,
        volatility=volatility,
        adx=adx,
        plus_di=plus_di,
        minus_di=minus_di,
        bb_width_pct=bb_width_pct,
        bb_width_percentile=bb_width_percentile,
        atr=atr,
        atr_percentile=atr_percentile,
        confidence=confidence,
    )


# ── Multi-timeframe confluence ──────────────────────────────────────────────

def classify_multi_timeframe(
    df_by_timeframe: Dict[str, pd.DataFrame],
    as_of_idx_by_timeframe: Optional[Dict[str, int]] = None,
) -> MultiTimeframeRegime:
    """
    Klasifikasi regime untuk beberapa timeframe dan cek confluence.

    Args:
        df_by_timeframe: {"H1": df_h1, "H4": df_h4, ...}
        as_of_idx_by_timeframe: {"H1": 100, "H4": 25, ...} atau None

    Returns:
        MultiTimeframeRegime dengan snapshots + overall regime
    """
    snapshots: Dict[str, RegimeSnapshot] = {}

    for tf, df in df_by_timeframe.items():
        as_of_idx = None
        if as_of_idx_by_timeframe and tf in as_of_idx_by_timeframe:
            as_of_idx = as_of_idx_by_timeframe[tf]
        snapshots[tf] = classify_regime(df, as_of_idx=as_of_idx, timeframe=tf)

    # Overall regime: priority higher TF (H4 > H1 > M15)
    tf_priority = ["H4", "H1", "M15", "M5", "M30"]
    overall_regime = Regime.UNKNOWN
    for tf in tf_priority:
        if tf in snapshots and snapshots[tf].regime != Regime.UNKNOWN:
            overall_regime = snapshots[tf].regime
            break
    if overall_regime == Regime.UNKNOWN and snapshots:
        overall_regime = next(iter(snapshots.values())).regime

    # Confluence: H1 dan H4 harus align (atau unknown)
    confluence = True
    h1_regime = snapshots.get("H1", RegimeSnapshot(None, "H1", Regime.UNKNOWN, VolatilityState.UNKNOWN, 0, 0, 0, 0, 50, 0, 50, 0)).regime
    h4_regime = snapshots.get("H4", RegimeSnapshot(None, "H4", Regime.UNKNOWN, VolatilityState.UNKNOWN, 0, 0, 0, 0, 50, 0, 50, 0)).regime

    if h1_regime != Regime.UNKNOWN and h4_regime != Regime.UNKNOWN:
        # Map trending_up & trending_down → "directional"
        h1_dir = "up" if h1_regime == Regime.TRENDING_UP else ("down" if h1_regime == Regime.TRENDING_DOWN else "neutral")
        h4_dir = "up" if h4_regime == Regime.TRENDING_UP else ("down" if h4_regime == Regime.TRENDING_DOWN else "neutral")
        confluence = (h1_dir == h4_dir) or ("neutral" in (h1_dir, h4_dir))

    # Recommendation plain text
    rec_lines = []
    for tf, snap in snapshots.items():
        rec_lines.append(
            f"  {tf}: {snap.regime.value} (ADX={snap.adx:.1f}, "
            f"+DI={snap.plus_di:.1f}, -DI={snap.minus_di:.1f}, "
            f"vol={snap.volatility.value}, conf={snap.confidence:.2f})"
        )
    rec_lines.append(f"  Overall: {overall_regime.value}")
    rec_lines.append(f"  H1/H4 Confluence: {'YES' if confluence else 'NO'}")
    recommendation = "\n".join(rec_lines)

    as_of = None
    if snapshots:
        as_of = next(iter(snapshots.values())).as_of

    return MultiTimeframeRegime(
        as_of=as_of,
        snapshots=snapshots,
        overall_regime=overall_regime,
        confluence=confluence,
        recommendation=recommendation,
    )


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: trending vs ranging scenarios.
    """
    import numpy as np

    # Scenario 1: Trending up
    n = 300
    np.random.seed(13)
    trend = np.cumsum(np.random.randn(n) * 0.5 + 0.3)  # positive drift
    prices_trend = 2000.0 + trend

    df_trend = pd.DataFrame(
        {
            "time": pd.date_range("2023-01-01", periods=n, freq="15min"),
            "open": prices_trend + np.random.randn(n) * 0.2,
            "high": prices_trend + abs(np.random.randn(n)) * 0.8,
            "low": prices_trend - abs(np.random.randn(n)) * 0.8,
            "close": prices_trend,
        }
    )

    # Scenario 2: Ranging (sinusoid + low noise, no drift)
    np.random.seed(17)
    t = np.arange(n)
    prices_range = 2000.0 + 3.0 * np.sin(t / 20) + np.random.randn(n) * 0.3

    df_range = pd.DataFrame(
        {
            "time": pd.date_range("2023-02-01", periods=n, freq="15min"),
            "open": prices_range + np.random.randn(n) * 0.2,
            "high": prices_range + abs(np.random.randn(n)) * 0.8,
            "low": prices_range - abs(np.random.randn(n)) * 0.8,
            "close": prices_range,
        }
    )

    # Test trending
    snap_trend = classify_regime(df_trend, as_of_idx=290)
    print("=== Trending Scenario ===")
    print(f"  Regime: {snap_trend.regime.value}")
    print(f"  ADX: {snap_trend.adx:.1f}, +DI: {snap_trend.plus_di:.1f}, -DI: {snap_trend.minus_di:.1f}")
    print(f"  Volatility: {snap_trend.volatility.value} (ATR pct: {snap_trend.atr_percentile:.0f})")
    print(f"  BB width pct: {snap_trend.bb_width_percentile:.0f}")
    print(f"  Confidence: {snap_trend.confidence:.2f}")

    # Test ranging
    snap_range = classify_regime(df_range, as_of_idx=290)
    print("\n=== Ranging Scenario ===")
    print(f"  Regime: {snap_range.regime.value}")
    print(f"  ADX: {snap_range.adx:.1f}, +DI: {snap_range.plus_di:.1f}, -DI: {snap_range.minus_di:.1f}")
    print(f"  Volatility: {snap_range.volatility.value} (ATR pct: {snap_range.atr_percentile:.0f})")
    print(f"  BB width pct: {snap_range.bb_width_percentile:.0f}")
    print(f"  Confidence: {snap_range.confidence:.2f}")

    # Test multi-TF
    # Resample trending to H1 and H4 (simple take-every-N approach for test)
    df_h1 = df_trend.iloc[::4].reset_index(drop=True)
    df_h4 = df_trend.iloc[::16].reset_index(drop=True)
    mtf = classify_multi_timeframe(
        {"M15": df_trend, "H1": df_h1, "H4": df_h4},
        as_of_idx_by_timeframe={"M15": 290, "H1": 72, "H4": 18},
    )
    print("\n=== Multi-Timeframe (Trending) ===")
    print(mtf.recommendation)
