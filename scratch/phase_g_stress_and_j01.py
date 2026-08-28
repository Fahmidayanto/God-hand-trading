"""Fase G: evaluasi j01@1.0 + stress test champion (spread/komisi) vs gate v8."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from evaluate_walk_forward_trades import evaluate_scored, gate_check  # noqa: E402

EXP = Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "experiments" / "v12opencode"
raw = json.loads((EXP / "baseline_v8_canonical.json").read_text(encoding="utf-8"))
base = {
    **raw["metrics"],
    **{k: raw[k] for k in ("by_year", "by_side", "by_session", "by_vol_regime")},
    "name": "v8_canonical",
}

cases = [
    ("j01_ms5_thr100", EXP / "runs" / "scored_j01_session_joint_ms5.csv", 1.0, 0.0, 0.0),
    ("m03_thr105_stress_spr30", EXP / "runs" / "scored_m03_session_joint.csv", 1.05, 30.0, 0.0),
    ("m03_thr100_stress_spr30", EXP / "runs" / "scored_m03_session_joint.csv", 1.0, 30.0, 0.0),
    ("m03_thr100_stress_comm07", EXP / "runs" / "scored_m03_session_joint.csv", 1.0, 0.0, 0.7),
    ("m03_thr100_stress_spr50_comm07", EXP / "runs" / "scored_m03_session_joint.csv", 1.0, 50.0, 0.7),
]

for name, path, thr, spr, com in cases:
    r = evaluate_scored(path, name, threshold=thr, stress_spread_points=spr, stress_commission_usd=com)
    ok, failed = gate_check(r, base, verbose=False)
    print(
        f"{name:32} | tr {r['trades']:3} | WR {r['win_rate']:5.2f} | flat {r['flat_net_pnl']:10.2f}"
        f" | dyn {r['dynamic_net_pnl']:10.2f} | PF {min(r['profit_factor_dynamic'], 99):5.3f}"
        f" | DD {r['max_drawdown_dynamic']:8.2f} | GATE {'PASS' if ok else 'FAIL ' + str(failed)}"
    )
