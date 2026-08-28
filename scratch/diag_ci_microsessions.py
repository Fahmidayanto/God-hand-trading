"""CI bootstrap + identifikasi sesi mikro L/S untuk kandidat joint."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd  # noqa: E402
from evaluate_walk_forward_trades import evaluate_scored, prepare_trades  # noqa: E402

EXP = Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "experiments" / "v12opencode"
tag = sys.argv[1] if len(sys.argv) > 1 else "m03_session_joint"

res = evaluate_scored(EXP / "runs" / f"scored_{tag}.csv", tag, threshold=1.05)
print(f"{tag}: dyn={res['dynamic_net_pnl']:.2f} CI95={res['dynamic_net_pnl_ci95']}")
print(f"{tag}: WR={res['win_rate']:.2f} CI95={res['win_rate_ci95']}")

ea = prepare_trades(EXP / "runs" / f"scored_{tag}.csv")
ea["expected_rr"] = ea["predicted_mfe"] / ea["predicted_mae"].clip(lower=1.0)
passed = ea[ea["expected_rr"] >= 1.05]
small = passed[passed["session_name"].isin(["L", "S"])]
print("\nSesi L/S detail:")
print(small.groupby(["year", "session_name"]).agg(n=("actual_net_profit", "size"), pnl=("actual_net_profit", "sum")))
print("\nSemua nilai session_name unik:", sorted(passed["session_name"].dropna().unique()))
