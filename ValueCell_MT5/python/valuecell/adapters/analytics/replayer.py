"""
Replayer (Sprint 5, Tier 4 #18)

Offline A/B harness: replays historical decisions from the audit log under
candidate configurations, so we can measure the impact of a sentiment /
threshold / filter change *without* touching live trading.

Ponytail choices:
- One knob: ``min_final_confidence`` (drop decisions below threshold).
  Laziest meaningful experiment — answers "is our approval bar wrong?"
- Pure stdlib. Reads the SQLite decision log, simulates the alternate
  config per row, aggregates wins/losses/PnL, prints a Markdown diff
  against the baseline (actual recorded outcomes).
- No new DB tables. No side effects beyond stdout. Re-run safely.

Usage:
    python -m valuecell.adapters.analytics.replayer --db logs/decisions_XAUUSD_M15.db
    python -m valuecell.adapters.analytics.replayer --db logs/decisions_XAUUSD_M15.db --min-conf 0.65
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any, Callable, Dict, List, Optional


# ---------- I/O ---------- #

def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- Simulators ----------
#
# A simulator is ``(row) -> {traded: bool, pnl: float | None, reason: str}``.
# The baseline is what actually happened. Experiments are counterfactual
# responses to "what if config X had been live?".

def _baseline_sim(r: sqlite3.Row) -> Dict[str, Any]:
    if not r["approved"]:
        return {"traded": False, "pnl": None, "reason": "not_approved"}
    return {"traded": True, "pnl": r["outcome_pnl"], "reason": "as_baseline"}


def _min_conf_sim(min_conf: float) -> Callable[[sqlite3.Row], Dict[str, Any]]:
    """Filter: drop any decision whose final_confidence is below ``min_conf``."""
    def fn(r: sqlite3.Row) -> Dict[str, Any]:
        if r["final_confidence"] is not None and r["final_confidence"] < min_conf:
            return {
                "traded": False,
                "pnl": None,
                "reason": f"conf {r['final_confidence']:.2f}<{min_conf:.2f}",
            }
        return _baseline_sim(r)
    return fn


# ---------- Aggregation ---------- #

def _aggregate(
    rows: List[sqlite3.Row],
    sim: Callable[[sqlite3.Row], Dict[str, Any]],
) -> Dict[str, Any]:
    """Pure-function aggregation. ``None`` pnl rows are counted as pending."""
    traded = wins = losses = no_outcome = skipped = 0
    pnl = 0.0
    for r in rows:
        s = sim(r)
        if not s["traded"]:
            skipped += 1
            continue
        traded += 1
        outcome = s["pnl"]
        if outcome is None:
            no_outcome += 1
            continue
        pnl += outcome
        if outcome > 0:
            wins += 1
        elif outcome < 0:
            losses += 1
    return {
        "traded": traded,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / traded if traded else 0.0,
        "total_pnl": pnl,
        "avg_pnl": pnl / traded if traded else 0.0,
        "skipped_no_trade": skipped,
        "pending_outcome": no_outcome,
    }


# ---------- Top-level ---------- #

def replay(
    db_path: str,
    symbol: Optional[str] = None,
    min_conf: Optional[float] = None,
) -> Dict[str, Any]:
    """Run baseline vs experiment and return a structured diff.

    If ``min_conf`` is None, the experiment is identical to the baseline
    (sanity check that the harness agrees with itself).
    """
    with _connect(db_path) as conn:
        where = "WHERE symbol = ?" if symbol else ""
        params = (symbol,) if symbol else ()
        rows = conn.execute(
            f"SELECT * FROM decisions {where} ORDER BY ts ASC", params
        ).fetchall()

    if not rows:
        return {
            "db_path": db_path,
            "symbol": symbol,
            "decisions_total": 0,
            "config": {"min_final_confidence": min_conf},
            "baseline": {},
            "experiment": {},
            "delta": {},
            "warning": "no rows in audit log",
        }

    base = _aggregate(rows, _baseline_sim)
    experiment = _aggregate(rows, _min_conf_sim(min_conf) if min_conf is not None else _baseline_sim)

    return {
        "db_path": db_path,
        "symbol": symbol,
        "decisions_total": len(rows),
        "config": {"min_final_confidence": min_conf},
        "baseline": base,
        "experiment": experiment,
        "delta": {
            "pnl": experiment["total_pnl"] - base["total_pnl"],
            "trades": experiment["traded"] - base["traded"],
            "win_rate": experiment["win_rate"] - base["win_rate"],
        },
    }


def _format_report(r: Dict[str, Any]) -> str:
    """Render the result dict as a Markdown-ish summary for Telegram / CLI."""
    def line(name: str, m: Dict[str, Any]) -> str:
        return (
            f"{name:>10s}: {m.get('traded', 0):>3d} trades | "
            f"{m.get('wins', 0):>2d}W / {m.get('losses', 0):>2d}L | "
            f"WR {(m.get('win_rate', 0) * 100):>5.1f}% | "
            f"PnL {m.get('total_pnl', 0):>+8.2f} | "
            f"avg {m.get('avg_pnl', 0):>+7.2f} | "
            f"skip {m.get('skipped_no_trade', 0):>3d} | "
            f"pend {m.get('pending_outcome', 0):>3d}"
        )

    sym = r.get("symbol") or "ALL"
    cfg = r["config"].get("min_final_confidence")
    cfg_str = f"{cfg:.2f}" if cfg is not None else "off (baseline only)"

    base = r["baseline"]
    exp = r["experiment"]
    delta = r["delta"]

    lines = [
        "=== Replay Report ===",
        f"DB        : {r['db_path']}",
        f"Symbol    : {sym}",
        f"Decisions : {r['decisions_total']}",
        f"min_conf  : {cfg_str}",
        "",
        line("Baseline", base),
        line("Experiment", exp),
        "",
        f"Δ PnL     : {delta['pnl']:+.2f}",
        f"Δ Trades  : {delta['trades']:+d}",
        f"Δ WinRate : {(delta['win_rate'] * 100):+.2f}pp",
    ]
    if "warning" in r:
        lines.append(f"\nWARN: {r['warning']}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Replay historical decisions through alternate configs.")
    p.add_argument("--db", required=True, help="Path to decisions_*.db SQLite file")
    p.add_argument("--symbol", default=None, help="Filter by symbol (default: all)")
    p.add_argument("--min-conf", type=float, default=None,
                   help="Drop decisions whose final_confidence is below this")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    args = p.parse_args(argv)

    try:
        result = replay(args.db, symbol=args.symbol, min_conf=args.min_conf)
    except sqlite3.OperationalError as e:
        print(f"ERROR opening {args.db}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(_format_report(result))
    return 0


# ---------- Self-test ----------
#
# Ponytail: one runnable check that fails if the harness lies about itself.

if __name__ == "__main__":
    if "--self-test" in (sys.argv[1:] or []):
        import tempfile, os
        from datetime import datetime
        from valuecell.adapters.db.decision_log import DecisionLogger

        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "replay_self.db")
            dl = DecisionLogger(db)

            # 4 decisions: 3 trades, 1 filtered. Outcomes: +50, +30, -20.
            # All final_confidence ≥ 0.6. No sentiment filter applied at decision time.
            samples = [
                ("BUY", 0.85, True, 50.0),
                ("BUY", 0.78, True, 30.0),
                ("SELL", 0.70, True, -20.0),
                ("BUY", 0.55, False, None),  # below-threshold and not approved
            ]
            ids = []
            for sig, conf, approved, pnl in samples:
                rid = dl.log_decision(
                    symbol="XAUUSD", mode="paper", timeframe="M15",
                    bar_time=datetime.utcnow(),
                    upstream_signal=sig, upstream_confidence=conf,
                    orchestrator_result={
                        "final_signal": sig if approved else "HOLD",
                        "final_confidence": conf,
                        "approved": approved,
                        "agent_results": {"sentiment": {"sentiment": {"type": "neutral", "score": 0.0, "strength": "none"}, "confidence_adjustment": 0.0, "events": {"adjustment": 0.0}, "filtered": False, "filter_reason": "", "shadow_mode": False}},
                        "market_data": {"news_headlines": []},
                    },
                )
                ids.append(rid)
                if pnl is not None:
                    dl.record_outcome(rid, pnl=pnl, ticket=10000 + rid)

            # 1) Baseline & no-config experiment must agree.
            res0 = replay(db, symbol="XAUUSD", min_conf=None)
            assert res0["delta"]["pnl"] == 0.0, "no-config experiment must equal baseline"
            assert res0["delta"]["trades"] == 0
            # Baseline: 3 trades, +50 +30 -20 = +60 pnl, WR = 2/3.
            assert res0["baseline"]["traded"] == 3
            assert abs(res0["baseline"]["total_pnl"] - 60.0) < 0.01
            assert abs(res0["baseline"]["win_rate"] - 2/3) < 0.01

            # 2) min_conf=0.60 keeps the 3 approved decisions, baseline-equivalent.
            res1 = replay(db, symbol="XAUUSD", min_conf=0.60)
            assert res1["delta"]["pnl"] == 0.0, "all kept → baseline"

            # 3) min_conf=0.75 drops the -20 SELL (0.70) → keeps +50 +30 = +80, 2/2 WR.
            res2 = replay(db, symbol="XAUUSD", min_conf=0.75)
            assert res2["experiment"]["traded"] == 2
            assert abs(res2["experiment"]["total_pnl"] - 80.0) < 0.01
            assert abs(res2["experiment"]["win_rate"] - 1.0) < 0.01
            assert abs(res2["delta"]["pnl"] - 20.0) < 0.01  # 80 vs 60
            assert res2["delta"]["trades"] == -1
            # pending outcome untouched (the dropped -20 SELL doesn't appear in traded)
            assert res2["experiment"]["skipped_no_trade"] == 2  # 1 unapproved + 1 dropped-by-conf

            print("replayer self-test PASS")
        sys.exit(0)

    sys.exit(main())
