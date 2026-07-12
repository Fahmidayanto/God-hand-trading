"""
Daily PnL Report (Sprint 6, Tier 4 #19)

Reads the decisions audit log and renders a Telegram-friendly end-of-day
summary: totals, win rate, top/bottom sources, pending positions.

Ponytail choices:
- Pure read-only over the SQLite audit log. No new tables, no caching.
- One CLI: ``--db`` (required) and ``--date YYYY-MM-DD`` (default: today UTC).
- Output: plaintext with monospace alignment so it survives Telegram's
  monospace blocks without HTML gymnastics.
- A ``Notifier`` instance can be wired in to actually push the message;
  the function returns the string so it can also be printed in tests.

Usage:
    python -m valuecell.adapters.analytics.daily_report --db logs/decisions_XAUUSD_M15.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _day_bounds(day: date) -> tuple:
    """Return UTC ISO timestamps for ``[day 00:00, next day 00:00)``."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def build_report(
    db_path: str,
    symbol: Optional[str] = None,
    day: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute the report payload. Returns a dict; caller renders or sends."""
    day = day or datetime.now(timezone.utc).date()
    start, end = _day_bounds(day)

    with _connect(db_path) as conn:
        # Decisions logged on this day
        params: List[Any] = [start, end]
        sym_filter = ""
        if symbol:
            sym_filter = " AND symbol = ?"
            params.append(symbol)

        decisions_rows = conn.execute(
            f"SELECT * FROM decisions "
            f"WHERE ts >= ? AND ts < ? {sym_filter} ORDER BY ts ASC",
            params,
        ).fetchall()

        # Source attribution for the day
        outcome_rows = conn.execute(
            f"SELECT news_sources_json, outcome_pnl FROM decisions "
            f"WHERE ts >= ? AND ts < ? AND outcome_pnl IS NOT NULL {sym_filter}",
            params,
        ).fetchall()

    decisions = [dict(r) for r in decisions_rows]
    approved = [d for d in decisions if d["approved"]]

    # Outcome breakdown
    wins = [d for d in approved if (d["outcome_pnl"] or 0) > 0]
    losses = [d for d in approved if (d["outcome_pnl"] or 0) < 0]
    pending = [d for d in approved if d["outcome_pnl"] is None]

    realized = sum((d["outcome_pnl"] or 0.0) for d in approved)
    avg_pnl = realized / len(approved) if approved else 0.0
    wr = len(wins) / len(approved) if approved else 0.0

    # Per-source attribution (presence-based — same model as DecisionLogger)
    by_src: Dict[str, Dict[str, float]] = {}
    for r in outcome_rows:
        try:
            sources = json.loads(r["news_sources_json"] or "[]")
        except (TypeError, ValueError):
            sources = []
        if not sources:
            continue
        share = float(r["outcome_pnl"]) / len(sources)
        for src in sources:
            s = by_src.setdefault(src, {"pnl": 0.0, "n": 0})
            s["pnl"] += share
            s["n"] += 1
    top = sorted(by_src.items(), key=lambda kv: kv[1]["pnl"], reverse=True)

    return {
        "db_path": db_path,
        "symbol": symbol or "ALL",
        "day": day.isoformat(),
        "decisions_total": len(decisions),
        "approved": len(approved),
        "wins": len(wins),
        "losses": len(losses),
        "pending_outcome": len(pending),
        "win_rate": wr,
        "total_pnl": realized,
        "avg_pnl": avg_pnl,
        "by_source": top,
        "pending_tickets": [d.get("outcome_ticket") for d in pending],
    }


def render_text(report: Dict[str, Any]) -> str:
    """Plaintext rendering — Telegram-friendly (works in monospace code blocks)."""
    lines = [
        f"Daily PnL — {report['day']} (UTC)",
        f"Symbol: {report['symbol']}",
        "─" * 36,
        f"Decisions      : {report['decisions_total']:>4}",
        f"Approved       : {report['approved']:>4}",
        f"  Wins         : {report['wins']:>4}",
        f"  Losses       : {report['losses']:>4}",
        f"  Pending      : {report['pending_outcome']:>4}",
        f"Win rate       : {report['win_rate'] * 100:>5.1f}%",
        f"Total PnL      : {report['total_pnl']:>+8.2f}",
        f"Avg PnL / trade: {report['avg_pnl']:>+7.2f}",
        "─" * 36,
        "Per-source attribution (presence-based):",
    ]
    if report["by_source"]:
        for src, s in report["by_source"][:5]:
            lines.append(f"  {src:<18s} n={int(s['n']):>3d}  pnl={s['pnl']:>+8.2f}")
    else:
        lines.append("  (no realized sources)")
    if report["pending_tickets"]:
        lines.append(
            f"\nPending positions: tickets={report['pending_tickets']}"
        )
    lines.append("─" * 36)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Daily PnL report from the audit log.")
    p.add_argument("--db", required=True, help="Path to decisions_*.db SQLite file")
    p.add_argument("--symbol", default=None, help="Filter by symbol (default: all)")
    p.add_argument("--date", default=None, help="ISO date YYYY-MM-DD (default: today UTC)")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of plaintext")
    args = p.parse_args(argv)

    day: Optional[date] = None
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            print(f"--date must be YYYY-MM-DD, got {args.date!r}", file=sys.stderr)
            return 2

    try:
        report = build_report(args.db, symbol=args.symbol, day=day)
    except sqlite3.OperationalError as e:
        print(f"ERROR opening {args.db}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render_text(report))
    return 0


# ---------- Self-test ----------

if __name__ == "__main__":
    if "--self-test" in (sys.argv[1:] or []):
        import tempfile, os
        from valuecell.adapters.db.decision_log import DecisionLogger

        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "report_self.db")
            dl = DecisionLogger(db)

            # Build a fixed-day slice. We override ``ts`` by writing the row
            # then re-stamping ``ts`` to a known day via raw SQL — easier than
            # mucking with utcnow() mocking.
            today = datetime.now(timezone.utc).date()
            today_iso = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).isoformat()

            # Day +1 (out of range)
            yesterday_iso = (datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
                             - timedelta(days=1)).isoformat()

            def _log(ts_iso, news, conf, approved, pnl=None):
                rid = dl.log_decision(
                    symbol="XAUUSD", mode="paper", timeframe="M15",
                    bar_time=datetime.fromisoformat(ts_iso.replace("Z", "")),
                    upstream_signal="BUY", upstream_confidence=conf,
                    orchestrator_result={
                        "final_signal": "BUY" if approved else "HOLD",
                        "final_confidence": conf, "approved": approved,
                        "agent_results": {"sentiment": {"sentiment": {"type": "neutral", "score": 0.0, "strength": "none"}, "confidence_adjustment": 0.0, "events": {"adjustment": 0.0}, "filtered": False, "filter_reason": "", "shadow_mode": False}},
                        "market_data": {"news_headlines": news},
                    },
                )
                # Force ts to the chosen day
                with sqlite3.connect(db) as c:
                    c.execute("UPDATE decisions SET ts = ? WHERE id = ?", (ts_iso, rid))
                if pnl is not None:
                    dl.record_outcome(rid, pnl=pnl, ticket=9000 + (rid or 0))
                return rid

            # Today: 3 approved, 1 win/loss, 1 pending, 1 not-approved. 1 yesterday (excluded).
            _log(today_iso, [{"headline": "Gold up", "source": "web_search"}], 0.80, True, 40.0)
            _log(today_iso, [{"headline": "Fed hawkish", "source": "rss_alpha"}], 0.65, True, -10.0)
            _log(today_iso, [{"headline": "Quiet day", "source": "rss_beta"}], 0.70, True, None)  # pending
            _log(today_iso, [{"headline": "Inflation high", "source": "rss_alpha"}], 0.55, False, None)  # not approved
            _log(yesterday_iso, [{"headline": "Old news", "source": "web_search"}], 0.80, True, 100.0)  # excluded

            rep = build_report(db, symbol="XAUUSD", day=today)
            assert rep["decisions_total"] == 4, f"got {rep['decisions_total']}"
            assert rep["approved"] == 3
            assert rep["wins"] == 1
            assert rep["losses"] == 1
            assert rep["pending_outcome"] == 1
            assert abs(rep["total_pnl"] - 30.0) < 0.01, f"got {rep['total_pnl']}"
            # Per-source: web_search +40, rss_alpha -10/2 + 0 = -5
            src_map = {k: v for k, v in rep["by_source"]}
            assert abs(src_map["web_search"]["pnl"] - 40.0) < 0.01
            assert abs(src_map["rss_alpha"]["pnl"] - (-10.0)) < 0.01
            # ponytail: pending outcomes aren't attributed — we don't know
            # the realized PnL, so leaving the source out is honest.
            assert "rss_beta" not in src_map, "pending rows must not be attributed"

            # Sanity: yesterday's row is excluded from today's day-window.
            yesterday_dt = today - timedelta(days=1)
            rep_yday = build_report(db, symbol="XAUUSD", day=yesterday_dt)
            assert rep_yday["decisions_total"] == 1, "yesterday row must surface in yesterday's slice"
            assert rep_yday["total_pnl"] == 100.0

            text = render_text(rep)
            assert "Daily PnL" in text and "web_search" in text
            print("daily_report self-test PASS")
        sys.exit(0)

    sys.exit(main())
