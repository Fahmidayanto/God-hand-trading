"""
Liquidity Analyzer - BSL/SSL & Equal Highs/Lows Detection

Mendeteksi liquidity pools yang menjadi target SL placement dan TP hunting:
- BSL (Buy-Side Liquidity): Equal highs / swing highs yang belum di-sweep
- SSL (Sell-Side Liquidity): Equal lows / swing lows yang belum di-sweep
- Sweep detection: ketika liquidity sudah diambil (stop hunt)
- Time-anchored query: untuk replay, lookback dari candle T (no look-ahead)

Output dipakai oleh:
- Rule-based decision engine (LLM OFF)
- LLMTradeSetup context (LLM ON)

Ponytail choices:
- Stateless per query: function-based, no instance state → aman untuk replay
- Lookback window explicit: tidak scan seluruh history
- Pure pandas: tidak butuh DB atau external state
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

import pandas as pd
from loguru import logger

# Suppress pandas UserWarning: "Discarding nonzero nanoseconds in conversion"
# Dipicu oleh pd.Timestamp(t).to_pydatetime() dimana t punya nanoseconds dari M15/H1/H4 OHLC
warnings.filterwarnings("ignore", message="Discarding nonzero nanoseconds in conversion")


# ── Constants ───────────────────────────────────────────────────────────────

# Toleransi untuk "equal" high/low (price diff dalam ATR units)
DEFAULT_EQUAL_TOLERANCE_ATR = 0.20  # 20% dari ATR(14) = dianggap sama

# Minimum touch count untuk qualify sebagai liquidity pool
DEFAULT_MIN_TOUCHES = 2

# Lookback default (candle) untuk replay context
DEFAULT_LOOKBACK = 200


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class LiquidityLevel:
    """Satu level liquidity (BSL atau SSL)."""
    kind: str  # "BSL" atau "SSL"
    price: float
    first_touch_time: datetime
    last_touch_time: datetime
    touch_count: int
    swept: bool
    sweep_time: Optional[datetime] = None
    sweep_candle_idx: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LiquidityContext:
    """Bundle output untuk decision engine / LLM."""
    as_of: datetime
    timeframe: str
    current_price: float
    nearest_bsl: Optional[LiquidityLevel] = None
    nearest_ssl: Optional[LiquidityLevel] = None
    all_bsl: List[LiquidityLevel] = None
    all_ssl: List[LiquidityLevel] = None
    recent_sweeps: List[LiquidityLevel] = None
    atr: Optional[float] = None

    def __post_init__(self):
        if self.all_bsl is None:
            self.all_bsl = []
        if self.all_ssl is None:
            self.all_ssl = []
        if self.recent_sweeps is None:
            self.recent_sweeps = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "timeframe": self.timeframe,
            "current_price": self.current_price,
            "nearest_bsl": self.nearest_bsl.to_dict() if self.nearest_bsl else None,
            "nearest_ssl": self.nearest_ssl.to_dict() if self.nearest_ssl else None,
            "all_bsl_count": len(self.all_bsl),
            "all_ssl_count": len(self.all_ssl),
            "recent_sweeps": [s.to_dict() for s in self.recent_sweeps[-5:]],
            "atr": self.atr,
        }


# ── Helper: ATR ─────────────────────────────────────────────────────────────

def _atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Hitung ATR(period) dari dataframe. Return None kalau data tidak cukup."""
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


# ── Core: Equal highs/lows clustering ───────────────────────────────────────

def _find_equal_highs(
    df: pd.DataFrame,
    swing_idx: List[int],
    tolerance: float,
    min_touches: int,
) -> List[Dict[str, Any]]:
    """
    Cluster swing highs yang berada dalam tolerance band → equal highs.
    """
    if not swing_idx or len(swing_idx) < min_touches:
        return []

    levels: List[Dict[str, Any]] = []
    highs = df["high"].values
    times = df["time"].values

    # Sort by price
    sorted_swings = sorted(swing_idx, key=lambda i: highs[i])
    used = set()

    for i, idx in enumerate(sorted_swings):
        if idx in used:
            continue
        cluster = [idx]
        for j in range(i + 1, len(sorted_swings)):
            jdx = sorted_swings[j]
            if jdx in used:
                continue
            if abs(highs[jdx] - highs[idx]) <= tolerance:
                cluster.append(jdx)
            else:
                break  # sorted by price, beyond tolerance = stop

        if len(cluster) >= min_touches:
            used.update(cluster)
            cluster_times = [pd.Timestamp(times[c]) for c in cluster]
            levels.append(
                {
                    "price": float(highs[idx]),
                    "indices": cluster,
                    "first_touch": min(cluster_times),
                    "last_touch": max(cluster_times),
                    "touch_count": len(cluster),
                }
            )
    return levels


def _find_equal_lows(
    df: pd.DataFrame,
    swing_idx: List[int],
    tolerance: float,
    min_touches: int,
) -> List[Dict[str, Any]]:
    """Mirror dari _find_equal_highs untuk swing lows."""
    if not swing_idx or len(swing_idx) < min_touches:
        return []

    levels: List[Dict[str, Any]] = []
    lows = df["low"].values
    times = df["time"].values

    sorted_swings = sorted(swing_idx, key=lambda i: -lows[i])  # descending
    used = set()

    for i, idx in enumerate(sorted_swings):
        if idx in used:
            continue
        cluster = [idx]
        for j in range(i + 1, len(sorted_swings)):
            jdx = sorted_swings[j]
            if jdx in used:
                continue
            if abs(lows[jdx] - lows[idx]) <= tolerance:
                cluster.append(jdx)
            else:
                break

        if len(cluster) >= min_touches:
            used.update(cluster)
            cluster_times = [pd.Timestamp(times[c]) for c in cluster]
            levels.append(
                {
                    "price": float(lows[idx]),
                    "indices": cluster,
                    "first_touch": min(cluster_times),
                    "last_touch": max(cluster_times),
                    "touch_count": len(cluster),
                }
            )
    return levels


# ── Swing detection (simple fractal) ────────────────────────────────────────

def _fractal_swings(
    df: pd.DataFrame,
    n: int,
) -> tuple:
    """
    Swing highs/lows via simple fractal:
    - Swing high: high[i] > high[i-n:i] dan high[i] > high[i+1:i+n+1]
    - Swing low : low[i]  < low[i-n:i]  dan low[i]  < low[i+1:i+n+1]

    Untuk replay time-anchored: tidak boleh swing di n candle terakhir
    (belum konfirm). Return dua list of int index.
    """
    highs = df["high"].values
    lows = df["low"].values
    n_rows = len(df)

    sh, sl = [], []
    for i in range(n, n_rows - n):
        h_window = highs[i - n : i]
        h_future = highs[i + 1 : i + n + 1]
        if highs[i] > h_window.max() and highs[i] > h_future.max():
            sh.append(i)

        l_window = lows[i - n : i]
        l_future = lows[i + 1 : i + n + 1]
        if lows[i] < l_window.min() and lows[i] < l_future.min():
            sl.append(i)
    return sh, sl


# ── Sweep detection ─────────────────────────────────────────────────────────

def _detect_sweeps(
    df: pd.DataFrame,
    level_price: float,
    kind: str,
    last_touch_idx: int,
) -> tuple:
    """
    Cek apakah level sudah di-sweep SETELAH last_touch.

    BSL sweep: candle setelah last_touch close > level_price (high wick tembus lalu close above)
    SSL sweep: candle setelah last_touch close < level_price (low wick tembus lalu close below)

    Return (swept: bool, sweep_idx: Optional[int], sweep_time: Optional[datetime])
    """
    if last_touch_idx >= len(df) - 1:
        return False, None, None

    times = df["time"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values

    if kind == "BSL":
        for i in range(last_touch_idx + 1, len(df)):
            if highs[i] > level_price and closes[i] > level_price:
                return True, i, pd.Timestamp(times[i])
        return False, None, None
    else:  # SSL
        for i in range(last_touch_idx + 1, len(df)):
            if lows[i] < level_price and closes[i] < level_price:
                return True, i, pd.Timestamp(times[i])
        return False, None, None


# ── Public API ──────────────────────────────────────────────────────────────

def analyze_liquidity(
    df: pd.DataFrame,
    as_of_idx: Optional[int] = None,
    fractal_n: int = 5,
    equal_tolerance_atr: float = DEFAULT_EQUAL_TOLERANCE_ATR,
    min_touches: int = DEFAULT_MIN_TOUCHES,
    timeframe: str = "M15",
) -> LiquidityContext:
    """
    Hitung liquidity context time-anchored di as_of_idx.

    Args:
        df: DataFrame dengan kolom [time, open, high, low, close, volume?].
            Wajib sorted ascending by time.
        as_of_idx: Index candle "sekarang" untuk time-anchoring.
                   None = pakai candle terakhir.
        fractal_n: Lookback/lookforward bars untuk swing fractal.
        equal_tolerance_atr: Toleransi "equal" sebagai fraksi ATR(14).
        min_touches: Minimal jumlah touch untuk qualify sebagai pool.
        timeframe: Label untuk output.

    Returns:
        LiquidityContext dengan nearest BSL/SSL, semua level, recent sweeps.

    CRITICAL: as_of_idx memastikan tidak ada look-ahead.
    Hanya data s.d. candle as_of_idx yang dipakai untuk detection.
    Sweep detection hanya scan SETELAH last_touch idx (no future info needed).
    """
    if df is None or len(df) < (fractal_n * 2 + 20):
        logger.warning("Insufficient data for liquidity analysis")
        return LiquidityContext(
            as_of=datetime.utcnow(),
            timeframe=timeframe,
            current_price=float(df["close"].iloc[-1]) if df is not None else 0.0,
        )

    if as_of_idx is None:
        as_of_idx = len(df) - 1

    if as_of_idx < 0 or as_of_idx >= len(df):
        raise ValueError(f"as_of_idx {as_of_idx} out of range [0, {len(df) - 1}]")

    as_of_time = pd.Timestamp(df["time"].iloc[as_of_idx])
    current_price = float(df["close"].iloc[as_of_idx])
    atr = _atr(df.iloc[: as_of_idx + 1], period=14)
    if atr is None or atr == 0:
        logger.warning("ATR invalid, using price-based fallback tolerance")
        atr = current_price * 0.001  # 0.1% fallback

    tolerance = atr * equal_tolerance_atr

    # Slice data: hanya sampai as_of_idx (NO LOOK-AHEAD)
    df_slice = df.iloc[: as_of_idx + 1].reset_index(drop=True)
    # Index asli (relatif terhadap df_slice) untuk swing detection
    sh, sl = _fractal_swings(df_slice, n=fractal_n)

    # Equal highs/lows clustering
    eq_highs = _find_equal_highs(df_slice, sh, tolerance, min_touches)
    eq_lows = _find_equal_lows(df_slice, sl, tolerance, min_touches)

    # Bangun LiquidityLevel objects + cek sweep
    bsl_levels: List[LiquidityLevel] = []
    for h in eq_highs:
        last_idx = max(h["indices"])
        swept, sweep_idx, sweep_time = _detect_sweeps(
            df_slice, h["price"], "BSL", last_idx
        )
        bsl_levels.append(
            LiquidityLevel(
                kind="BSL",
                price=h["price"],
                first_touch_time=h["first_touch"],
                last_touch_time=h["last_touch"],
                touch_count=h["touch_count"],
                swept=swept,
                sweep_time=sweep_time,
                sweep_candle_idx=sweep_idx,
            )
        )

    ssl_levels: List[LiquidityLevel] = []
    for low in eq_lows:
        last_idx = max(low["indices"])
        swept, sweep_idx, sweep_time = _detect_sweeps(
            df_slice, low["price"], "SSL", last_idx
        )
        ssl_levels.append(
            LiquidityLevel(
                kind="SSL",
                price=low["price"],
                first_touch_time=low["first_touch"],
                last_touch_time=low["last_touch"],
                touch_count=low["touch_count"],
                swept=swept,
                sweep_time=sweep_time,
                sweep_candle_idx=sweep_idx,
            )
        )

    # Filter: hanya pool yang BELUM swept (BSL = TP target, SSL = SL reference)
    # Tapi tetap expose swept pools di recent_sweeps
    unswept_bsl = [b for b in bsl_levels if not b.swept]
    unswept_ssl = [s for s in ssl_levels if not s.swept]

    # Nearest BSL di atas current price, nearest SSL di bawah
    nearest_bsl = None
    if unswept_bsl:
        above = [b for b in unswept_bsl if b.price > current_price]
        if above:
            nearest_bsl = min(above, key=lambda b: b.price - current_price)

    nearest_ssl = None
    if unswept_ssl:
        below = [s for s in unswept_ssl if s.price < current_price]
        if below:
            nearest_ssl = min(below, key=lambda s: current_price - s.price)

    # Recent sweeps (5 terakhir)
    swept_all = [lv for lv in bsl_levels + ssl_levels if lv.swept]
    swept_all.sort(key=lambda lv: lv.sweep_time, reverse=True)
    recent_sweeps = swept_all[:5]

    return LiquidityContext(
        as_of=as_of_time.to_pydatetime(),
        timeframe=timeframe,
        current_price=current_price,
        nearest_bsl=nearest_bsl,
        nearest_ssl=nearest_ssl,
        all_bsl=bsl_levels,
        all_ssl=ssl_levels,
        recent_sweeps=recent_sweeps,
        atr=atr,
    )


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: bikin fake OHLC, jalankan analyzer, print output.

    Cara run:
        python verification_system/analyzers/liquidity_analyzer.py
    """
    import numpy as np

    n = 300
    np.random.seed(42)
    base = 2000.0
    prices = base + np.cumsum(np.random.randn(n) * 1.5)

    # Inject 2 equal highs (liquidity pool) dan 1 equal lows
    prices[100] = 2050.0
    prices[140] = 2050.3
    prices[180] = 2049.8  # Equal highs cluster
    prices[60] = 1980.0
    prices[200] = 1979.7  # Equal lows cluster

    df = pd.DataFrame(
        {
            "time": pd.date_range("2023-01-01", periods=n, freq="15min"),
            "open": prices + np.random.randn(n) * 0.5,
            "high": prices + abs(np.random.randn(n)) * 1.0,
            "low": prices - abs(np.random.randn(n)) * 1.0,
            "close": prices,
        }
    )

    # Test di candle 250 (sebelum sweep)
    ctx = analyze_liquidity(df, as_of_idx=250)
    print("=== Liquidity Context @ idx=250 ===")
    print(f"as_of: {ctx.as_of}")
    print(f"current_price: {ctx.current_price:.2f}")
    print(f"atr: {ctx.atr:.2f}")
    print(f"BSL count: {len(ctx.all_bsl)}, unswept: {len([b for b in ctx.all_bsl if not b.swept])}")
    print(f"SSL count: {len(ctx.all_ssl)}, unswept: {len([s for s in ctx.all_ssl if not s.swept])}")
    if ctx.nearest_bsl:
        print(f"Nearest BSL: {ctx.nearest_bsl.price:.2f} (touches={ctx.nearest_bsl.touch_count})")
    if ctx.nearest_ssl:
        print(f"Nearest SSL: {ctx.nearest_ssl.price:.2f} (touches={ctx.nearest_ssl.touch_count})")
    print(f"Recent sweeps: {len(ctx.recent_sweeps)}")
