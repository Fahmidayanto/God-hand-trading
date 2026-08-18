"""
FVG (Fair Value Gap) Detector - ICT/SMC Imbalance

Mendeteksi Fair Value Gap / imbalance:
- Bullish FVG: low[i+1] > high[i-1] → gap up antara candle-1 dan candle+1
  - Zone: [high[i-1], low[i+1]] = area yang belum di-fill
- Bearish FVG: high[i+1] < low[i-1] → gap down
  - Zone: [high[i+1], low[i-1]]

Konsep ICT:
- FVG = area inefisiensi yang price cenderung kembali untuk di-fill
- Mitigation: price return ke zone → entry signal (mitigation entry)
- CE (Consequent Encroachment): midpoint zone, sering jadi partial TP
- Inverse FVG: ketika FVG dimitigated lalu tembus, jadi FVG di sisi sebaliknya
- FVG di discount (lower half range) = high probability long
- FVG di premium (upper half range) = high probability short

Penting untuk SL/TP:
- Entry sering di FVG yang baru dimitigated
- TP1 di CE (50% fill), TP2 di opposite edge (full fill)
- SL di luar FVG zone

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

DEFAULT_MIN_GAP_ATR = 0.30      # Minimum gap size = 30% dari ATR (avoid noise)
DEFAULT_LOOKBACK = 200
DEFAULT_ZONE_BUFFER_ATR = 0.05  # Buffer di atas/bawah FVG zone


# ── Enums & dataclasses ─────────────────────────────────────────────────────

class FVGKind(str, Enum):
    BULLISH = "bullish"  # Gap up, expect price fill from above → support
    BEARISH = "bearish"  # Gap down, expect price fill from below → resistance


class FVGState(str, Enum):
    FRESH = "fresh"
    PARTIALLY_FILLED = "partially_filled"
    FULLY_FILLED = "fully_filled"
    INVALIDATED = "invalidated"  # Tembus jadi inverse FVG
    INVERSE = "inverse"          # Confirmed inverse FVG


@dataclass
class FVG:
    kind: FVGKind
    state: FVGState
    top: float
    bottom: float
    ce: float  # Consequent Encroachment (midpoint)
    fvg_time: datetime      # Time of middle candle [i]
    fvg_index: int
    pre_candle_time: datetime
    post_candle_time: datetime
    gap_size_atr: float     # Gap size dalam ATR units
    fill_pct: float = 0.0   # 0=fresh, 1=fully filled
    mitigated_time: Optional[datetime] = None
    inverse_time: Optional[datetime] = None

    @property
    def zone_size(self) -> float:
        return self.top - self.bottom

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["state"] = self.state.value
        d["zone_size"] = self.zone_size
        return d


@dataclass
class FVGContext:
    as_of: datetime
    timeframe: str
    current_price: float
    atr: Optional[float]
    bullish_fvgs: List[FVG]
    bearish_fvgs: List[FVG]
    fresh_bullish_near: Optional[FVG] = None
    fresh_bearish_near: Optional[FVG] = None
    mitigated_bullish_recent: Optional[FVG] = None
    mitigated_bearish_recent: Optional[FVG] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "timeframe": self.timeframe,
            "current_price": self.current_price,
            "atr": self.atr,
            "bullish_count": len(self.bullish_fvgs),
            "bearish_count": len(self.bearish_fvgs),
            "fresh_bullish_near": self.fresh_bullish_near.to_dict() if self.fresh_bullish_near else None,
            "fresh_bearish_near": self.fresh_bearish_near.to_dict() if self.fresh_bearish_near else None,
            "mitigated_bullish_recent": self.mitigated_bullish_recent.to_dict() if self.mitigated_bullish_recent else None,
            "mitigated_bearish_recent": self.mitigated_bearish_recent.to_dict() if self.mitigated_bearish_recent else None,
        }


# ── Helper: ATR ─────────────────────────────────────────────────────────────

def _atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if len(df) < period + 1:
        return None
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
    return float(tr.rolling(period).mean().iloc[-1])


# ── FVG state update ────────────────────────────────────────────────────────

def _update_fvg_state(
    fvg: FVG,
    df: pd.DataFrame,
    fvg_idx: int,
) -> FVG:
    """
    Scan candle SETELAH fvg_idx (s.d. end of df) untuk update state.

    Logic:
    - Bullish FVG (gap up): expect price fill from above
      - Partial fill: candle low masuk zone
      - Full fill: candle low tembus bottom (low <= bottom)
      - Invalidation: close < bottom → gap invalid, jadi inverse
    - Bearish FVG (gap down): expect price fill from below
      - Partial fill: candle high masuk zone
      - Full fill: candle high tembus top (high >= top)
      - Invalidation: close > top → jadi inverse
    """
    if fvg.state in (FVGState.INVALIDATED, FVGState.INVERSE):
        return fvg

    zone_size = fvg.zone_size
    if zone_size <= 0:
        return fvg

    for i in range(fvg_idx + 1, len(df)):
        row = df.iloc[i]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        t = pd.Timestamp(row["time"]).to_pydatetime()

        if fvg.kind == FVGKind.BULLISH:
            # Invalidation: close tembus bottom → jadi inverse
            if close < fvg.bottom:
                fvg.state = FVGState.INVERSE
                fvg.inverse_time = t
                # Inverse FVG: zone jadi resistance di atas current
                return fvg

            # Track fill
            if low <= fvg.top and not fvg.mitigated_time:
                fvg.mitigated_time = t
                fvg.state = FVGState.PARTIALLY_FILLED

            if fvg.state in (FVGState.PARTIALLY_FILLED, FVGState.FULLY_FILLED):
                if low <= fvg.top:
                    # Hitung fill_pct: seberapa dalam price masuk zone
                    penetration = (fvg.top - low) / zone_size
                    fvg.fill_pct = min(1.0, max(fvg.fill_pct, penetration))
                    if low <= fvg.bottom:
                        fvg.state = FVGState.FULLY_FILLED
                        fvg.fill_pct = 1.0

        else:  # BEARISH FVG
            # Invalidation: close tembus top → jadi inverse
            if close > fvg.top:
                fvg.state = FVGState.INVERSE
                fvg.inverse_time = t
                return fvg

            if high >= fvg.bottom and not fvg.mitigated_time:
                fvg.mitigated_time = t
                fvg.state = FVGState.PARTIALLY_FILLED

            if fvg.state in (FVGState.PARTIALLY_FILLED, FVGState.FULLY_FILLED):
                if high >= fvg.bottom:
                    penetration = (high - fvg.bottom) / zone_size
                    fvg.fill_pct = min(1.0, max(fvg.fill_pct, penetration))
                    if high >= fvg.top:
                        fvg.state = FVGState.FULLY_FILLED
                        fvg.fill_pct = 1.0

    return fvg


# ── Core: detect FVGs ───────────────────────────────────────────────────────

def detect_fvgs(
    df: pd.DataFrame,
    as_of_idx: Optional[int] = None,
    min_gap_atr: float = DEFAULT_MIN_GAP_ATR,
    lookback_bars: int = DEFAULT_LOOKBACK,
    timeframe: str = "M15",
) -> FVGContext:
    """
    Deteksi Fair Value Gaps time-anchored di as_of_idx.

    Algoritma:
    1. Hitung ATR(14) di slice s.d. as_of_idx
    2. Scan candle [i-1, i, i+1]:
       - Bullish FVG jika low[i+1] > high[i-1] + min_gap
       - Bearish FVG jika high[i+1] < low[i-1] - min_gap
    3. Update state: mitigation/invalidation scan SETELAH fvg
    4. Filter & return

    CRITICAL: hanya scan s.d. as_of_idx. Tidak ada look-ahead.
    """
    if df is None or len(df) < 30:
        logger.warning("Insufficient data for FVG detection")
        return FVGContext(
            as_of=datetime.utcnow(),
            timeframe=timeframe,
            current_price=float(df["close"].iloc[-1]) if df is not None else 0.0,
            bullish_fvgs=[],
            bearish_fvgs=[],
        )

    if as_of_idx is None:
        as_of_idx = len(df) - 1

    if as_of_idx < 0 or as_of_idx >= len(df):
        raise ValueError(f"as_of_idx {as_of_idx} out of range [0, {len(df) - 1}]")

    as_of_time = pd.Timestamp(df["time"].iloc[as_of_idx])
    current_price = float(df["close"].iloc[as_of_idx])
    atr = _atr(df.iloc[: as_of_idx + 1], period=14)
    if atr is None or atr == 0:
        logger.warning("ATR invalid, fallback")
        atr = current_price * 0.001

    buffer = atr * DEFAULT_ZONE_BUFFER_ATR
    min_gap = atr * min_gap_atr

    # Slice HANYA sampai as_of_idx (NO LOOK-AHEAD)
    df_slice = df.iloc[: as_of_idx + 1].reset_index(drop=True)
    n = len(df_slice)

    opens = df_slice["open"].values
    closes = df_slice["close"].values
    highs = df_slice["high"].values
    lows = df_slice["low"].values
    times = df_slice["time"].values

    start = max(1, as_of_idx - lookback_bars)
    end = as_of_idx  # inclusive, butuh i+1 valid

    fvgs: List[FVG] = []

    # i = middle candle, butuh i-1 dan i+1 valid
    for i in range(start, min(end, n - 1)):
        # Bullish FVG: low[i+1] > high[i-1]
        if i + 1 < n:
            gap_up = float(lows[i + 1]) - float(highs[i - 1])
            if gap_up > min_gap:
                top = float(lows[i + 1]) + buffer
                bottom = float(highs[i - 1]) - buffer
                fvgs.append(
                    FVG(
                        kind=FVGKind.BULLISH,
                        state=FVGState.FRESH,
                        top=top,
                        bottom=bottom,
                        ce=(top + bottom) / 2,
                        fvg_time=pd.Timestamp(times[i]).to_pydatetime(),
                        fvg_index=i,
                        pre_candle_time=pd.Timestamp(times[i - 1]).to_pydatetime(),
                        post_candle_time=pd.Timestamp(times[i + 1]).to_pydatetime(),
                        gap_size_atr=gap_up / atr,
                    )
                )

        # Bearish FVG: high[i+1] < low[i-1]
        if i + 1 < n:
            gap_down = float(lows[i - 1]) - float(highs[i + 1])
            if gap_down > min_gap:
                top = float(lows[i - 1]) + buffer
                bottom = float(highs[i + 1]) - buffer
                fvgs.append(
                    FVG(
                        kind=FVGKind.BEARISH,
                        state=FVGState.FRESH,
                        top=top,
                        bottom=bottom,
                        ce=(top + bottom) / 2,
                        fvg_time=pd.Timestamp(times[i]).to_pydatetime(),
                        fvg_index=i,
                        pre_candle_time=pd.Timestamp(times[i - 1]).to_pydatetime(),
                        post_candle_time=pd.Timestamp(times[i + 1]).to_pydatetime(),
                        gap_size_atr=gap_down / atr,
                    )
                )

    # Update state untuk semua FVG
    for fvg in fvgs:
        _update_fvg_state(fvg, df_slice, fvg.fvg_index)

    # Sort by recency
    fvgs.sort(key=lambda f: f.fvg_time, reverse=True)

    bullish_fvgs = [f for f in fvgs if f.kind == FVGKind.BULLISH]
    bearish_fvgs = [f for f in fvgs if f.kind == FVGKind.BEARISH]

    # Nearest FRESH bullish FVG di bawah current price (support)
    fresh_bullish_near = None
    for f in bullish_fvgs:
        if f.state == FVGState.FRESH and f.top < current_price:
            if fresh_bullish_near is None or f.top > fresh_bullish_near.top:
                fresh_bullish_near = f

    # Nearest FRESH bearish FVG di atas current price (resistance)
    fresh_bearish_near = None
    for f in bearish_fvgs:
        if f.state == FVGState.FRESH and f.bottom > current_price:
            if fresh_bearish_near is None or f.bottom < fresh_bearish_near.bottom:
                fresh_bearish_near = f

    # Most recent mitigated
    mitigated_bullish_recent = None
    for f in bullish_fvgs:
        if f.state in (FVGState.PARTIALLY_FILLED, FVGState.FULLY_FILLED):
            if (
                mitigated_bullish_recent is None
                or f.mitigated_time > mitigated_bullish_recent.mitigated_time
            ):
                mitigated_bullish_recent = f

    mitigated_bearish_recent = None
    for f in bearish_fvgs:
        if f.state in (FVGState.PARTIALLY_FILLED, FVGState.FULLY_FILLED):
            if (
                mitigated_bearish_recent is None
                or f.mitigated_time > mitigated_bearish_recent.mitigated_time
            ):
                mitigated_bearish_recent = f

    return FVGContext(
        as_of=as_of_time.to_pydatetime(),
        timeframe=timeframe,
        current_price=current_price,
        atr=atr,
        bullish_fvgs=bullish_fvgs,
        bearish_fvgs=bearish_fvgs,
        fresh_bullish_near=fresh_bullish_near,
        fresh_bearish_near=fresh_bearish_near,
        mitigated_bullish_recent=mitigated_bullish_recent,
        mitigated_bearish_recent=mitigated_bearish_recent,
    )


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: synthetic FVG scenario.

    Scenario:
    - idx 30: high=2000, close=2010 (bullish)
    - idx 31: bullish impulse candle
    - idx 32: low=2018 (gap up vs idx 30 high) → BULLISH FVG [2000, 2018]
    - idx 60: bearish impulse
    - idx 61: bearish candle
    - idx 62: high=1970 (gap down vs idx 60 low=1980) → BEARISH FVG [1970, 1980]
    """
    import numpy as np

    n = 200
    np.random.seed(11)
    base = 2000.0
    prices = base + np.cumsum(np.random.randn(n) * 1.0)

    df = pd.DataFrame(
        {
            "time": pd.date_range("2023-08-01", periods=n, freq="15min"),
            "open": prices + np.random.randn(n) * 0.3,
            "high": prices + abs(np.random.randn(n)) * 0.8,
            "low": prices - abs(np.random.randn(n)) * 0.8,
            "close": prices,
        }
    )

    # Inject BULLISH FVG at idx 31 (middle candle)
    # pre candle (30): high=2000, low=1990
    # mid candle (31): open=2001, close=2010, low=2000.5, high=2011
    # post candle (32): low=2018 (gap up from pre high 2000)
    df.iloc[30, df.columns.get_loc("high")] = 2000.0
    df.iloc[30, df.columns.get_loc("low")] = 1990.0
    df.iloc[31, df.columns.get_loc("open")] = 2001.0
    df.iloc[31, df.columns.get_loc("close")] = 2010.0
    df.iloc[31, df.columns.get_loc("low")] = 2000.5
    df.iloc[31, df.columns.get_loc("high")] = 2011.0
    df.iloc[32, df.columns.get_loc("low")] = 2018.0
    df.iloc[32, df.columns.get_loc("high")] = 2019.0

    # Inject BEARISH FVG at idx 80 (middle candle)
    # pre candle (79): low=1980, high=1990
    # mid candle (80): open=1985, close=1975
    # post candle (81): high=1970 (gap down from pre low 1980)
    df.iloc[79, df.columns.get_loc("high")] = 1990.0
    df.iloc[79, df.columns.get_loc("low")] = 1980.0
    df.iloc[80, df.columns.get_loc("open")] = 1985.0
    df.iloc[80, df.columns.get_loc("close")] = 1975.0
    df.iloc[80, df.columns.get_loc("low")] = 1974.0
    df.iloc[80, df.columns.get_loc("high")] = 1986.0
    df.iloc[81, df.columns.get_loc("high")] = 1970.0
    df.iloc[81, df.columns.get_loc("low")] = 1968.0

    # Test di idx 150 (setelah FVG terbentuk)
    ctx = detect_fvgs(df, as_of_idx=150, lookback_bars=200)

    print("=== FVG Context @ idx=150 ===")
    print(f"as_of: {ctx.as_of}")
    print(f"current_price: {ctx.current_price:.2f}, atr: {ctx.atr:.2f}")
    print(f"Bullish FVGs: {len(ctx.bullish_fvgs)}, Bearish FVGs: {len(ctx.bearish_fvgs)}")
    print()
    for f in ctx.bullish_fvgs[:5]:
        print(f"  BULL {f.state.value:18s} zone [{f.bottom:.2f}-{f.top:.2f}] "
              f"CE={f.ce:.2f} gap={f.gap_size_atr:.1f}x ATR fill={f.fill_pct*100:.0f}%")
    print()
    for f in ctx.bearish_fvgs[:5]:
        print(f"  BEAR {f.state.value:18s} zone [{f.bottom:.2f}-{f.top:.2f}] "
              f"CE={f.ce:.2f} gap={f.gap_size_atr:.1f}x ATR fill={f.fill_pct*100:.0f}%")
    print()
    if ctx.fresh_bullish_near:
        print(f"Fresh demand below: [{ctx.fresh_bullish_near.bottom:.2f}-"
              f"{ctx.fresh_bullish_near.top:.2f}]")
    if ctx.fresh_bearish_near:
        print(f"Fresh supply above: [{ctx.fresh_bearish_near.bottom:.2f}-"
              f"{ctx.fresh_bearish_near.top:.2f}]")
