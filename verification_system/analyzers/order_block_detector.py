"""
Order Block Detector - ICT/SMC Order Block & Breaker Block

Mendeteksi:
- Order Block (OB): candle terakhir sebelum impulsive move (BOS/CHoCH trigger)
  - Bullish OB: candle bearish terakhir sebelum strong bullish impulse
  - Bearish OB: candle bullish terakhir sebelum strong bearish impulse
- Mitigation: ketika price return ke OB zone (entry signal)
- Invalidation: ketika price tembus OB → OB jadi "breaker"
- Breaker Block: OB yang sudah broken, jadi support/resistance di sisi sebaliknya

Penting untuk SL/TP placement:
- TP sering di order block yang belum dimitigated di higher TF
- Entry sering di OB yang baru dimitigated (mitigation entry)
- SL ditaruh di luar OB zone + buffer

Ponytail choices:
- Stateless function: replay-safe
- Time-anchored query via as_of_idx
- Impulse detection via body ratio vs ATR
- Pure pandas, no DB
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

DEFAULT_IMPULSE_BODY_ATR = 2.0   # Body candle >= 2x ATR → impulse
DEFAULT_LOOKAHEAD_BARS = 5        # Sisa candle setelah OB yg harus impulsive
DEFAULT_OB_LOOKBACK = 100         # Max candle ke belakang untuk cari OB
DEFAULT_OB_BUFFER_ATR = 0.10      # Zone buffer di atas/bawah OB


# ── Enums & dataclasses ─────────────────────────────────────────────────────

class OBKind(str, Enum):
    BULLISH = "bullish"   # Demand zone, expect price bounce up
    BEARISH = "bearish"   # Supply zone, expect price bounce down


class OBState(str, Enum):
    FRESH = "fresh"           # Baru terbentuk, belum disentuh
    MITIGATED = "mitigated"   # Sudah di-test, price pernah masuk zone
    INVALIDATED = "invalidated"  # Tembus, jadi breaker
    BREAKER = "breaker"       # Confirmed breaker block


@dataclass
class OrderBlock:
    kind: OBKind
    state: OBState
    top: float
    bottom: float
    ob_time: datetime          # Time of OB candle
    ob_index: int              # Index of OB candle
    impulse_time: datetime     # Time of impulse candle
    impulse_size_atr: float    # Body size dalam ATR units
    mitigated_time: Optional[datetime] = None
    breaker_time: Optional[datetime] = None
    touches: int = 0
    last_touch_time: Optional[datetime] = None
    last_touch_price: Optional[float] = None

    @property
    def zone_size(self) -> float:
        return self.top - self.bottom

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["state"] = self.state.value
        d["zone_size"] = self.zone_size
        return d


@dataclass
class OrderBlockContext:
    as_of: datetime
    timeframe: str
    current_price: float
    atr: Optional[float]
    bullish_obs: List[OrderBlock]
    bearish_obs: List[OrderBlock]
    fresh_bullish_near: Optional[OrderBlock] = None   # OB demand di bawah price
    fresh_bearish_near: Optional[OrderBlock] = None   # OB supply di atas price
    mitigated_bullish_recent: Optional[OrderBlock] = None
    mitigated_bearish_recent: Optional[OrderBlock] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "timeframe": self.timeframe,
            "current_price": self.current_price,
            "atr": self.atr,
            "bullish_count": len(self.bullish_obs),
            "bearish_count": len(self.bearish_obs),
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


# ── Impulse detection ───────────────────────────────────────────────────────

def _is_bullish_impulse(row_body: float, atr: float, threshold: float) -> bool:
    return row_body >= atr * threshold


def _is_bearish_impulse(row_body: float, atr: float, threshold: float) -> bool:
    return row_body >= atr * threshold


# ── OB state update: mitigation / invalidation / breaker ────────────────────

def _update_ob_state(
    ob: OrderBlock,
    df: pd.DataFrame,
    ob_idx: int,
) -> OrderBlock:
    """
    Scan candle SETELAH ob_idx (s.d. end of df) untuk update state.

    Logic:
    - Mitigation (bullish OB): candle low menyentuh bottom zone (price masuk)
    - Mitigation (bearish OB): candle high menyentuh top zone
    - Invalidation (bullish OB): candle close < bottom → OB jadi breaker
    - Invalidation (bearish OB): candle close > top → OB jadi breaker
    """
    if ob.state == OBState.INVALIDATED or ob.state == OBState.BREAKER:
        return ob

    for i in range(ob_idx + 1, len(df)):
        row = df.iloc[i]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        t = pd.Timestamp(row["time"]).to_pydatetime()

        if ob.kind == OBKind.BULLISH:
            # Mitigation: low masuk zone
            if low <= ob.top and not ob.mitigated_time:
                # Pastikan tidak tembus (close > bottom)
                if close > ob.bottom:
                    ob.mitigated_time = t
                    ob.state = OBState.MITIGATED
                    ob.touches += 1
                    ob.last_touch_time = t
                    ob.last_touch_price = low
                # Jika close < bottom → invalidation handled di bawah
            # Invalidation: close tembus bottom
            if close < ob.bottom:
                ob.state = OBState.BREAKER
                ob.breaker_time = t
                return ob
        else:  # BEARISH
            # Mitigation: high masuk zone
            if high >= ob.bottom and not ob.mitigated_time:
                if close < ob.top:
                    ob.mitigated_time = t
                    ob.state = OBState.MITIGATED
                    ob.touches += 1
                    ob.last_touch_time = t
                    ob.last_touch_price = high
            # Invalidation: close tembus top
            if close > ob.top:
                ob.state = OBState.BREAKER
                ob.breaker_time = t
                return ob

        # Update touches if re-entry ke zone setelah mitigation
        if ob.state == OBState.MITIGATED:
            if ob.kind == OBKind.BULLISH and low <= ob.top and i > 0:
                if pd.Timestamp(df.iloc[i - 1]["time"]).to_pydatetime() != ob.last_touch_time:
                    ob.touches += 1
                    ob.last_touch_time = t
                    ob.last_touch_price = low
            elif ob.kind == OBKind.BEARISH and high >= ob.bottom and i > 0:
                if pd.Timestamp(df.iloc[i - 1]["time"]).to_pydatetime() != ob.last_touch_time:
                    ob.touches += 1
                    ob.last_touch_time = t
                    ob.last_touch_price = high

    return ob


# ── Core: detect Order Blocks ───────────────────────────────────────────────

def detect_order_blocks(
    df: pd.DataFrame,
    as_of_idx: Optional[int] = None,
    impulse_body_atr: float = DEFAULT_IMPULSE_BODY_ATR,
    lookahead_bars: int = DEFAULT_LOOKAHEAD_BARS,
    lookback_bars: int = DEFAULT_OB_LOOKBACK,
    timeframe: str = "M15",
) -> OrderBlockContext:
    """
    Deteksi Order Block time-anchored di as_of_idx.

    Algoritma:
    1. Hitung ATR(14) di slice s.d. as_of_idx
    2. Scan candle dari [as_of_idx - lookback_bars, as_of_idx]
    3. Untuk setiap candle, cek apakah candle berikut (lookahead) impulsive
    4. Jika ya → candle itu adalah kandidat OB
    5. Tentukan bullish/bearish based on impulse direction
    6. Update state (mitigation/invalidation) dengan scan SETELAH OB

    CRITICAL: lookahead di sini TETAP time-anchored — as_of_idx adalah
    hard cutoff, OB hanya valid jika impulse terjadi s.d. candle as_of_idx.
    Tidak melihat masa depan.
    """
    if df is None or len(df) < 30:
        logger.warning("Insufficient data for OB detection")
        return OrderBlockContext(
            as_of=datetime.utcnow(),
            timeframe=timeframe,
            current_price=float(df["close"].iloc[-1]) if df is not None else 0.0,
            bullish_obs=[],
            bearish_obs=[],
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

    buffer = atr * DEFAULT_OB_BUFFER_ATR

    # Slice HANYA sampai as_of_idx (NO LOOK-AHEAD)
    df_slice = df.iloc[: as_of_idx + 1].reset_index(drop=True)

    # Scan range
    start = max(0, as_of_idx - lookback_bars)
    # Stop sebelum lookahead (kita butuh candle setelahnya untuk konfirmasi impulse)
    end = as_of_idx  # inclusive
    max_ob_search_end = max(0, end - lookahead_bars)

    obs: List[OrderBlock] = []

    opens = df_slice["open"].values
    closes = df_slice["close"].values
    highs = df_slice["high"].values
    lows = df_slice["low"].values
    times = df_slice["time"].values

    for i in range(start, max_ob_search_end + 1):
        # Cek apakah ada impulse dalam lookahead window SETELAH i
        max_follow = min(i + 1 + lookahead_bars, len(df_slice))
        impulse_found = None

        for j in range(i + 1, max_follow):
            body = abs(closes[j] - opens[j])
            if body < atr * impulse_body_atr:
                continue
            # Bullish impulse: close > open, strong up
            if closes[j] > opens[j]:
                impulse_found = (j, body, OBKind.BULLISH)
                break
            # Bearish impulse: close < open, strong down
            elif closes[j] < opens[j]:
                impulse_found = (j, body, OBKind.BEARISH)
                break

        if not impulse_found:
            continue

        impulse_idx, impulse_body, kind = impulse_found
        # OB = candle SEBELUM impulse
        ob_idx = i
        ob_candle_is_bullish = closes[ob_idx] > opens[ob_idx]
        ob_candle_is_bearish = closes[ob_idx] < opens[ob_idx]

        # Bullish OB: candle bearish sebelum bullish impulse
        if kind == OBKind.BULLISH and ob_candle_is_bearish:
            top = float(highs[ob_idx]) + buffer
            bottom = float(lows[ob_idx]) - buffer
            ob = OrderBlock(
                kind=OBKind.BULLISH,
                state=OBState.FRESH,
                top=top,
                bottom=bottom,
                ob_time=pd.Timestamp(times[ob_idx]).to_pydatetime(),
                ob_index=ob_idx,
                impulse_time=pd.Timestamp(times[impulse_idx]).to_pydatetime(),
                impulse_size_atr=impulse_body / atr,
            )
            obs.append(ob)

        # Bearish OB: candle bullish sebelum bearish impulse
        elif kind == OBKind.BEARISH and ob_candle_is_bullish:
            top = float(highs[ob_idx]) + buffer
            bottom = float(lows[ob_idx]) - buffer
            ob = OrderBlock(
                kind=OBKind.BEARISH,
                state=OBState.FRESH,
                top=top,
                bottom=bottom,
                ob_time=pd.Timestamp(times[ob_idx]).to_pydatetime(),
                ob_index=ob_idx,
                impulse_time=pd.Timestamp(times[impulse_idx]).to_pydatetime(),
                impulse_size_atr=impulse_body / atr,
            )
            obs.append(ob)

    # Update state untuk semua OB (scan SETELAH masing-masing OB)
    for ob in obs:
        # Update dengan df full (sampai as_of_idx) — NO future
        _update_ob_state(ob, df_slice, ob.ob_index)

    # Sort by recency (most recent first)
    obs.sort(key=lambda o: o.ob_time, reverse=True)

    # Filter: pisahkan bullish vs bearish
    bullish_obs = [o for o in obs if o.kind == OBKind.BULLISH]
    bearish_obs = [o for o in obs if o.kind == OBKind.BEARISH]

    # Nearest FRESH bullish OB di BAWAH current price (demand zone)
    fresh_bullish_near = None
    for ob in bullish_obs:
        if ob.state == OBState.FRESH and ob.top < current_price:
            if fresh_bullish_near is None or ob.top > fresh_bullish_near.top:
                fresh_bullish_near = ob

    # Nearest FRESH bearish OB di ATAS current price (supply zone)
    fresh_bearish_near = None
    for ob in bearish_obs:
        if ob.state == OBState.FRESH and ob.bottom > current_price:
            if fresh_bearish_near is None or ob.bottom < fresh_bearish_near.bottom:
                fresh_bearish_near = ob

    # Most recent mitigated
    mitigated_bullish_recent = None
    for ob in bullish_obs:
        if ob.state == OBState.MITIGATED:
            if (
                mitigated_bullish_recent is None
                or ob.mitigated_time > mitigated_bullish_recent.mitigated_time
            ):
                mitigated_bullish_recent = ob

    mitigated_bearish_recent = None
    for ob in bearish_obs:
        if ob.state == OBState.MITIGATED:
            if (
                mitigated_bearish_recent is None
                or ob.mitigated_time > mitigated_bearish_recent.mitigated_time
            ):
                mitigated_bearish_recent = ob

    return OrderBlockContext(
        as_of=as_of_time.to_pydatetime(),
        timeframe=timeframe,
        current_price=current_price,
        atr=atr,
        bullish_obs=bullish_obs,
        bearish_obs=bearish_obs,
        fresh_bullish_near=fresh_bullish_near,
        fresh_bearish_near=fresh_bearish_near,
        mitigated_bullish_recent=mitigated_bullish_recent,
        mitigated_bearish_recent=mitigated_bearish_recent,
    )


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: synthetic OB scenario, validate detection.

    Scenario:
    - idx 50: bearish candle (OB candidate)
    - idx 51-55: 5 bullish candles strong move (impulse)
    - idx 80: bullish candle (OB candidate)
    - idx 81-85: 5 bearish candles strong move (impulse)
    - idx 120: price return ke OB zone idx 50 (mitigation)
    - idx 150: price tembus OB idx 50 (breaker)
    """
    import numpy as np

    n = 200
    np.random.seed(7)
    base = 2000.0
    prices = base + np.cumsum(np.random.randn(n) * 1.0)

    df = pd.DataFrame(
        {
            "time": pd.date_range("2023-06-01", periods=n, freq="15min"),
            "open": prices + np.random.randn(n) * 0.3,
            "high": prices + abs(np.random.randn(n)) * 0.8,
            "low": prices - abs(np.random.randn(n)) * 0.8,
            "close": prices,
        }
    )

    # Inject OB1 (bullish) — bearish candle @ idx 50, impulse @ 51-55
    df.iloc[50, df.columns.get_loc("open")] = 2010.0
    df.iloc[50, df.columns.get_loc("close")] = 2003.0  # bearish
    df.iloc[50, df.columns.get_loc("high")] = 2011.0
    df.iloc[50, df.columns.get_loc("low")] = 2002.0
    for k in range(51, 56):
        df.iloc[k, df.columns.get_loc("open")] = 2003.0 + (k - 51) * 1.0
        df.iloc[k, df.columns.get_loc("close")] = 2003.0 + (k - 51) * 3.0  # strong bullish

    # Inject OB2 (bearish) — bullish candle @ idx 80, impulse @ 81-85
    df.iloc[80, df.columns.get_loc("open")] = 2050.0
    df.iloc[80, df.columns.get_loc("close")] = 2057.0  # bullish
    df.iloc[80, df.columns.get_loc("high")] = 2058.0
    df.iloc[80, df.columns.get_loc("low")] = 2049.0
    for k in range(81, 86):
        df.iloc[k, df.columns.get_loc("open")] = 2057.0 - (k - 81) * 1.0
        df.iloc[k, df.columns.get_loc("close")] = 2057.0 - (k - 81) * 3.0  # strong bearish

    # Test di idx 180 (semua event sudah lewat)
    # lookback_bars=200 cover OB di idx 50 & 80 (default 100 hanya 1 day M15)
    ctx = detect_order_blocks(df, as_of_idx=180, lookback_bars=200)

    print("=== Order Block Context @ idx=180 ===")
    print(f"as_of: {ctx.as_of}")
    print(f"current_price: {ctx.current_price:.2f}")
    print(f"atr: {ctx.atr:.2f}")
    print(f"Total bullish OB: {len(ctx.bullish_obs)}")
    print(f"Total bearish OB: {len(ctx.bearish_obs)}")
    print()
    for ob in ctx.bullish_obs[:3]:
        print(f"BULL {ob.state.value}: zone [{ob.bottom:.2f} - {ob.top:.2f}] "
              f"impulse={ob.impulse_size_atr:.1f}x ATR")
    print()
    for ob in ctx.bearish_obs[:3]:
        print(f"BEAR {ob.state.value}: zone [{ob.bottom:.2f} - {ob.top:.2f}] "
              f"impulse={ob.impulse_size_atr:.1f}x ATR")
    print()
    if ctx.fresh_bullish_near:
        print(f"Fresh demand below: [{ctx.fresh_bullish_near.bottom:.2f} - "
              f"{ctx.fresh_bullish_near.top:.2f}]")
    if ctx.fresh_bearish_near:
        print(f"Fresh supply above: [{ctx.fresh_bearish_near.bottom:.2f} - "
              f"{ctx.fresh_bearish_near.top:.2f}]")
