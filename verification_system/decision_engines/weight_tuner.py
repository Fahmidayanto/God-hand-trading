"""
Weight Tuner - Sweep SmartRuleEngine weights untuk find optimal config.

Menguji beberapa weight configuration untuk confluence scoring di
SmartRuleEngine, jalankan A/B test pada synthetic 2023, pilih yang
menghasilkan avg_R tertinggi.

Tunable weights:
- w_ob_fresh: weight untuk fresh OB (default 0.30)
- w_ob_mitigated: weight untuk mitigated OB (default 0.15)
- w_fvg_fresh: weight untuk fresh FVG (default 0.20)
- w_liquidity: weight untuk liquidity target (default 0.20)
- w_regime: weight untuk regime alignment (default 0.30)
- min_signal_score: minimum score untuk take trade (default 0.30)

Ponytail: deterministic, no LLM cost, fast iteration.
"""

from __future__ import annotations

import os
import sys
import json
import random
from dataclasses import dataclass
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from loguru import logger

# Setup imports
try:
    from ..analyzers.replay_structure_provider import ReplayStructureProvider
    from .smart_rule_engine import SmartRuleEngine, TradeSetup, Signal
    from .ab_test_harness import (
        generate_synthetic_2023_ohlc,
        simulate_trade_outcome,
        aggregate_metrics,
    )
except ImportError:
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from verification_system.analyzers.replay_structure_provider import ReplayStructureProvider
    from verification_system.decision_engines.smart_rule_engine import SmartRuleEngine, TradeSetup, Signal
    from verification_system.decision_engines.ab_test_harness import (
        generate_synthetic_2023_ohlc,
        simulate_trade_outcome,
        aggregate_metrics,
    )


# ── Weight config ──────────────────────────────────────────────────────────

@dataclass
class WeightConfig:
    name: str
    w_ob_fresh: float = 0.30
    w_ob_mitigated: float = 0.15
    w_fvg_fresh: float = 0.20
    w_liquidity: float = 0.20
    w_regime: float = 0.30
    min_signal_score: float = 0.30

    def to_dict(self) -> Dict[str, float]:
        return {
            "w_ob_fresh": self.w_ob_fresh,
            "w_ob_mitigated": self.w_ob_mitigated,
            "w_fvg_fresh": self.w_fvg_fresh,
            "w_liquidity": self.w_liquidity,
            "w_regime": self.w_regime,
            "min_signal_score": self.min_signal_score,
        }


# Default weight configurations to test
DEFAULT_CONFIGS: List[WeightConfig] = [
    WeightConfig(name="default"),
    WeightConfig(
        name="ob_heavy",
        w_ob_fresh=0.40,
        w_ob_mitigated=0.20,
        w_fvg_fresh=0.15,
        w_liquidity=0.15,
        w_regime=0.10,
        min_signal_score=0.40,
    ),
    WeightConfig(
        name="fvg_heavy",
        w_ob_fresh=0.15,
        w_ob_mitigated=0.10,
        w_fvg_fresh=0.40,
        w_liquidity=0.20,
        w_regime=0.15,
        min_signal_score=0.35,
    ),
    WeightConfig(
        name="liquidity_heavy",
        w_ob_fresh=0.15,
        w_ob_mitigated=0.10,
        w_fvg_fresh=0.15,
        w_liquidity=0.40,
        w_regime=0.20,
        min_signal_score=0.35,
    ),
    WeightConfig(
        name="regime_strict",
        w_ob_fresh=0.20,
        w_ob_mitigated=0.10,
        w_fvg_fresh=0.15,
        w_liquidity=0.15,
        w_regime=0.40,
        min_signal_score=0.50,
    ),
    WeightConfig(
        name="loose_filter",
        w_ob_fresh=0.20,
        w_ob_mitigated=0.10,
        w_fvg_fresh=0.15,
        w_liquidity=0.15,
        w_regime=0.20,
        min_signal_score=0.20,
    ),
]


# ── Tuned engine (wraps SmartRuleEngine with custom weights) ───────────────

class TunedRuleEngine(SmartRuleEngine):
    """SmartRuleEngine dengan customizable confluence weights."""

    def __init__(self, weights: WeightConfig, **kwargs):
        super().__init__(**kwargs)
        self.weights = weights

    def _direction(self, context, regime, confluences):
        """Override parent method dengan custom weights."""
        from verification_system.decision_engines.smart_rule_engine import Signal

        ob = context.order_blocks or {}
        fvg = context.fvg or {}
        liq = context.liquidity or {}

        score_buy = 0.0
        score_sell = 0.0
        reasons = []
        w = self.weights

        if ob.get("fresh_bullish_near"):
            score_buy += w.w_ob_fresh
            confluences.append("OB_demand_below")
        if ob.get("fresh_bearish_near"):
            score_sell += w.w_ob_fresh
            confluences.append("OB_supply_above")
        if ob.get("mitigated_bullish_recent"):
            score_buy += w.w_ob_mitigated
        if ob.get("mitigated_bearish_recent"):
            score_sell += w.w_ob_mitigated

        if fvg.get("fresh_bullish_near"):
            score_buy += w.w_fvg_fresh
            confluences.append("FVG_bullish_below")
        if fvg.get("fresh_bearish_near"):
            score_sell += w.w_fvg_fresh
            confluences.append("FVG_bearish_above")

        if liq.get("nearest_bsl"):
            score_buy += w.w_liquidity
        if liq.get("nearest_ssl"):
            score_sell += w.w_liquidity

        if regime == "trending_up":
            score_buy += w.w_regime
            confluences.append("regime_trending_up")
        elif regime == "trending_down":
            score_sell += w.w_regime
            confluences.append("regime_trending_down")

        signal = Signal.HOLD
        direction_conf = max(score_buy, score_sell)
        if score_buy > score_sell and score_buy >= w.min_signal_score:
            signal = Signal.BUY
            reasons.append(f"BUY score={score_buy:.2f}")
        elif score_sell > score_buy and score_sell >= w.min_signal_score:
            signal = Signal.SELL
            reasons.append(f"SELL score={score_sell:.2f}")
        else:
            reasons.append(f"No direction (buy={score_buy:.2f}, sell={score_sell:.2f})")
            direction_conf = 0.0

        return signal, min(1.0, direction_conf), reasons


# ── Sweep runner ───────────────────────────────────────────────────────────

def run_sweep(
    configs: List[WeightConfig],
    n_trades: int = 30,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Jalankan setiap weight config dan return ranked results.
    """
    random.seed(seed)
    np.random.seed(seed)

    logger.info("Generating synthetic 2023 OHLC...")
    df_m15 = generate_synthetic_2023_ohlc(n_candles=5000, seed=seed)
    df_h1 = df_m15.iloc[::4].reset_index(drop=True)
    df_h4 = df_m15.iloc[::16].reset_index(drop=True)

    available = list(range(300, len(df_m15) - 100))
    entry_indices = sorted(random.sample(available, min(n_trades, len(available))))
    logger.info(f"Sampled {len(entry_indices)} trade entry points")

    provider = ReplayStructureProvider()
    results = []

    for config in configs:
        engine = TunedRuleEngine(weights=config, balance=1000.0)
        config_results = []

        for trade_idx, entry_idx in enumerate(entry_indices):
            anchor_ts = df_m15["time"].iloc[entry_idx].to_pydatetime()
            if anchor_ts.tzinfo is None:
                from datetime import timezone
                anchor_ts = anchor_ts.replace(tzinfo=timezone.utc)

            try:
                ctx = provider.build(
                    ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
                    anchor_ts=anchor_ts,
                    anchor_idx_by_timeframe={"M15": entry_idx, "H1": entry_idx // 4, "H4": entry_idx // 16},
                )
            except Exception:
                continue

            setup = engine.decide(ctx)
            outcome = simulate_trade_outcome(setup, entry_idx, df_m15)
            outcome.engine_name = f"Tuned-{config.name}"
            outcome.trade_idx = trade_idx
            outcome.regime = (ctx.regime or {}).get("overall_regime", "unknown")
            config_results.append(outcome)

        metrics = aggregate_metrics(config_results, f"Tuned-{config.name}")
        results.append({
            "config_name": config.name,
            "weights": config.to_dict(),
            "metrics": metrics,
        })
        logger.info(
            f"Config '{config.name}': "
            f"win%={metrics['win_rate_pct']}, "
            f"avg_R={metrics['avg_r']}, "
            f"total_R={metrics['total_r']}"
        )

    # Sort by avg_R (best first)
    results.sort(key=lambda r: r["metrics"]["avg_r"], reverse=True)
    return results


# ── Report ─────────────────────────────────────────────────────────────────

def format_sweep_report(results: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("# Weight Tuning Sweep Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append("| Rank | Config | Win % | Avg R | Total R | Profit Factor | Max DD |")
    lines.append("|---|---|---|---|---|---|---|")

    for rank, r in enumerate(results, 1):
        m = r["metrics"]
        lines.append(
            f"| {rank} | {r['config_name']} | {m['win_rate_pct']} | "
            f"{m['avg_r']} | {m['total_r']} | {m['profit_factor']} | "
            f"{m['max_drawdown_r']} |"
        )
    lines.append("")

    best = results[0]
    lines.append("## Best Configuration")
    lines.append("")
    lines.append(f"**{best['config_name']}**")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(best["weights"], indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    n = int(os.getenv("N_TRADES", "30"))
    seed = int(os.getenv("SEED", "42"))

    print(f"Sweeping {len(DEFAULT_CONFIGS)} weight configs, n={n} trades, seed={seed}")
    print()
    results = run_sweep(DEFAULT_CONFIGS, n_trades=n, seed=seed)
    print(format_sweep_report(results))
