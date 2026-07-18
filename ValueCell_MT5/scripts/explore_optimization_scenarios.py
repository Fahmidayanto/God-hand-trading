"""
Explore and simulate optimization scenarios (Dynamic Lot Sizing, R:R Threshold tuning, and Dynamic Exits)
for gold trading based on unconstrained regression v5 predictions.
All metrics are base-scaled to 0.05 lot size for comparison.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORED_CSV_PATH = REPO_ROOT / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest" / "scored_v5_unconstrained.csv"
STRUCTURE_LOG_GLOB = str(REPO_ROOT / "Backtest_result" / "LLHHBOSData_XAUUSD_*.csv")


def build_bos_cycle_table() -> pd.DataFrame:
    """Parse market structure event logs and number each BoS by its cycle
    since the last CHoCH (1 = first BoS after a CHoCH, 2 = the next one, etc.)."""
    frames = []
    for path in sorted(glob.glob(STRUCTURE_LOG_GLOB)):
        raw = pd.read_csv(path, skiprows=1)
        raw.columns = [c.strip() for c in raw.columns]
        frames.append(raw)
    events = pd.concat(frames, ignore_index=True).drop_duplicates()
    events["Time"] = pd.to_datetime(events["Time"], format="%Y.%m.%d %H:%M:%S")
    events = events[events["Type"].isin(["BoS", "CHoCH"])].sort_values("Time")

    cycle = 0
    rows = []
    for _, row in events.iterrows():
        if row["Type"] == "CHoCH":
            cycle = 0
        else:
            cycle += 1
            rows.append({"entry_time": row["Time"].strftime("%Y-%m-%d %H:%M:%S"), "cycle": cycle})
    return pd.DataFrame(rows).drop_duplicates(subset="entry_time")


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


def main():
    logger.info("=== Starting Optimization Scenarios Exploration ===")
    
    if not SCORED_CSV_PATH.exists():
        logger.error(f"Scored dataset not found at {SCORED_CSV_PATH}")
        return 1
        
    df = pd.read_csv(SCORED_CSV_PATH)
    logger.info("Scored dataset loaded successfully. Total samples: {}", len(df))
    
    # Calculate Expected R:R (MFE / MAE)
    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)
    
    # Scale base profit to 0.05 lot size (original profit in scored CSV is set at 0.1 lot base)
    df["profit_0_05"] = df["actual_net_profit"] * 0.5
    
    records = []
    
    # -------------------------------------------------------------
    # BASELINE SCENARIOS (0.05 lot)
    # -------------------------------------------------------------
    # Scenario 0.1: MS Baseline (No Filters)
    ms_only = df["profit_0_05"]
    
    # Scenario 0.2: ML Filter Only (R:R >= 1.0)
    ml_only = df[df["expected_rr"] >= 1.0]["profit_0_05"]
    
    # Scenario 0.3: ML + EA Combined Filter (R:R >= 1.0 + body_ratio >= 0.5)
    ml_ea = df[(df["expected_rr"] >= 1.0) & (df["body_ratio"] >= 0.5)]["profit_0_05"]
    
    # -------------------------------------------------------------
    # OPTIMIZATION SCENARIOS (0.05 lot base)
    # -------------------------------------------------------------
    
    # Scenario 1: Dynamic Lot Sizing
    # If expected_rr >= 1.5 -> Scale lot from 0.05 to 0.08 lot (1.6x multiplier)
    # If expected_rr >= 1.2 -> Scale lot from 0.05 to 0.06 lot (1.2x multiplier)
    # If expected_rr < 1.0  -> Filter (HOLD)
    # Otherwise             -> 0.05 lot
    dyn_lots = []
    dyn_profits = []
    for _, row in df.iterrows():
        err = row["expected_rr"]
        if err < 1.0:
            lot = 0.0
        elif err >= 1.5:
            lot = 0.08
        elif err >= 1.2:
            lot = 0.06
        else:
            lot = 0.05
            
        dyn_lots.append(lot)
        # Scale original profit (0.1 lot base) to the dynamic lot
        dyn_profits.append(row["actual_net_profit"] * (lot / 0.1))
        
    df["dyn_lot"] = dyn_lots
    df["dyn_profit"] = dyn_profits
    dyn_lot_active = df[df["dyn_lot"] > 0]["dyn_profit"]
    
    # Scenario 2: Optimized R:R Threshold Tuning
    # Find the best threshold by searching from 0.8 to 1.8 on the validation set (2025)
    best_th = 1.0
    best_val_profit = -99999.0
    
    # Log the grid search process
    logger.info("Performing R:R threshold grid search...")
    for th in np.arange(0.8, 1.81, 0.05):
        # Validation split
        val_df = df[(df["year"] == 2025) & (df["expected_rr"] >= th)]
        val_profit = val_df["profit_0_05"].sum()
        if val_profit > best_val_profit:
            best_val_profit = val_profit
            best_th = round(float(th), 2)
            
    logger.info("Optimal validation R:R threshold found: {}", best_th)
    
    # Apply optimal threshold to full dataset
    optimal_th_profit = df[df["expected_rr"] >= best_th]["profit_0_05"]
    
    # Scenario 3: Dynamic Exit SL/TP (using predicted MFE and MAE points)
    # Base lot: 0.05.
    # If actual drawdown (mae_target) >= predicted_mae -> exit at predicted_mae loss.
    # Else if actual profit (mfe_target) >= predicted_mfe -> exit at predicted_mfe profit.
    # Otherwise -> exit at end of window with final price profit/loss.
    dyn_exit_profits = []
    for _, row in df.iterrows():
        # skip filtered trades (using R:R >= 1.0 filter as base)
        if row["expected_rr"] < 1.0:
            dyn_exit_profits.append(0.0)
            continue
            
        p_mfe = row["predicted_mfe"]
        p_mae = row["predicted_mae"]
        act_mfe = row["mfe_target"]
        act_mae = row["mae_target"]
        
        # Conservative assumption: if both targets are hit in the 24h window, assume SL was hit first
        if act_mae >= p_mae and act_mfe >= p_mfe:
            points_pnl = -p_mae
        elif act_mae >= p_mae:
            points_pnl = -p_mae
        elif act_mfe >= p_mfe:
            points_pnl = p_mfe
        else:
            # use end of window net profit from original trade (scaled to 0.05 lot)
            points_pnl = (row["actual_net_profit"] / 0.1) * 10.0  # back to points
            
        # Convert points to USD profit at 0.05 lot size (1 point = 0.1 USD at 1 lot, so 0.005 USD at 0.05 lot)
        # points = USD change * 100.
        # So points_pnl / 10 = USD change per ounce.
        # For 0.05 lot (5 ounces), USD profit = (points_pnl / 10.0) * 0.5
        usd_profit = (points_pnl / 10.0) * 0.5
        dyn_exit_profits.append(usd_profit)
        
    df["dyn_exit_profit"] = dyn_exit_profits
    dyn_exit_active = df[df["expected_rr"] >= 1.0]["dyn_exit_profit"]
    
    # Scenario 4: Combined Dynamic Lot Sizing + Dynamic SL/TP Exits
    dyn_exit_dyn_lot_profits = []
    for _, row in df.iterrows():
        err = row["expected_rr"]
        if err < 1.0:
            dyn_exit_dyn_lot_profits.append(0.0)
            continue
            
        # Determine dynamic lot
        if err >= 1.5:
            lot = 0.08
        elif err >= 1.2:
            lot = 0.06
        else:
            lot = 0.05
            
        # Determine points PnL from dynamic SL/TP
        p_mfe = row["predicted_mfe"]
        p_mae = row["predicted_mae"]
        act_mfe = row["mfe_target"]
        act_mae = row["mae_target"]
        
        if act_mae >= p_mae and act_mfe >= p_mfe:
            points_pnl = -p_mae
        elif act_mae >= p_mae:
            points_pnl = -p_mae
        elif act_mfe >= p_mfe:
            points_pnl = p_mfe
        else:
            points_pnl = (row["actual_net_profit"] / 0.1) * 10.0
            
        # Convert points to USD using dynamic lot
        usd_profit = (points_pnl / 10.0) * (lot / 0.1)
        dyn_exit_dyn_lot_profits.append(usd_profit)
        
    df["dyn_exit_dyn_lot_profit"] = dyn_exit_dyn_lot_profits
    dyn_exit_dyn_lot_active = df[df["expected_rr"] >= 1.0]["dyn_exit_dyn_lot_profit"]

    # Scenario 5: BoS-Only (all cycles) + Optimized Threshold + Extended Lot Tier
    # Base filter: entry must be triggered directly by a BoS event (any cycle since
    # last CHoCH -- CHoCH-triggered entries and non-structural entries are excluded)
    # AND expected_rr >= best_th (instead of fixed 1.0).
    # Lot tiers: R:R >= 3.0 -> 0.10, R:R >= 1.5 -> 0.08, R:R >= 1.2 -> 0.06, else 0.05
    # Exit: same dynamic SL/TP logic as Scenario 3/4
    bos_cycles = build_bos_cycle_table()
    df = df.merge(bos_cycles, on="entry_time", how="left")
    df["is_bos_entry"] = df["cycle"].notna()
    logger.info("BoS-triggered entries matched: {} / {}", int(df["is_bos_entry"].sum()), len(df))

    s5_profits = []
    for _, row in df.iterrows():
        err = row["expected_rr"]
        if err < best_th or not row["is_bos_entry"]:
            s5_profits.append(0.0)
            continue

        if err >= 3.0:
            lot = 0.10
        elif err >= 1.5:
            lot = 0.08
        elif err >= 1.2:
            lot = 0.06
        else:
            lot = 0.05

        p_mfe = row["predicted_mfe"]
        p_mae = row["predicted_mae"]
        act_mfe = row["mfe_target"]
        act_mae = row["mae_target"]

        if act_mae >= p_mae and act_mfe >= p_mfe:
            points_pnl = -p_mae
        elif act_mae >= p_mae:
            points_pnl = -p_mae
        elif act_mfe >= p_mfe:
            points_pnl = p_mfe
        else:
            points_pnl = (row["actual_net_profit"] / 0.1) * 10.0

        usd_profit = (points_pnl / 10.0) * (lot / 0.1)
        s5_profits.append(usd_profit)

    df["s5_profit"] = s5_profits
    s5_active = df[(df["expected_rr"] >= best_th) & (df["is_bos_entry"])]["s5_profit"]

    # -------------------------------------------------------------
    # COMPILE AND REPORT RESULTS
    # -------------------------------------------------------------
    scenarios = [
        ("MS Baseline (No Filters)", ms_only),
        ("ML Filter Only (R:R >= 1.0)", ml_only),
        ("ML + EA Combined Filter", ml_ea),
        ("Scenario 1: Dynamic Lot Sizing", dyn_lot_active),
        (f"Scenario 2: Opt R:R Threshold (R:R >= {best_th})", optimal_th_profit),
        ("Scenario 3: Dynamic SL/TP Exits", dyn_exit_active),
        ("Scenario 4: Combined S1 + S3", dyn_exit_dyn_lot_active),
        (f"Scenario 5: BoS-Only + Opt Th + Ext Lot (R:R>={best_th})", s5_active),
    ]
    
    print("\n" + "=" * 95)
    print(f"{'Trading Strategy Scenario (0.05 lot base)':42} | {'Trades':6} | {'Win Rate':8} | {'Net Profit':10} | {'Profit Factor':13} | {'Max DD'}")
    print("=" * 95)
    
    for name, returns in scenarios:
        win_rate = (returns > 0).mean() if len(returns) else 0.0
        pf = profit_factor(returns)
        dd = max_drawdown(returns)
        print(f"{name:42} | {len(returns):6} | {win_rate:8.1%} | ${returns.sum():9.2f} | {pf:13.2f} | ${dd:.2f}")
        records.append({
            "scenario": name,
            "trades": len(returns),
            "win_rate": win_rate,
            "net_profit": returns.sum(),
            "profit_factor": pf,
            "max_drawdown": dd,
        })
        
    print("=" * 95 + "\n")
    
    # Save CSV report
    output_path = SCORED_CSV_PATH.parent / "optimization_scenarios_report.csv"
    pd.DataFrame(records).to_csv(output_path, index=False)
    logger.info("Optimization report saved to {}", output_path)


if __name__ == "__main__":
    main()
