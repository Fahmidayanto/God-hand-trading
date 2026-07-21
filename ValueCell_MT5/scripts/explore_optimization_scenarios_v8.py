"""
Explore and simulate optimization scenarios (Dynamic Lot Sizing, R:R Threshold tuning, and Dynamic Exits)
for gold trading based on v8 walk-forward (ATR-normalized) regression predictions, 2022-2026 combined
out-of-sample (every row in scored_v8_walk_forward.csv was predicted by a fold model that never trained
on that row's own year).
All metrics are base-scaled to 0.05 lot size for comparison.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORED_CSV_PATH = REPO_ROOT / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest" / "scored_v8_walk_forward.csv"


def max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    equity = values.cumsum()
    peak = equity.cummax()
    return float((equity - peak).min())


def profit_factor(values: pd.Series) -> float:
    gross_profit = float(values[values > 0].sum())
    gross_loss = abs(float(values[values < 0].sum()))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def dynamic_exit_points_pnl(row) -> float:
    p_mfe = row["predicted_mfe"]
    p_mae = row["predicted_mae"]
    act_mfe = row["mfe_target"]
    act_mae = row["mae_target"]

    if act_mae >= p_mae and act_mfe >= p_mfe:
        return -p_mae
    elif act_mae >= p_mae:
        return -p_mae
    elif act_mfe >= p_mfe:
        return p_mfe
    else:
        # actual_net_profit was computed by the EA at 0.05 lot (confirmed against
        # the live EA's real position sizing -- the LotSize=0.01 column in the raw
        # Backtest_Results CSV is a logging placeholder, not what P&L was computed at).
        return row["actual_net_profit"] / 0.05


def s5_row_profit(row, threshold: float) -> float:
    """Scenario 5's actual per-row USD profit (extended lot tier + dynamic exit) at a
    given entry threshold -- used both for the threshold grid search and the final report,
    so the threshold chosen is optimal for what actually gets reported."""
    err = row["expected_rr"]
    if err < threshold:
        return 0.0
    if err >= 3.0:
        lot = 0.10
    elif err >= 1.5:
        lot = 0.08
    elif err >= 1.2:
        lot = 0.06
    else:
        lot = 0.05
    return (dynamic_exit_points_pnl(row) / 10.0) * (lot / 0.1)


def main():
    logger.info("=== Starting Optimization Scenarios Exploration (v8, walk-forward 2022-2026 OOS) ===")

    if not SCORED_CSV_PATH.exists():
        logger.error(f"Scored dataset not found at {SCORED_CSV_PATH}. Run train_ml_prediction_v8_walk_forward_normalized.py first.")
        return 1

    df = pd.read_csv(SCORED_CSV_PATH)
    logger.info("Scored dataset loaded successfully. Total samples: {} (years: {})", len(df), sorted(df["year"].unique().tolist()))

    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)

    # Optimal R:R threshold for Scenario 5, tuned on 2022-2025 combined (validation) and
    # reported on 2022-2026 -- 2026 is held out entirely from threshold selection so it stays
    # a genuine blind test. Evaluated using Scenario 5's actual formula (extended lot tier +
    # dynamic exit), not a simplified fixed-lot profit, so the threshold chosen is optimal for
    # what's actually reported.
    val_rows = df[df["year"] <= 2025]
    best_th = 1.0
    best_val_profit = -99999.0
    logger.info("Performing R:R threshold grid search (validation years=2022-2025, S5 formula)...")
    for th in np.arange(0.8, 1.81, 0.05):
        val_profit = val_rows.apply(lambda r: s5_row_profit(r, th), axis=1).sum()
        if val_profit > best_val_profit:
            best_val_profit = val_profit
            best_th = round(float(th), 2)
    logger.info("Optimal validation R:R threshold found: {} (validation net profit: ${:.2f})", best_th, best_val_profit)

    # Scenario 4: Combined Dynamic Lot Sizing + Dynamic SL/TP Exits
    dyn_exit_dyn_lot_profits = []
    for _, row in df.iterrows():
        err = row["expected_rr"]
        if err < 1.0:
            dyn_exit_dyn_lot_profits.append(0.0)
            continue
        if err >= 1.5:
            lot = 0.08
        elif err >= 1.2:
            lot = 0.06
        else:
            lot = 0.05
        usd_profit = (dynamic_exit_points_pnl(row) / 10.0) * (lot / 0.1)
        dyn_exit_dyn_lot_profits.append(usd_profit)

    df["s4_profit"] = dyn_exit_dyn_lot_profits
    s4_active = df[df["expected_rr"] >= 1.0]

    # Scenario 5: All entries + Optimized Threshold + Extended Lot Tier (no BoS-only filter)
    df["s5_profit"] = df.apply(lambda r: s5_row_profit(r, best_th), axis=1)
    s5_active = df[df["expected_rr"] >= best_th]

    # -------------------------------------------------------------
    # COMBINED 2022-2026 REPORT
    # -------------------------------------------------------------
    scenarios = [
        ("Scenario 4: Combined Dynamic Lot + Dynamic Exit", s4_active["s4_profit"]),
        (f"Scenario 5: Opt Th (R:R>={best_th}) + Ext Lot (all entries)", s5_active["s5_profit"]),
    ]

    records = []
    print("\n" + "=" * 95)
    print(f"{'Trading Strategy Scenario (0.05 lot base) [v8, 2022-2026 combined]':50} | {'Trades':6} | {'Win Rate':8} | {'Net Profit':10} | {'Profit Factor':13} | {'Max DD'}")
    print("=" * 95)
    for name, returns in scenarios:
        win_rate = (returns > 0).mean() if len(returns) else 0.0
        pf = profit_factor(returns)
        dd = max_drawdown(returns)
        print(f"{name:50} | {len(returns):6} | {win_rate:8.1%} | ${returns.sum():9.2f} | {pf:13.2f} | ${dd:.2f}")
        records.append({
            "scope": "2022-2026 combined", "scenario": name, "trades": len(returns),
            "win_rate": win_rate, "net_profit": returns.sum(), "profit_factor": pf, "max_drawdown": dd,
        })
    print("=" * 95 + "\n")

    # -------------------------------------------------------------
    # PER-YEAR BREAKDOWN
    # -------------------------------------------------------------
    print("=" * 95)
    print(f"{'Per-year breakdown':50} | {'Trades':6} | {'Win Rate':8} | {'Net Profit':10} | {'Profit Factor':13} | {'Max DD'}")
    print("=" * 95)
    for year in sorted(df["year"].unique()):
        s4_year = s4_active[s4_active["year"] == year]["s4_profit"]
        s5_year = s5_active[s5_active["year"] == year]["s5_profit"]
        for label, returns in [(f"S4 - {year}", s4_year), (f"S5 - {year}", s5_year)]:
            win_rate = (returns > 0).mean() if len(returns) else 0.0
            pf = profit_factor(returns)
            dd = max_drawdown(returns)
            print(f"{label:50} | {len(returns):6} | {win_rate:8.1%} | ${returns.sum():9.2f} | {pf:13.2f} | ${dd:.2f}")
            records.append({
                "scope": str(year), "scenario": label.split(" - ")[0], "trades": len(returns),
                "win_rate": win_rate, "net_profit": returns.sum(), "profit_factor": pf, "max_drawdown": dd,
            })
    print("=" * 95 + "\n")

    output_path = SCORED_CSV_PATH.parent / "optimization_scenarios_report_v8.csv"
    pd.DataFrame(records).to_csv(output_path, index=False)
    logger.info("Optimization report saved to {}", output_path)


if __name__ == "__main__":
    main()
