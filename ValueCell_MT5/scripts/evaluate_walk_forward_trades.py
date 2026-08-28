"""
Unified walk-forward trade-level evaluator for ML prediction models.

Protocol canonical (locked):
- Universe        : ea_status == "EXECUTED" (tradeable universe setelah keputusan EA)
- Expected R:R    : predicted_mfe / max(1.0, predicted_mae)
- Gate            : expected_rr >= threshold (default 1.05)
- Lot tiers       : rr>=2.0 -> 0.07 ; >=1.5 -> 0.04 ; >=1.2 -> 0.02 ; >=1.05 -> 0.01 ; else 0
- Net PnL         : kolom actual_net_profit (Net_Profit, BUKAN gross Profit)
- Dynamic Net PnL : net_profit x (lot / 0.01)
- Win             : net_profit > 0 ; Loss : net_profit <= 0

Usage:
  python evaluate_walk_forward_trades.py --scored <path.csv> [--name v8] [--threshold 1.05]
         [--news-filter] [--weekend-filter] [--baseline <spec.json>]
         [--stress-spread-points 30] [--stress-commission-usd 0.7] [--save-eval out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2] if (Path(__file__).resolve().parents[1].name == "scripts") else Path(__file__).resolve().parents[1]

BASE_REF_PRICE = 4500.0
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 42


def get_dynamic_lot(rr: float) -> float:
    if rr >= 2.0:
        return 0.07
    if rr >= 1.5:
        return 0.04
    if rr >= 1.2:
        return 0.02
    if rr >= 1.05:
        return 0.01
    return 0.0


def max_drawdown(pnl: pd.Series) -> float:
    if len(pnl) == 0:
        return 0.0
    equity = pnl.cumsum()
    return float((equity - equity.cummax()).min())


def profit_factor(pnl: pd.Series) -> float:
    wins = pnl[pnl > 0].sum()
    losses = abs(pnl[pnl < 0].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


def _bootstrap_ci(values: np.ndarray, stat: str = "mean") -> tuple[float, float]:
    if len(values) == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(values), size=(BOOTSTRAP_N, len(values)))
    samples = values[idx]
    stats = samples.mean(axis=1) if stat == "mean" else samples.sum(axis=1)
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def prepare_trades(scored_path: Path) -> pd.DataFrame:
    df = pd.read_csv(scored_path)
    if "ea_status" in df.columns:
        ea = df[df["ea_status"] == "EXECUTED"].copy()
    elif "source" in df.columns:
        ea = df[df["source"] == "EXECUTED"].copy()
    else:
        ea = df.copy()
    ea = ea.reset_index(drop=True)
    if "actual_net_profit" not in ea.columns and "net_profit" in ea.columns:
        ea["actual_net_profit"] = ea["net_profit"]

    t = pd.to_datetime(ea["entry_time"], utc=True)
    ea["entry_ts"] = t
    ea["is_friday_late"] = (t.dt.weekday == 4) & (t.dt.hour >= 18)
    ea["is_weekend_open"] = ((t.dt.weekday == 6) & (t.dt.hour >= 22)) | ((t.dt.weekday == 0) & (t.dt.hour < 1))
    ea["is_weekend"] = ea["is_friday_late"] | ea["is_weekend_open"]
    ea["price_bucket"] = pd.cut(
        ea["entry_price"],
        bins=[0, 2000, 3000, 4000, np.inf],
        labels=["<2000", "2000-3000", "3000-4000", ">=4000"],
    )
    if "atr_14_pct" in ea.columns:
        q1, q2 = ea["atr_14_pct"].quantile([1 / 3, 2 / 3])
        ea["vol_regime"] = pd.cut(ea["atr_14_pct"], bins=[-np.inf, q1, q2, np.inf], labels=["low", "mid", "high"])
    else:
        ea["vol_regime"] = "NA"
    ea["year"] = ea["year"].astype(int)
    return ea


def evaluate_scored(
    scored_path: Path,
    name: str,
    threshold: float = 1.05,
    news_filter: bool = False,
    weekend_filter: bool = False,
    stress_spread_points: float = 0.0,
    stress_commission_usd: float = 0.0,
    threshold_by_year: dict | None = None,
) -> dict:
    ea = prepare_trades(scored_path)

    ea["expected_rr"] = ea["predicted_mfe"] / np.maximum(1.0, ea["predicted_mae"])
    eff_threshold = threshold
    if threshold_by_year:
        ea["eff_thr"] = ea["year"].map(lambda y: threshold_by_year.get(int(y), threshold))
        eff_threshold_series = ea["eff_thr"]
    else:
        eff_threshold_series = pd.Series(threshold, index=ea.index)
    pass_mask = ea["expected_rr"] >= eff_threshold_series
    if news_filter and "is_news_blackout" in ea.columns:
        pass_mask &= ea["is_news_blackout"] == 0
    if weekend_filter:
        pass_mask &= ~ea["is_weekend"]

    tr = ea[pass_mask].copy().reset_index(drop=True)
    tr["dyn_lot"] = [get_dynamic_lot(r) for r in tr["expected_rr"]]
    tr["lot_mult"] = tr["dyn_lot"] / 0.01

    # Stress: spread penalty dalam poin -> USD di lot 0.01 = poin x 0.01
    stress_usd_flat = stress_spread_points * 0.01 + stress_commission_usd
    tr["net_adj"] = tr["actual_net_profit"] - stress_usd_flat
    tr["flat_net_pnl"] = tr["net_adj"]
    tr["dyn_net_pnl"] = tr["net_adj"] * tr["lot_mult"]

    tr = tr.sort_values("entry_ts").reset_index(drop=True)

    n = len(tr)
    res = {
        "name": name,
        "config": {
            "threshold": threshold,
            "threshold_by_year": threshold_by_year,
            "news_filter": news_filter,
            "weekend_filter": weekend_filter,
            "stress_spread_points": stress_spread_points,
            "stress_commission_usd": stress_commission_usd,
        },
        "trades": int(n),
        "wins": int((tr["net_adj"] > 0).sum()),
        "win_rate": float((tr["net_adj"] > 0).mean() * 100) if n else 0.0,
        "flat_net_pnl": float(tr["flat_net_pnl"].sum()),
        "dynamic_net_pnl": float(tr["dyn_net_pnl"].sum()),
        "profit_factor_dynamic": profit_factor(tr["dyn_net_pnl"]),
        "profit_factor_flat": profit_factor(tr["flat_net_pnl"]),
        "max_drawdown_dynamic": max_drawdown(tr["dyn_net_pnl"]),
        "max_drawdown_flat": max_drawdown(tr["flat_net_pnl"]),
        "expectancy_flat": float(tr["flat_net_pnl"].mean()) if n else 0.0,
        "expectancy_dynamic": float(tr["dyn_net_pnl"].mean()) if n else 0.0,
    }
    wr_lo, wr_hi = _bootstrap_ci((tr["net_adj"] > 0).astype(float).values, "mean")
    dyn_lo, dyn_hi = _bootstrap_ci(tr["dyn_net_pnl"].values, "sum")
    res["win_rate_ci95"] = [wr_lo * 100, wr_hi * 100]
    res["dynamic_net_pnl_ci95"] = [dyn_lo, dyn_hi]

    def slice_block(key: str) -> dict:
        out = {}
        for val, sub in tr.groupby(key, observed=True):
            k = len(sub)
            out[str(val)] = {
                "trades": int(k),
                "win_rate": float((sub["net_adj"] > 0).mean() * 100) if k else 0.0,
                "flat_net_pnl": float(sub["flat_net_pnl"].sum()),
                "dynamic_net_pnl": float(sub["dyn_net_pnl"].sum()),
            }
        return out

    res["by_year"] = slice_block("year")
    res["by_side"] = slice_block("signal")
    res["by_session"] = slice_block("session_name") if "session_name" in tr.columns else {}
    res["by_structure"] = slice_block("entry_structure") if "entry_structure" in tr.columns else {}
    res["by_news"] = (
        slice_block("is_news_blackout") if "is_news_blackout" in tr.columns else {}
    )
    res["by_vol_regime"] = slice_block("vol_regime")
    res["by_price_bucket"] = slice_block("price_bucket")
    return res


GATE_NOISE_WR_PP = 2.0


def gate_check(cand: dict, base: dict, verbose: bool = True) -> tuple[bool, list[str]]:
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, bool(ok), detail))

    add(
        "total_win_rate",
        cand["win_rate"] >= base["win_rate"],
        f"{cand['win_rate']:.2f} vs {base['win_rate']:.2f}",
    )
    add(
        "total_dynamic_net_pnl",
        cand["dynamic_net_pnl"] >= base["dynamic_net_pnl"],
        f"{cand['dynamic_net_pnl']:.2f} vs {base['dynamic_net_pnl']:.2f}",
    )
    add(
        "total_flat_net_pnl",
        cand["flat_net_pnl"] >= base["flat_net_pnl"],
        f"{cand['flat_net_pnl']:.2f} vs {base['flat_net_pnl']:.2f}",
    )

    years = sorted(set(cand["by_year"]) & set(base["by_year"]))
    bad_dyn_y = [y for y in years if cand["by_year"][y]["dynamic_net_pnl"] < base["by_year"][y]["dynamic_net_pnl"]]
    add("per_year_dynamic_net_pnl", not bad_dyn_y, f"gagal tahun: {bad_dyn_y}")

    bad_wr_y = []
    for y in years:
        cw = cand["by_year"][y]["win_rate"]
        bw = base["by_year"][y]["win_rate"]
        bn = max(1, base["by_year"][y]["trades"])
        cn = max(1, cand["by_year"][y]["trades"])
        cdp = cand["by_year"][y]["dynamic_net_pnl"]
        bdp = base["by_year"][y]["dynamic_net_pnl"]
        # Noise statistik binomial (1.96 x SE, pakai n efektif min(base,cand));
        # rule user: WR tahun boleh turun jika dalam noise DAN Net PnL tahun itu naik.
        p0 = min(max(bw / 100.0, 1e-9), 1.0 - 1e-9)
        se = float(np.sqrt(p0 * (1.0 - p0) / min(bn, cn)))
        noise_pp = max(GATE_NOISE_WR_PP, 196.0 * se)
        if cw < bw and not ((bw - cw) <= noise_pp and cdp > bdp):
            bad_wr_y.append(y)
    add("per_year_win_rate", not bad_wr_y, f"gagal tahun: {bad_wr_y}")

    add(
        "max_drawdown_dynamic",
        cand["max_drawdown_dynamic"] >= base["max_drawdown_dynamic"],
        f"{cand['max_drawdown_dynamic']:.2f} vs {base['max_drawdown_dynamic']:.2f}",
    )
    add(
        "profit_factor_dynamic",
        cand["profit_factor_dynamic"] >= base["profit_factor_dynamic"],
        f"{cand['profit_factor_dynamic']:.3f} vs {base['profit_factor_dynamic']:.3f}",
    )

    cov_ok = cand["trades"] >= 0.9 * base["trades"]
    ci_supports = cand["dynamic_net_pnl_ci95"][0] > base["dynamic_net_pnl"]
    add("coverage_90pct", cov_ok or ci_supports, f"{cand['trades']} vs 90% x {base['trades']} (CI support={ci_supports})")

    collapse = []
    for key in ("by_side",):
        for s, b in base.get(key, {}).items():
            cv = cand.get(key, {}).get(s, {}).get("dynamic_net_pnl", 0.0)
            bv = b["dynamic_net_pnl"]
            if bv > 0 and cv <= 0:
                collapse.append(f"{key}:{s}")
    # "Sesi utama" = top-3 sesi baseline berdasarkan jumlah trade (redaksi user),
    # sesi mikro/artefak penamaan legacy di luar scope gate.
    main_sessions = sorted(base.get("by_session", {}).items(), key=lambda kv: -kv[1]["trades"])[:3]
    for sname, b in main_sessions:
        cv = cand.get("by_session", {}).get(sname, {}).get("dynamic_net_pnl", 0.0)
        bv = b["dynamic_net_pnl"]
        if bv > 0 and cv <= 0:
            collapse.append(f"session:{sname}")
    for s, b in base.get("by_vol_regime", {}).items():
        if s == "NA":
            continue
        cv = cand.get("by_vol_regime", {}).get(s, {}).get("dynamic_net_pnl", 0.0)
        bv = b["dynamic_net_pnl"]
        if bv > 0 and cv <= 0:
            collapse.append(f"vol:{s}")
    add("no_collapse_slices", not collapse, f"collapse: {collapse}")

    max_lot_ok = True
    add("lot_cap_007", max_lot_ok, "tier kanonik maksimum 0.07 (struktural)")

    passed = all(ok for _, ok, _ in checks)
    if verbose:
        print(f"\n--- PROMOTION GATE: {cand['name']} vs {base['name']} ---")
        for nm, ok, dt in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {nm:26} | {dt}")
        print(f"=== KEPUTUSAN: {'PROMOTE' if passed else 'REJECT'} ===")
    return passed, [nm for nm, ok, _ in checks if not ok]


def print_table(results: list[dict]) -> None:
    hdr = (
        f"{'Model':28} | {'Tr':4} | {'WR':6} | {'FlatPnL':12} | {'DynPnL':13} | "
        f"{'PFd':5} | {'DDdyn':9} | {'ExpD':8}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        pf = r["profit_factor_dynamic"]
        pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"
        print(
            f"{r['name']:28} | {r['trades']:4} | {r['win_rate']:5.1f}% | "
            f"{r['flat_net_pnl']:11.2f} | {r['dynamic_net_pnl']:12.2f} | {pf_s:>5} | "
            f"{r['max_drawdown_dynamic']:9.2f} | {r['expectancy_dynamic']:7.2f}"
        )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", action="append", required=True)
    ap.add_argument("--name", action="append")
    ap.add_argument("--threshold", type=float, default=1.05)
    ap.add_argument("--news-filter", action="store_true")
    ap.add_argument("--weekend-filter", action="store_true")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--stress-spread-points", type=float, default=0.0)
    ap.add_argument("--stress-commission-usd", type=float, default=0.0)
    ap.add_argument("--save-eval", default=None)
    args = ap.parse_args()

    names = args.name or [Path(p).parent.name + ":" + Path(p).stem for p in args.scored]
    results = []
    for path, name in zip(args.scored, names):
        r = evaluate_scored(
            Path(path),
            name,
            threshold=args.threshold,
            news_filter=args.news_filter,
            weekend_filter=args.weekend_filter,
            stress_spread_points=args.stress_spread_points,
            stress_commission_usd=args.stress_commission_usd,
        )
        results.append(r)

    print_table(results)

    base = None
    if args.baseline:
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        gate_check(results[-1], base)

    if args.save_eval:
        out = Path(args.save_eval)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"results": results}
        if base is not None:
            ok, failed = gate_check(results[-1], base, verbose=False)
            payload["gate_passed"] = ok
            payload["gate_failed"] = failed
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved eval JSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
