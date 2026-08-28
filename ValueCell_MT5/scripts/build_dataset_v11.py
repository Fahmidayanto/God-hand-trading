"""
Build Dataset v11 (Planned R:R & Reject Reason Clustering + News-Aware).

Enriches dataset_v9_unconstrained.csv with:
1. planned_rr: (InitialRewardPoints / InitialRiskPoints) from EA backtest orders
2. reject_group: Categorical grouping of EA reject reasons:
   - 'NONE' (Executed trade)
   - 'TREND_FILTER_EMA' (H1/H4 EMA200 filters)
   - 'CYCLE_LIMIT' (Max BOS Cycle limit)
   - 'UNCONSTRAINED_SIM' (Simulated structure signals)
3. One-hot encoded reject_group dummies:
   - reject_group_NONE
   - reject_group_TREND_FILTER_EMA
   - reject_group_CYCLE_LIMIT
   - reject_group_UNCONSTRAINED_SIM
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
BACKTEST_DIR = PROJECT_ROOT.parent / "Backtest_result"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def get_reject_group(reason_str: str, ea_status: str) -> str:
    if pd.isna(reason_str) or str(reason_str).strip() in ("", "nan", "NaN", "None", "NONE", "N/A"):
        return "NONE" if str(ea_status).upper() == "EXECUTED" else "UNCONSTRAINED_SIM"
    reason_upper = str(reason_str).upper()
    if "EMA" in reason_upper:
        return "TREND_FILTER_EMA"
    elif "CYCLE" in reason_upper or "BOS" in reason_upper:
        return "CYCLE_LIMIT"
    elif "NONE" in reason_upper or reason_upper == "EXECUTED":
        return "NONE"
    return "OTHER"


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_v9_path = output_dir / "dataset_v9_unconstrained.csv"

    logger.info("=== Building Dataset v11 (Planned R:R + Categorical Reject Reason) ===")
    df = pd.read_csv(dataset_v9_path)
    logger.info("Loaded Dataset v9: {} samples ({} columns)", len(df), len(df.columns))

    # Map raw backtest result files for InitialRiskPoints and InitialRewardPoints
    backtest_map = {}
    for res_file in sorted(BACKTEST_DIR.glob("Backtest_Results_XAUUSD_*.csv")):
        try:
            res_df = pd.read_csv(res_file)
            res_df.columns = [c.strip() for c in res_df.columns]
            for _, r in res_df.iterrows():
                t_time_str = str(r.get("EntryTime", "")).strip()
                t_type = str(r.get("Type", "")).strip().upper()
                if t_time_str and t_type in ("BUY", "SELL"):
                    # Key by raw time string + type
                    t_time = pd.to_datetime(t_time_str, utc=True)
                    # Offset -15 mins to match structure time
                    struct_time = (t_time - pd.Timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    risk_pts = float(r.get("InitialRiskPoints", 3000.0))
                    reward_pts = float(r.get("InitialRewardPoints", 6000.0))
                    if risk_pts <= 0:
                        risk_pts = 3000.0
                    if reward_pts <= 0:
                        reward_pts = 6000.0
                        
                    planned_rr = reward_pts / risk_pts
                    reject_raw = str(r.get("Reject_Reason", "NONE")).strip()
                    status_raw = str(r.get("Status", "EXECUTED")).strip()
                    
                    backtest_map[(struct_time, t_type)] = {
                        "planned_rr": planned_rr,
                        "init_risk_points": risk_pts,
                        "init_reward_points": reward_pts,
                        "reject_reason": reject_raw,
                        "status": status_raw,
                    }
        except Exception as e:
            logger.warning("Error reading {}: {}", res_file.name, e)

    logger.info("Mapped {} backtest entries from raw results", len(backtest_map))

    # Enrich df with planned_rr and reject_group
    planned_rr_list = []
    init_risk_list = []
    init_reward_list = []
    reject_group_list = []

    for _, row in df.iterrows():
        entry_time_str = str(row["entry_time"]).strip()
        sig = str(row["signal"]).strip().upper()
        t_dt = pd.to_datetime(entry_time_str, utc=True).strftime("%Y-%m-%d %H:%M:%S")
        
        info = backtest_map.get((t_dt, sig))
        if info is not None:
            p_rr = info["planned_rr"]
            i_risk = info["init_risk_points"]
            i_rew = info["init_reward_points"]
            r_grp = get_reject_group(info["reject_reason"], info["status"])
        else:
            # Fallback for unconstrained / simulated signals: standard EA ratio
            ratio = max(float(row["entry_price"]), 1.0) / 4500.0
            i_risk = 3000.0 * ratio
            i_rew = 6000.0 * ratio
            p_rr = i_rew / max(1.0, i_risk)
            r_grp = get_reject_group(str(row.get("ea_reject_reason", "N/A")), str(row.get("ea_status", "N/A")))

        planned_rr_list.append(p_rr)
        init_risk_list.append(i_risk)
        init_reward_list.append(i_rew)
        reject_group_list.append(r_grp)

    df["planned_rr"] = planned_rr_list
    df["init_risk_points"] = init_risk_list
    df["init_reward_points"] = init_reward_list
    df["reject_group"] = reject_group_list

    # One-hot encode reject_group
    dummies = pd.get_dummies(df["reject_group"], prefix="reject_group", dtype=float)
    for col in ["reject_group_NONE", "reject_group_TREND_FILTER_EMA", "reject_group_CYCLE_LIMIT", "reject_group_UNCONSTRAINED_SIM"]:
        if col not in dummies.columns:
            dummies[col] = 0.0

    df = pd.concat([df, dummies], axis=1)

    logger.info("Reject Group Distribution:\n{}", df["reject_group"].value_counts())
    logger.info("Planned R:R Summary: Min={:.2f}, Mean={:.2f}, Max={:.2f}", df["planned_rr"].min(), df["planned_rr"].mean(), df["planned_rr"].max())

    output_path = output_dir / "dataset_v11_unconstrained.csv"
    df.to_csv(output_path, index=False)
    logger.info("✅ Dataset v11 saved to: {} (Total Columns: {})", output_path, len(df.columns))

    return 0


if __name__ == "__main__":
    sys.exit(main())
