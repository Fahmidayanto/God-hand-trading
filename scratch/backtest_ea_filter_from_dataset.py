"""
Backtest ulang dataset ML dengan FILTER ASLI EA Dev_Bot_v11_Gold.

Menggunakan kolom ea_status / ea_reject_reason yang kini terekam langsung
dari CSV Backtest_Results (Status + Reject_Reason per event), bukan lagi
aproksimasi fitur. Event dengan status EXECUTED = lolos semua filter EA asli.

Output: tabel PnL per tahun untuk 3 skenario:
  1. Tanpa filter (semua event)
  2. Filter asli EA (hanya EXECUTED)
  3. Filter asli EA + ML gate (EXECUTED dan expected_rr >= threshold)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORED_CSV = REPO_ROOT / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest" / "scored_v8_walk_forward.csv"
RR_THRESHOLD = 1.2


def main() -> None:
    df = pd.read_csv(SCORED_CSV)
    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)
    executed = df["ea_status"].str.upper() == "EXECUTED"

    print("=== Distribusi Status & Reject Reason (filter asli EA) ===")
    print(df.groupby([df["ea_status"], df["ea_reject_reason"]]).size().sort_values(ascending=False).head(12).to_string())
    print()

    rows = []
    for year, grp in df.groupby("year"):
        f_ea = grp[executed.loc[grp.index]]
        f_ml = f_ea[f_ea["expected_rr"] >= RR_THRESHOLD]
        rows.append({
            "year": int(year),
            "events": len(grp),
            "ea_trades": len(f_ea),
            "pnl_no_filter": round(grp["actual_net_profit"].sum(), 2),
            "pnl_ea_filter": round(f_ea["actual_net_profit"].sum(), 2),
            "ea_plus_ml_trades": len(f_ml),
            "pnl_ea_plus_ml": round(f_ml["actual_net_profit"].sum(), 2),
        })
    r = pd.DataFrame(rows).sort_values("year")
    print("=== PnL per Tahun: Tanpa Filter vs Filter Asli EA vs EA+ML ===")
    print(r.to_string(index=False))
    print()
    print("TOTAL no_filter :", round(r["pnl_no_filter"].sum(), 2), "USD")
    print("TOTAL ea_filter :", round(r["pnl_ea_filter"].sum(), 2), "USD |", int(r["ea_trades"].sum()), "trades")
    print("TOTAL ea+ml     :", round(r["pnl_ea_plus_ml"].sum(), 2), "USD |", int(r["ea_plus_ml_trades"].sum()), "trades")


if __name__ == "__main__":
    main()
