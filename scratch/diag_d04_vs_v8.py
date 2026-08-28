"""Diagnosis detail d04_session vs baseline v8 canonical (per tahun + slice)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from evaluate_walk_forward_trades import evaluate_scored, gate_check  # noqa: E402

EXP = Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "experiments" / "v12opencode"

base_raw = json.loads((EXP / "baseline_v8_canonical.json").read_text(encoding="utf-8"))
base = {
    **base_raw["metrics"],
    **{k: base_raw[k] for k in ("by_year", "by_side", "by_session", "by_vol_regime")},
    "name": "v8_canonical",
}

tag = sys.argv[1] if len(sys.argv) > 1 else "d04_session"
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 1.05
res = evaluate_scored(EXP / "runs" / f"scored_{tag}.csv", tag, threshold=thr)

print(f"PER TAHUN  {tag} vs v8:")
print(f"{'Year':6} | {'tr_c':>4} {'tr_b':>4} | {'WR_c':>6} {'WR_b':>6} | {'dyn_c':>10} {'dyn_b':>10} | {'flat_c':>9}")
for y in sorted(set(res["by_year"]) & set(base["by_year"])):
    c = res["by_year"][y]
    b = base["by_year"][y]
    print(
        f"{y:6} | {c['trades']:4} {b['trades']:4} | {c['win_rate']:5.1f}% {b['win_rate']:5.1f}%"
        f" | {c['dynamic_net_pnl']:10.1f} {b['dynamic_net_pnl']:10.1f} | {c['flat_net_pnl']:9.1f}"
    )

for key in ("by_side", "by_vol_regime"):
    print(f"\nSLICE {key}:")
    keys = sorted(set(res[key]) | set(base[key]))
    for k in keys:
        if k == "NA":
            continue
        c = res[key].get(k, {})
        b = base[key].get(k, {})
        print(
            f"  {k:12} cand(tr={c.get('trades',0):3}, dyn={c.get('dynamic_net_pnl',0.0):9.1f})"
            f"  base(tr={b.get('trades',0):3}, dyn={b.get('dynamic_net_pnl',0.0):9.1f})"
        )

print("\nSLICE by_session (top by trades):")
sess = sorted(res["by_session"].items(), key=lambda kv: -kv[1]["trades"])[:5]
bsess = base["by_session"]
for k, v in sess:
    b = bsess.get(k, {"trades": 0, "dynamic_net_pnl": 0.0})
    print(f"  {k:16} cand(tr={v['trades']:3}, dyn={v['dynamic_net_pnl']:9.1f})  base(tr={b['trades']:3}, dyn={b['dynamic_net_pnl']:9.1f})")

gate_check(res, base)
