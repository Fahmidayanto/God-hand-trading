"""
A/B Test Harness - Compare SmartRuleEngine vs LLMDecisionEngine

Jalankan kedua engine paralel di synthetic 2023 XAUUSD trades, hitung:
- Win rate per engine
- Average R:R achieved
- Profit factor (gross profit / gross loss)
- Per-regime breakdown (trending vs ranging)
- Per-event-proximity breakdown (pre/during/post high-impact event)

Mode:
- DRY_RUN: pakai mock LLM (deterministic, free, fast)
- LIVE: real LLM call (cost, slow, but actual reasoning)

PENTING:
- Time-anchored: setiap decision hanya pakai data s.d. entry timestamp
- No look-ahead: simulasi exit dari candle setelah entry
- Same OHLC untuk kedua engine (apples-to-apples)

Output: Markdown report ke stdout.

Ponytail:
- Stateless, no DB write
- Configurable N trades, seed, mode
- Reuse SmartRuleEngine + LLMDecisionEngine (no duplicate logic)
"""

from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from loguru import logger

# Setup imports
try:
    from ..analyzers.replay_structure_provider import ReplayStructureProvider
    from .smart_rule_engine import SmartRuleEngine, TradeSetup, Signal
except ImportError:
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from verification_system.analyzers.replay_structure_provider import ReplayStructureProvider
    from verification_system.decision_engines.smart_rule_engine import SmartRuleEngine, TradeSetup, Signal


# ── Trade result dataclass ─────────────────────────────────────────────────

@dataclass
class TradeResult:
    """One simulated trade with outcome."""
    engine_name: str
    trade_idx: int
    entry_time: datetime
    entry_price: float
    sl: float
    tp1: float
    tp2: Optional[float]
    signal: str
    confidence: float
    regime: str
    # Outcome
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""  # "tp1" | "tp2" | "sl" | "no_exit"
    pnl: float = 0.0  # in R units (1.0 = 1R profit, -1.0 = 1R loss)
    r_achieved: float = 0.0  # actual R achieved
    # Meta
    event_proximity: str = "none"  # "pre_event" | "post_event" | "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine_name,
            "trade_idx": self.trade_idx,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "signal": self.signal,
            "confidence": self.confidence,
            "regime": self.regime,
            "exit_reason": self.exit_reason,
            "pnl_r": self.pnl,
            "r_achieved": self.r_achieved,
            "event_proximity": self.event_proximity,
        }


# ── Synthetic 2023 OHLC generator ──────────────────────────────────────────

def generate_synthetic_2023_ohlc(
    symbol: str = "XAUUSD",
    n_candles: int = 5000,
    start_date: str = "2023-01-02",
    freq: str = "15min",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLC untuk 2023 dengan multiple regimes.
    Realistic: trending periods, ranging periods, volatility clusters.
    """
    np.random.seed(seed)
    n = n_candles
    base = 1900.0

    # Build price dengan regime switches
    prices = np.zeros(n)
    prices[0] = base
    regime = 0  # 0=trending, 1=ranging, 2=volatile

    for i in range(1, n):
        # Regime switch probability per 200 candles
        if i % 200 == 0 and np.random.rand() < 0.5:
            regime = np.random.choice([0, 1, 2])
        if regime == 0:
            drift = 0.05
            vol = 1.0
        elif regime == 1:
            drift = 0.0
            vol = 0.5
            # Mean reversion
            prices[i - 1] = prices[i - 1] * 0.998 + base * 0.002
        else:
            drift = 0.0
            vol = 2.0
        shock = np.random.randn() * vol
        prices[i] = prices[i - 1] + drift + shock

    # OHLC
    df = pd.DataFrame(
        {
            "time": pd.date_range(start_date, periods=n, freq=freq),
            "open": prices + np.random.randn(n) * 0.3,
            "high": prices + abs(np.random.randn(n)) * 0.8,
            "low": prices - abs(np.random.randn(n)) * 0.8,
            "close": prices,
        }
    )
    return df


# ── Mock LLM (deterministic, for dry-run) ──────────────────────────────────

def mock_llm_decide(context, rule_setup: TradeSetup) -> TradeSetup:
    """
    Mock LLM yang模仿 rule engine dengan sedikit variation.

    Untuk A/B test dry-run: LLM produces similar tapi slightly different setups
    (simulating the variability of real LLM).
    """
    if rule_setup.signal == Signal.BLOCKED or rule_setup.signal == Signal.HOLD:
        return rule_setup

    # Add small perturbation (LLM "thinking" variance)
    entry = rule_setup.entry_price
    sl_offset = random.uniform(0.95, 1.05)  # ±5% SL width
    tp_offset = random.uniform(0.95, 1.10)  # +5%/+10% TP
    confidence_adj = random.uniform(0.85, 1.10)  # ±15% confidence

    if rule_setup.signal == Signal.BUY:
        sl = entry - abs(entry - rule_setup.sl) * sl_offset
        tp1 = entry + abs(rule_setup.tp1 - entry) * tp_offset
        tp2 = rule_setup.tp2 * tp_offset if rule_setup.tp2 else None
    else:  # SELL
        sl = entry + abs(rule_setup.sl - entry) * sl_offset
        tp1 = entry - abs(entry - rule_setup.tp1) * tp_offset
        tp2 = rule_setup.tp2 * tp_offset if rule_setup.tp2 else None

    return TradeSetup(
        signal=rule_setup.signal,
        entry_price=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        lot_size=rule_setup.lot_size,
        risk_pct=rule_setup.risk_pct,
        confidence=min(1.0, max(0.0, rule_setup.confidence * confidence_adj)),
        reasoning=f"[MOCK LLM] variant of rule-based: {rule_setup.reasoning[:200]}",
        confluences=rule_setup.confluences + ["llm_variant"],
        filters_applied=["mock_llm"],
    )


# ── Trade simulator ────────────────────────────────────────────────────────

def simulate_trade_outcome(
    setup: TradeSetup,
    entry_idx: int,
    ohlc: pd.DataFrame,
    max_candles: int = 100,  # exit setelah N candle jika tidak hit SL/TP
) -> TradeResult:
    """
    Simulate trade outcome: walk forward dari entry_idx, check SL vs TP.

    Returns TradeResult dengan exit_reason dan PnL dalam R units.
    """
    if setup.signal not in (Signal.BUY, Signal.SELL):
        return TradeResult(
            engine_name="",
            trade_idx=0,
            entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
            entry_price=ohlc["close"].iloc[entry_idx],
            sl=setup.sl,
            tp1=setup.tp1,
            tp2=setup.tp2,
            signal=setup.signal.value,
            confidence=setup.confidence,
            regime="unknown",
            exit_reason="no_trade",
            pnl=0.0,
            r_achieved=0.0,
        )

    entry_price = ohlc["close"].iloc[entry_idx]
    risk_distance = abs(entry_price - setup.sl)
    if risk_distance <= 0:
        return TradeResult(
            engine_name="",
            trade_idx=0,
            entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
            entry_price=entry_price,
            sl=setup.sl,
            tp1=setup.tp1,
            tp2=setup.tp2,
            signal=setup.signal.value,
            confidence=setup.confidence,
            regime="unknown",
            exit_reason="invalid_sl",
            pnl=0.0,
            r_achieved=0.0,
        )

    # Walk forward
    for j in range(entry_idx + 1, min(entry_idx + max_candles, len(ohlc))):
        candle = ohlc.iloc[j]
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        if setup.signal == Signal.BUY:
            # Check SL first (conservative)
            if low <= setup.sl:
                pnl = -1.0  # -1R
                return TradeResult(
                    engine_name="",
                    trade_idx=0,
                    entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
                    entry_price=entry_price,
                    sl=setup.sl,
                    tp1=setup.tp1,
                    tp2=setup.tp2,
                    signal=setup.signal.value,
                    confidence=setup.confidence,
                    regime="unknown",
                    exit_time=pd.Timestamp(candle["time"]).to_pydatetime(),
                    exit_price=setup.sl,
                    exit_reason="sl",
                    pnl=-1.0,
                    r_achieved=-1.0,
                )
            # Check TP1
            if high >= setup.tp1:
                reward = abs(setup.tp1 - entry_price)
                r_achieved = reward / risk_distance
                return TradeResult(
                    engine_name="",
                    trade_idx=0,
                    entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
                    entry_price=entry_price,
                    sl=setup.sl,
                    tp1=setup.tp1,
                    tp2=setup.tp2,
                    signal=setup.signal.value,
                    confidence=setup.confidence,
                    regime="unknown",
                    exit_time=pd.Timestamp(candle["time"]).to_pydatetime(),
                    exit_price=setup.tp1,
                    exit_reason="tp1",
                    pnl=r_achieved,
                    r_achieved=r_achieved,
                )

        else:  # SELL
            if high >= setup.sl:
                return TradeResult(
                    engine_name="",
                    trade_idx=0,
                    entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
                    entry_price=entry_price,
                    sl=setup.sl,
                    tp1=setup.tp1,
                    tp2=setup.tp2,
                    signal=setup.signal.value,
                    confidence=setup.confidence,
                    regime="unknown",
                    exit_time=pd.Timestamp(candle["time"]).to_pydatetime(),
                    exit_price=setup.sl,
                    exit_reason="sl",
                    pnl=-1.0,
                    r_achieved=-1.0,
                )
            if low <= setup.tp1:
                reward = abs(entry_price - setup.tp1)
                r_achieved = reward / risk_distance
                return TradeResult(
                    engine_name="",
                    trade_idx=0,
                    entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
                    entry_price=entry_price,
                    sl=setup.sl,
                    tp1=setup.tp1,
                    tp2=setup.tp2,
                    signal=setup.signal.value,
                    confidence=setup.confidence,
                    regime="unknown",
                    exit_time=pd.Timestamp(candle["time"]).to_pydatetime(),
                    exit_price=setup.tp1,
                    exit_reason="tp1",
                    pnl=r_achieved,
                    r_achieved=r_achieved,
                )

    # No exit within max_candles
    close_at_end = float(ohlc["close"].iloc[min(entry_idx + max_candles, len(ohlc) - 1)])
    if setup.signal == Signal.BUY:
        unrealized = close_at_end - entry_price
    else:
        unrealized = entry_price - close_at_end
    r_achieved = unrealized / risk_distance
    return TradeResult(
        engine_name="",
        trade_idx=0,
        entry_time=ohlc["time"].iloc[entry_idx].to_pydatetime(),
        entry_price=entry_price,
        sl=setup.sl,
        tp1=setup.tp1,
        tp2=setup.tp2,
        signal=setup.signal.value,
        confidence=setup.confidence,
        regime="unknown",
        exit_time=ohlc["time"].iloc[min(entry_idx + max_candles, len(ohlc) - 1)].to_pydatetime(),
        exit_price=close_at_end,
        exit_reason="timeout",
        pnl=r_achieved,
        r_achieved=r_achieved,
    )


# ── Aggregate metrics ──────────────────────────────────────────────────────

def aggregate_metrics(results: List[TradeResult], engine_name: str) -> Dict[str, Any]:
    """Compute aggregate metrics dari list of TradeResult."""
    trades = [r for r in results if r.signal in ("BUY", "SELL")]
    if not trades:
        return {
            "engine": engine_name,
            "n_trades": 0,
            "win_rate_pct": 0.0,
            "avg_r": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_r": 0.0,
            "total_r": 0.0,
        }

    wins = [r for r in trades if r.pnl > 0]
    losses = [r for r in trades if r.pnl <= 0]
    win_rate = len(wins) / len(trades) * 100
    avg_r = sum(r.pnl for r in trades) / len(trades)
    gross_profit = sum(r.pnl for r in wins) if wins else 0.0
    gross_loss = abs(sum(r.pnl for r in losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown (running sum)
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in trades:
        cumulative += r.pnl
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)

    return {
        "engine": engine_name,
        "n_trades": len(trades),
        "win_rate_pct": round(win_rate, 1),
        "avg_r": round(avg_r, 3),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "max_drawdown_r": round(max_dd, 2),
        "total_r": round(sum(r.pnl for r in trades), 2),
    }


def metrics_by_regime(results: List[TradeResult]) -> Dict[str, Dict[str, Any]]:
    """Per-regime breakdown."""
    by_regime: Dict[str, List[TradeResult]] = {}
    for r in results:
        if r.signal not in ("BUY", "SELL"):
            continue
        by_regime.setdefault(r.regime, []).append(r)
    out = {}
    for regime, trades in by_regime.items():
        if not trades:
            continue
        wins = [r for r in trades if r.pnl > 0]
        out[regime] = {
            "n": len(trades),
            "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
            "avg_r": round(sum(r.pnl for r in trades) / len(trades), 3),
            "total_r": round(sum(r.pnl for r in trades), 2),
        }
    return out


# ── A/B test runner ────────────────────────────────────────────────────────

def run_ab_test(
    n_trades: int = 50,
    min_idx: int = 300,
    seed: int = 42,
    dry_run_llm: bool = True,
) -> Dict[str, Any]:
    """
    Run A/B test: SmartRuleEngine vs LLMDecisionEngine pada synthetic 2023.

    Args:
        n_trades: jumlah trade yang akan di-test
        min_idx: minimum candle index (skip early candles, butuh lookback)
        seed: random seed untuk reproducibility
        dry_run_llm: True = mock LLM, False = real LLM call (butuh API key)

    Returns:
        Dict dengan metrics untuk kedua engine + per-regime breakdown
    """
    random.seed(seed)
    np.random.seed(seed)

    logger.info(f"Generating synthetic 2023 OHLC...")
    df_m15 = generate_synthetic_2023_ohlc(n_candles=5000, seed=seed)
    df_h1 = df_m15.iloc[::4].reset_index(drop=True)
    df_h4 = df_m15.iloc[::16].reset_index(drop=True)

    # Sample N trade entry points secara random (dari min_idx ke akhir - 100)
    available = list(range(min_idx, len(df_m15) - 100))
    entry_indices = sorted(random.sample(available, min(n_trades, len(available))))
    logger.info(f"Sampled {len(entry_indices)} trade entry points")

    # Engines
    provider = ReplayStructureProvider()
    rule_engine = SmartRuleEngine(balance=1000.0, risk_pct=1.0)

    rule_results: List[TradeResult] = []
    llm_results: List[TradeResult] = []

    for trade_idx, entry_idx in enumerate(entry_indices):
        anchor_ts = df_m15["time"].iloc[entry_idx].to_pydatetime()
        if anchor_ts.tzinfo is None:
            anchor_ts = anchor_ts.replace(tzinfo=timezone.utc)

        # Slice H1/H4 indices proportional
        h1_idx = entry_idx // 4
        h4_idx = entry_idx // 16

        try:
            ctx = provider.build(
                ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
                anchor_ts=anchor_ts,
                anchor_idx_by_timeframe={"M15": entry_idx, "H1": h1_idx, "H4": h4_idx},
            )
        except Exception as exc:
            logger.warning(f"Trade {trade_idx}: context build failed: {exc}")
            continue

        # ── SmartRuleEngine ──
        rule_setup = rule_engine.decide(ctx)
        rule_outcome = simulate_trade_outcome(rule_setup, entry_idx, df_m15)
        rule_outcome.engine_name = "SmartRuleEngine"
        rule_outcome.trade_idx = trade_idx
        rule_outcome.regime = (ctx.regime or {}).get("overall_regime", "unknown")
        # Event proximity
        if (ctx.events or {}).get("should_avoid_trading"):
            rule_outcome.event_proximity = "pre_event"
        elif (ctx.events or {}).get("next_high_impact"):
            hours = (ctx.events["next_high_impact"].get("hours_until") if isinstance(ctx.events["next_high_impact"], dict) else 0) or 0
            if hours < 6:
                rule_outcome.event_proximity = "near_event"
            else:
                rule_outcome.event_proximity = "none"
        rule_results.append(rule_outcome)

        # ── LLMDecisionEngine ──
        if dry_run_llm:
            llm_setup = mock_llm_decide(ctx, rule_setup)
        else:
            from verification_system.decision_engines.llm_decision_engine import LLMDecisionEngine
            llm_engine = LLMDecisionEngine(balance=1000.0)
            llm_setup = llm_engine.decide(ctx)

        llm_outcome = simulate_trade_outcome(llm_setup, entry_idx, df_m15)
        llm_outcome.engine_name = "LLMDecisionEngine" if not dry_run_llm else "LLM(mock)"
        llm_outcome.trade_idx = trade_idx
        llm_outcome.regime = (ctx.regime or {}).get("overall_regime", "unknown")
        llm_outcome.event_proximity = rule_outcome.event_proximity
        llm_results.append(llm_outcome)

    # Aggregate
    rule_metrics = aggregate_metrics(rule_results, "SmartRuleEngine")
    llm_metrics = aggregate_metrics(llm_results, "LLMDecisionEngine" if not dry_run_llm else "LLM(mock)")

    return {
        "n_trades_sampled": len(entry_indices),
        "rule_metrics": rule_metrics,
        "llm_metrics": llm_metrics,
        "rule_by_regime": metrics_by_regime(rule_results),
        "llm_by_regime": metrics_by_regime(llm_results),
        "rule_results": [r.to_dict() for r in rule_results],
        "llm_results": [r.to_dict() for r in llm_results],
    }


# ── Report formatter ───────────────────────────────────────────────────────

def format_report(result: Dict[str, Any]) -> str:
    """Format A/B test result sebagai Markdown."""
    lines = []
    lines.append("=" * 60)
    lines.append("# A/B Test Report: SmartRuleEngine vs LLM Decision Engine")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Trades sampled: {result['n_trades_sampled']}")
    lines.append("")

    lines.append("## Overall Metrics")
    lines.append("")
    lines.append("| Metric | SmartRuleEngine | LLM Decision Engine | Winner |")
    lines.append("|---|---|---|---|")
    rm = result["rule_metrics"]
    lm = result["llm_metrics"]

    def winner(a, b, higher_is_better=True):
        if a == b:
            return "tie"
        if higher_is_better:
            return "Rule" if a > b else "LLM"
        return "Rule" if a < b else "LLM"

    wr_winner = winner(rm["win_rate_pct"], lm["win_rate_pct"])
    avg_r_winner = winner(rm["avg_r"], lm["avg_r"])
    pf_rule = rm["profit_factor"] if rm["profit_factor"] != "inf" else 999.99
    pf_llm = lm["profit_factor"] if lm["profit_factor"] != "inf" else 999.99
    pf_winner = winner(pf_rule, pf_llm)
    dd_winner = winner(rm["max_drawdown_r"], lm["max_drawdown_r"], higher_is_better=False)

    lines.append(f"| Win rate % | {rm['win_rate_pct']} | {lm['win_rate_pct']} | {wr_winner} |")
    lines.append(f"| Avg R | {rm['avg_r']} | {lm['avg_r']} | {avg_r_winner} |")
    lines.append(f"| Profit factor | {rm['profit_factor']} | {lm['profit_factor']} | {pf_winner} |")
    lines.append(f"| Max drawdown (R) | {rm['max_drawdown_r']} | {lm['max_drawdown_r']} | {dd_winner} |")
    lines.append(f"| Total R | {rm['total_r']} | {lm['total_r']} | - |")
    lines.append("")

    # Per-regime breakdown
    lines.append("## Per-Regime Breakdown")
    lines.append("")
    regimes = set(result["rule_by_regime"].keys()) | set(result["llm_by_regime"].keys())
    for regime in sorted(regimes):
        r_data = result["rule_by_regime"].get(regime, {})
        l_data = result["llm_by_regime"].get(regime, {})
        lines.append(f"### Regime: {regime}")
        lines.append(f"- SmartRule: n={r_data.get('n', 0)}, win%={r_data.get('win_rate_pct', 0)}, "
                     f"avg_R={r_data.get('avg_r', 0)}, total_R={r_data.get('total_r', 0)}")
        lines.append(f"- LLM:        n={l_data.get('n', 0)}, win%={l_data.get('win_rate_pct', 0)}, "
                     f"avg_R={l_data.get('avg_r', 0)}, total_R={l_data.get('total_r', 0)}")
        lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    rule_wins = sum(1 for w in [wr_winner, avg_r_winner, pf_winner] if w == "Rule")
    llm_wins = sum(1 for w in [wr_winner, avg_r_winner, pf_winner] if w == "LLM")
    if rule_wins > llm_wins:
        lines.append(f"**SmartRuleEngine outperforms** in {rule_wins}/3 primary metrics.")
    elif llm_wins > rule_wins:
        lines.append(f"**LLM Decision Engine outperforms** in {llm_wins}/3 primary metrics.")
    else:
        lines.append("**Tie** — no clear winner in primary metrics.")
    lines.append("")

    return "\n".join(lines)


# ── CLI entrypoint ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    n = int(os.getenv("N_TRADES", "50"))
    dry = os.getenv("DRY_RUN", "1") == "1"

    print(f"Running A/B test: n={n}, dry_run_llm={dry}")
    print()

    result = run_ab_test(n_trades=n, dry_run_llm=dry)
    print(format_report(result))

    # Optionally save JSON
    if os.getenv("SAVE_JSON"):
        out_path = os.getenv("SAVE_JSON")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull results saved to: {out_path}")
