"""
Replay Structure Provider - Unified Context Builder

Wrapper yang menggabungkan SEMUA analyzer (1-5) menjadi satu context bundle
untuk decision engine (rule-based atau LLM).

PENTING:
- Pure function, time-anchored
- Tidak ada side effect, no cache, no DB write
- Single API call → single context object
- Tergantung pada input: ohlc_by_timeframe dict + anchor timestamp

Output structure (untuk LLM prompt atau rule engine):
{
    "anchor": {...},
    "market_data": {...},
    "structure": {  # HH/LL/CHoCH/BoS dari existing detector
        "recent_events": [...],
        "last_bos": ...,
        "last_choch": ...
    },
    "liquidity": {
        "nearest_bsl": {...},
        "nearest_ssl": {...}
    },
    "order_blocks": {
        "fresh_bullish_near": {...},
        "fresh_bearish_near": {...}
    },
    "fvg": {
        "fresh_bullish_near": {...},
        "fresh_bearish_near": {...}
    },
    "regime": {
        "M15": {...},
        "H1": {...},
        "H4": {...},
        "overall": ...,
        "confluence": bool
    },
    "events": {
        "next_high_impact": {...} | None,
        "should_avoid_trading": bool,
        "avoid_reason": str
    }
}

Usage:
    provider = ReplayStructureProvider()
    context = provider.build(
        ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
        anchor_ts=datetime(2023, 6, 15, 14, 30, tzinfo=timezone.utc),
        anchor_idx_by_timeframe={"M15": 100, "H1": 25, "H4": 6},
    )
    # context adalah dict, ready untuk LLM prompt atau rule engine

Ponytail:
- Stateless
- Optional dependencies: jika satu analyzer gagal, context masih returned dengan note
- Pure Python, no I/O
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
from loguru import logger

# Local analyzer imports — support both package and standalone mode
try:
    from .liquidity_analyzer import analyze_liquidity
    from .order_block_detector import detect_order_blocks
    from .fvg_detector import detect_fvgs
    from .regime_detector import classify_regime, classify_multi_timeframe
    from .economic_calendar_replay import (
        get_next_high_impact,
        should_avoid_trading,
    )
except ImportError:
    from liquidity_analyzer import analyze_liquidity
    from order_block_detector import detect_order_blocks
    from fvg_detector import detect_fvgs
    from regime_detector import classify_regime, classify_multi_timeframe
    from economic_calendar_replay import (
        get_next_high_impact,
        should_avoid_trading,
    )


@dataclass
class ReplayContext:
    """Bundle semua context untuk decision engine / LLM."""
    anchor: Dict[str, Any]
    market_data: Dict[str, Any]
    liquidity: Dict[str, Any]
    order_blocks: Dict[str, Any]
    fvg: Dict[str, Any]
    regime: Dict[str, Any]
    events: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor": self.anchor,
            "market_data": self.market_data,
            "liquidity": self.liquidity,
            "order_blocks": self.order_blocks,
            "fvg": self.fvg,
            "regime": self.regime,
            "events": self.events,
            "metadata": self.metadata,
        }

    def to_llm_prompt_context(self) -> str:
        """
        Format context sebagai plain text untuk LLM prompt.
        Compact, structured, scan-friendly.
        """
        lines = []
        lines.append(f"=== ANCHOR ===")
        lines.append(f"Timestamp: {self.anchor.get('timestamp')}")
        lines.append(f"Timeframe: {self.anchor.get('primary_timeframe')}")
        lines.append(f"Current price: {self.market_data.get('current_price'):.2f}")
        lines.append(f"ATR(14): {self.market_data.get('atr', 0):.2f}")
        lines.append("")

        lines.append("=== REGIME ===")
        for tf, snap in self.regime.get("snapshots", {}).items():
            lines.append(
                f"  {tf}: {snap.get('regime')} | ADX={snap.get('adx', 0):.1f} "
                f"| +DI={snap.get('plus_di', 0):.1f} -DI={snap.get('minus_di', 0):.1f} "
                f"| vol={snap.get('volatility')} | conf={snap.get('confidence', 0):.2f}"
            )
        lines.append(f"  Overall: {self.regime.get('overall_regime')}")
        lines.append(f"  H1/H4 Confluence: {'YES' if self.regime.get('confluence') else 'NO'}")
        lines.append("")

        lines.append("=== LIQUIDITY ===")
        nearest_bsl = self.liquidity.get("nearest_bsl")
        nearest_ssl = self.liquidity.get("nearest_ssl")
        if nearest_bsl:
            lines.append(
                f"  Nearest BSL (TP target): {nearest_bsl.get('price', 0):.2f} "
                f"(touches={nearest_bsl.get('touch_count', 0)})"
            )
        else:
            lines.append("  Nearest BSL: none above current price")
        if nearest_ssl:
            lines.append(
                f"  Nearest SSL (SL ref): {nearest_ssl.get('price', 0):.2f} "
                f"(touches={nearest_ssl.get('touch_count', 0)})"
            )
        else:
            lines.append("  Nearest SSL: none below current price")
        lines.append("")

        lines.append("=== ORDER BLOCKS ===")
        ob_bull = self.order_blocks.get("fresh_bullish_near")
        ob_bear = self.order_blocks.get("fresh_bearish_near")
        if ob_bull:
            lines.append(
                f"  Fresh demand (bullish OB): "
                f"[{ob_bull.get('bottom', 0):.2f} - {ob_bull.get('top', 0):.2f}]"
            )
        else:
            lines.append("  Fresh demand: none below")
        if ob_bear:
            lines.append(
                f"  Fresh supply (bearish OB): "
                f"[{ob_bear.get('bottom', 0):.2f} - {ob_bear.get('top', 0):.2f}]"
            )
        else:
            lines.append("  Fresh supply: none above")
        lines.append("")

        lines.append("=== FVG ===")
        fvg_bull = self.fvg.get("fresh_bullish_near")
        fvg_bear = self.fvg.get("fresh_bearish_near")
        if fvg_bull:
            lines.append(
                f"  Fresh bullish FVG: [{fvg_bull.get('bottom', 0):.2f} - "
                f"{fvg_bull.get('top', 0):.2f}] CE={fvg_bull.get('ce', 0):.2f}"
            )
        else:
            lines.append("  Fresh bullish FVG: none")
        if fvg_bear:
            lines.append(
                f"  Fresh bearish FVG: [{fvg_bear.get('bottom', 0):.2f} - "
                f"{fvg_bear.get('top', 0):.2f}] CE={fvg_bear.get('ce', 0):.2f}"
            )
        else:
            lines.append("  Fresh bearish FVG: none")
        lines.append("")

        lines.append("=== EVENTS ===")
        next_ev = self.events.get("next_high_impact")
        if next_ev:
            lines.append(
                f"  Next high-impact: {next_ev.get('name')} "
                f"in {next_ev.get('hours_until', 0):.1f}h "
                f"@ {next_ev.get('time')}"
            )
        else:
            lines.append("  No high-impact event in next 72h")
        lines.append(
            f"  Should avoid trading: {self.events.get('should_avoid_trading', False)} "
            f"({self.events.get('avoid_reason', '')})"
        )

        return "\n".join(lines)


class ReplayStructureProvider:
    """
    Unified context builder. Stateless, time-anchored.
    """

    def __init__(
        self,
        default_lookback: int = 200,
        fractal_n: int = 5,
        impulse_body_atr: float = 2.0,
        fvg_min_gap_atr: float = 0.30,
    ):
        self.default_lookback = default_lookback
        self.fractal_n = fractal_n
        self.impulse_body_atr = impulse_body_atr
        self.fvg_min_gap_atr = fvg_min_gap_atr
        logger.info(
            f"ReplayStructureProvider initialized | lookback={default_lookback}, "
            f"fractal_n={fractal_n}"
        )

    def build(
        self,
        ohlc_by_timeframe: Dict[str, pd.DataFrame],
        anchor_ts: datetime,
        anchor_idx_by_timeframe: Optional[Dict[str, int]] = None,
    ) -> ReplayContext:
        """
        Build unified context.

        Args:
            ohlc_by_timeframe: {"M15": df, "H1": df, "H4": df}
            anchor_ts: Time anchor (UTC recommended)
            anchor_idx_by_timeframe: Per-TF anchor index. None = last candle.

        Returns:
            ReplayContext dengan semua analyzer output.
        """
        if anchor_idx_by_timeframe is None:
            anchor_idx_by_timeframe = {}

        # Pilih primary TF (M15 priority)
        primary_tf = "M15" if "M15" in ohlc_by_timeframe else next(iter(ohlc_by_timeframe))
        primary_df = ohlc_by_timeframe[primary_tf]
        primary_idx = anchor_idx_by_timeframe.get(
            primary_tf, len(primary_df) - 1
        )

        # ── Market data (primary TF) ──
        market_data = {}
        try:
            current_price = float(primary_df["close"].iloc[primary_idx])
            market_data = {
                "current_price": current_price,
                "timeframe": primary_tf,
                "ohlc": {
                    "open": float(primary_df["open"].iloc[primary_idx]),
                    "high": float(primary_df["high"].iloc[primary_idx]),
                    "low": float(primary_df["low"].iloc[primary_idx]),
                    "close": current_price,
                },
            }
            # ATR
            slice_df = primary_df.iloc[: primary_idx + 1]
            if len(slice_df) >= 15:
                high = slice_df["high"].astype(float)
                low = slice_df["low"].astype(float)
                close = slice_df["close"].astype(float)
                tr = pd.concat(
                    [
                        (high - low),
                        (high - close.shift(1)).abs(),
                        (low - close.shift(1)).abs(),
                    ],
                    axis=1,
                ).max(axis=1)
                market_data["atr"] = float(tr.rolling(14).mean().iloc[-1])
        except Exception as exc:
            logger.warning(f"market_data extraction failed: {exc}")

        # ── Liquidity ──
        liquidity = {}
        try:
            liq = analyze_liquidity(
                primary_df,
                as_of_idx=primary_idx,
                fractal_n=self.fractal_n,
                timeframe=primary_tf,
            )
            liquidity = {
                "nearest_bsl": liq.nearest_bsl.to_dict() if liq.nearest_bsl else None,
                "nearest_ssl": liq.nearest_ssl.to_dict() if liq.nearest_ssl else None,
                "all_bsl_count": len(liq.all_bsl),
                "all_ssl_count": len(liq.all_ssl),
                "recent_sweeps": [s.to_dict() for s in liq.recent_sweeps],
                "atr": liq.atr,
            }
        except Exception as exc:
            logger.warning(f"liquidity analysis failed: {exc}")

        # ── Order blocks ──
        order_blocks = {}
        try:
            obs = detect_order_blocks(
                primary_df,
                as_of_idx=primary_idx,
                impulse_body_atr=self.impulse_body_atr,
                lookback_bars=self.default_lookback,
                timeframe=primary_tf,
            )
            order_blocks = {
                "fresh_bullish_near": obs.fresh_bullish_near.to_dict() if obs.fresh_bullish_near else None,
                "fresh_bearish_near": obs.fresh_bearish_near.to_dict() if obs.fresh_bearish_near else None,
                "mitigated_bullish_recent": obs.mitigated_bullish_recent.to_dict() if obs.mitigated_bullish_recent else None,
                "mitigated_bearish_recent": obs.mitigated_bearish_recent.to_dict() if obs.mitigated_bearish_recent else None,
                "bullish_count": len(obs.bullish_obs),
                "bearish_count": len(obs.bearish_obs),
            }
        except Exception as exc:
            logger.warning(f"order block detection failed: {exc}")

        # ── FVG ──
        fvg = {}
        try:
            fvgs = detect_fvgs(
                primary_df,
                as_of_idx=primary_idx,
                min_gap_atr=self.fvg_min_gap_atr,
                lookback_bars=self.default_lookback,
                timeframe=primary_tf,
            )
            fvg = {
                "fresh_bullish_near": fvgs.fresh_bullish_near.to_dict() if fvgs.fresh_bullish_near else None,
                "fresh_bearish_near": fvgs.fresh_bearish_near.to_dict() if fvgs.fresh_bearish_near else None,
                "mitigated_bullish_recent": fvgs.mitigated_bullish_recent.to_dict() if fvgs.mitigated_bullish_recent else None,
                "mitigated_bearish_recent": fvgs.mitigated_bearish_recent.to_dict() if fvgs.mitigated_bearish_recent else None,
                "bullish_count": len(fvgs.bullish_fvgs),
                "bearish_count": len(fvgs.bearish_fvgs),
            }
        except Exception as exc:
            logger.warning(f"fvg detection failed: {exc}")

        # ── Regime (multi-timeframe) ──
        regime = {}
        try:
            mtf = classify_multi_timeframe(
                ohlc_by_timeframe,
                as_of_idx_by_timeframe=anchor_idx_by_timeframe,
            )
            regime = mtf.to_dict()
        except Exception as exc:
            logger.warning(f"regime classification failed: {exc}")

        # ── Events ──
        events = {}
        try:
            next_ev = get_next_high_impact(anchor_ts, max_hours_ahead=72)
            avoid, reason, _ = should_avoid_trading(anchor_ts, pre_hours=2, post_hours=1)
            events = {
                "next_high_impact": next_ev.to_dict() if next_ev else None,
                "should_avoid_trading": avoid,
                "avoid_reason": reason,
            }
        except Exception as exc:
            logger.warning(f"event lookup failed: {exc}")

        return ReplayContext(
            anchor={
                "timestamp": anchor_ts.isoformat(),
                "primary_timeframe": primary_tf,
                "primary_idx": primary_idx,
            },
            market_data=market_data,
            liquidity=liquidity,
            order_blocks=order_blocks,
            fvg=fvg,
            regime=regime,
            events=events,
            metadata={
                "provider_version": "1.0.0",
                "timeframes_provided": list(ohlc_by_timeframe.keys()),
                "lookback_bars": self.default_lookback,
            },
        )


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: build full context dari synthetic data.
    """
    import numpy as np

    np.random.seed(42)
    n = 500
    base = 2000.0
    prices = base + np.cumsum(np.random.randn(n) * 0.5 + 0.2)  # slight uptrend

    df_m15 = pd.DataFrame(
        {
            "time": pd.date_range("2023-04-15", periods=n, freq="15min"),
            "open": prices + np.random.randn(n) * 0.3,
            "high": prices + abs(np.random.randn(n)) * 0.8,
            "low": prices - abs(np.random.randn(n)) * 0.8,
            "close": prices,
        }
    )

    # Subsample untuk H1, H4
    df_h1 = df_m15.iloc[::4].reset_index(drop=True)
    df_h4 = df_m15.iloc[::16].reset_index(drop=True)

    provider = ReplayStructureProvider()

    anchor_ts = df_m15["time"].iloc[400]
    if anchor_ts.tzinfo is None:
        anchor_ts = anchor_ts.to_pydatetime().replace(tzinfo=None)

    ctx = provider.build(
        ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
        anchor_ts=anchor_ts,
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )

    print("=== Replay Context (LLM prompt format) ===")
    print(ctx.to_llm_prompt_context())
    print("\n=== Raw dict keys ===")
    print(list(ctx.to_dict().keys()))
