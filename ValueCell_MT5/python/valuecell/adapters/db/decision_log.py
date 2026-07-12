"""
Decision Audit Log (Sprint 4, Tier 4 #16)

Foundation for measuring any improvement to SentimentAgent / Orchestrator:
every signal carries a sentiment_decision (with shadow-mode would-have-been),
a final_decision, and (later) an outcome_pnl.

Ponytail choices:
- sqlite3 stdlib only. Single file DB, no Postgres, no migrations framework.
- One schema, four methods: ``log_decision``, ``record_outcome``,
  ``get_recent``, ``get_source_stats``. No ORM, no repository pattern.
- All writes are best-effort: failures log a warning, never raise into
  the trading cycle. The audit log is for measurement, not control.
- DB file lives next to trading state JSON (same convention as StateMachine).
- Schema bumps add columns via ``ALTER TABLE ... ADD COLUMN`` at startup;
  we don't run a full migrations framework because the table is internal.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# Schema version: bump when adding columns. We don't run a real migrations
# framework — at startup we attempt ADD COLUMN for everything newer than v1.
SCHEMA_VERSION = 2

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    mode TEXT NOT NULL,                -- 'paper' or 'live'
    timeframe TEXT NOT NULL,
    bar_time TEXT,
    signal TEXT NOT NULL,               -- upstream signal (BUY/SELL/HOLD)
    confidence REAL NOT NULL,           -- upstream confidence
    final_signal TEXT NOT NULL,
    final_confidence REAL NOT NULL,
    approved INTEGER NOT NULL,          -- 0/1
    sentiment_type TEXT,                -- bullish/bearish/neutral
    sentiment_score REAL,
    sentiment_strength TEXT,
    sentiment_adjustment REAL,
    event_proximity_penalty REAL,
    filtered INTEGER NOT NULL DEFAULT 0,
    filter_reason TEXT,
    shadow INTEGER NOT NULL DEFAULT 0,
    shadow_would_signal TEXT,
    shadow_would_confidence REAL,
    shadow_would_filtered INTEGER,
    raw_news_json TEXT,                -- List[Dict] of headlines used
    news_sources_json TEXT,             -- List[str] of sources, aligned with raw_news_json order
    sentiment_result_json TEXT,         -- full sentiment dict
    final_result_json TEXT,             -- full orchestrator dict
    outcome_pnl REAL,
    outcome_recorded_at TEXT,
    outcome_ticket INTEGER
);

CREATE INDEX IF NOT EXISTS idx_decisions_symbol_ts
    ON decisions(symbol, ts);
CREATE INDEX IF NOT EXISTS idx_decisions_outcome
    ON decisions(outcome_recorded_at);
"""


class DecisionLogger:
    """Minimal SQLite-backed decision audit log.

    Thread-safe (single lock; this isn't a hot path).
    """

    def __init__(
        self,
        db_path: str,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.db_path = db_path
        self._lock = threading.Lock()
        if not enabled:
            logger.info("DecisionLogger disabled (enabled=False)")
            return

        # Ensure parent dir exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        logger.info(f"DecisionLogger initialized at {db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.executescript(_SCHEMA)
                # Idempotent ALTERs for columns added in later versions.
                # ponytail: tolerates "duplicate column" by catching & moving on.
                for col, decl in (
                    ("news_sources_json", "TEXT"),
                ):
                    try:
                        conn.execute(f"ALTER TABLE decisions ADD COLUMN {col} {decl}")
                        logger.info(f"DecisionLogger: added column {col}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e).lower():
                            raise
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('version', ?)",
                    (str(SCHEMA_VERSION),),
                )
        except Exception as e:
            logger.error(f"DecisionLogger schema init failed: {e} | disabling")
            self.enabled = False

    def log_decision(
        self,
        symbol: str,
        mode: str,
        timeframe: str,
        bar_time: Optional[datetime],
        upstream_signal: str,
        upstream_confidence: float,
        orchestrator_result: Dict[str, Any],
    ) -> Optional[int]:
        """Append one decision row. Returns row id, or None on failure/disable.

        ``orchestrator_result`` is the full dict from
        ``OrchestratorAgent.analyze()`` — we unpack what we need and stash
        the rest in ``final_result_json`` for forensics.
        """
        if not self.enabled:
            return None

        sentiment = (orchestrator_result.get("agent_results") or {}).get("sentiment") or {}
        shadow = (orchestrator_result.get("agent_results") or {}).get("sentiment") or {}
        shadow_decision = shadow.get("shadow_decision") or {}

        # raw news + sources. The orchestrator result doesn't expose
        # market_data directly, but the trading_system logs the full
        # orchestrator_result under final_result_json — we mine it for the
        # headlines + source tags here.
        raw_news = (orchestrator_result.get("market_data") or {}).get("news_headlines", [])
        raw_news_json = json.dumps(raw_news, default=str)
        # Sources are aligned 1:1 with raw_news order. Headlines without a
        # source key fall back to "unknown" so the per-source breakdown is
        # never silently empty.
        sources = [
            (h.get("source") if isinstance(h, dict) else None) or "unknown"
            for h in raw_news
        ]
        news_sources_json = json.dumps(sources)

        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO decisions (
                        ts, symbol, mode, timeframe, bar_time,
                        signal, confidence,
                        final_signal, final_confidence, approved,
                        sentiment_type, sentiment_score, sentiment_strength,
                        sentiment_adjustment, event_proximity_penalty,
                        filtered, filter_reason,
                        shadow,
                        shadow_would_signal, shadow_would_confidence, shadow_would_filtered,
                        raw_news_json, news_sources_json,
                        sentiment_result_json, final_result_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        datetime.utcnow().isoformat(),
                        symbol,
                        mode,
                        timeframe,
                        bar_time.isoformat() if bar_time else None,
                        upstream_signal,
                        float(upstream_confidence),
                        orchestrator_result.get("final_signal", "HOLD"),
                        float(orchestrator_result.get("final_confidence", 0.0)),
                        1 if orchestrator_result.get("approved") else 0,
                        sentiment.get("sentiment", {}).get("type") if isinstance(sentiment.get("sentiment"), dict) else None,
                        sentiment.get("sentiment", {}).get("score") if isinstance(sentiment.get("sentiment"), dict) else None,
                        sentiment.get("sentiment", {}).get("strength") if isinstance(sentiment.get("sentiment"), dict) else None,
                        sentiment.get("confidence_adjustment"),
                        (sentiment.get("events") or {}).get("adjustment"),
                        1 if sentiment.get("filtered") else 0,
                        sentiment.get("filter_reason"),
                        1 if sentiment.get("shadow_mode") else 0,
                        shadow_decision.get("would_signal"),
                        shadow_decision.get("would_confidence"),
                        1 if shadow_decision.get("would_be_filtered") else 0,
                        raw_news_json,
                        news_sources_json,
                        json.dumps(sentiment, default=str),
                        json.dumps(orchestrator_result, default=str),
                    ),
                )
                row_id = cur.lastrowid
                logger.debug(f"DecisionLogger logged id={row_id} symbol={symbol}")
                return row_id
        except Exception as e:
            logger.warning(f"DecisionLogger.log_decision failed: {e}")
            return None

    def record_outcome(
        self,
        decision_id: int,
        pnl: float,
        ticket: Optional[int] = None,
    ) -> bool:
        """Attach a realized PnL to a previously-logged decision.

        Called from ``_monitor_position`` after the position closes. Until
        the MT5 history-deal fetch TODO is fixed, pnl may be 0.0 — that's
        still useful: it tells us the position closed, even if not how.
        """
        if not self.enabled or decision_id is None:
            return False
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    UPDATE decisions
                       SET outcome_pnl = ?,
                           outcome_recorded_at = ?,
                           outcome_ticket = ?
                     WHERE id = ?
                    """,
                    (float(pnl), datetime.utcnow().isoformat(), ticket, decision_id),
                )
                logger.debug(f"DecisionLogger outcome id={decision_id} pnl={pnl:+.2f}")
                return True
        except Exception as e:
            logger.warning(f"DecisionLogger.record_outcome failed: {e}")
            return False

    def get_recent(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Recent decisions, newest first. Returns list of dicts."""
        if not self.enabled:
            return []
        try:
            with self._lock, self._connect() as conn:
                if symbol:
                    rows = conn.execute(
                        "SELECT * FROM decisions WHERE symbol = ? "
                        "ORDER BY ts DESC LIMIT ?",
                        (symbol, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM decisions ORDER BY ts DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"DecisionLogger.get_recent failed: {e}")
            return []

    def get_source_stats(
        self, symbol: Optional[str] = None, min_decisions: int = 1
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate realized PnL by news source (Sprint 4 #17).

        Attribution model (Ponytail: presence-based, not match-based):
        every source that contributed at least one headline to a decision
        shares the realized outcome equally. Laziest meaningful attribution —
        no per-headline outcome math, just a list of sources per row.

        Returns: ``{source: {decisions, wins, losses, breakeven, total_pnl,
        avg_pnl, win_rate}}``. Sources with fewer than ``min_decisions``
        decisions are filtered out so the breakdown isn't dominated by
        single-shot noise.
        """
        if not self.enabled:
            return {}
        try:
            with self._lock, self._connect() as conn:
                where = (
                    "WHERE symbol = ? AND outcome_pnl IS NOT NULL"
                    if symbol else "WHERE outcome_pnl IS NOT NULL"
                )
                params: tuple = (symbol,) if symbol else ()
                rows = conn.execute(
                    f"SELECT news_sources_json, outcome_pnl FROM decisions {where}",
                    params,
                ).fetchall()

            by_source: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                try:
                    sources = json.loads(r["news_sources_json"] or "[]")
                except (TypeError, ValueError):
                    sources = []
                if not sources:
                    continue
                pnl = float(r["outcome_pnl"])
                # Equal share across contributing sources. Correct for
                # single-source fetches; reasonable enough for mixed.
                share = pnl / len(sources)
                for src in sources:
                    stats = by_source.setdefault(src, {
                        "decisions": 0, "wins": 0, "losses": 0,
                        "breakeven": 0, "total_pnl": 0.0, "avg_pnl": 0.0,
                        "win_rate": 0.0,
                    })
                    stats["decisions"] += 1
                    stats["total_pnl"] += share
                    if share > 0:
                        stats["wins"] += 1
                    elif share < 0:
                        stats["losses"] += 1
                    else:
                        stats["breakeven"] += 1

            for stats in by_source.values():
                stats["avg_pnl"] = stats["total_pnl"] / stats["decisions"] if stats["decisions"] else 0.0
                stats["win_rate"] = stats["wins"] / stats["decisions"] if stats["decisions"] else 0.0

            if min_decisions > 1:
                by_source = {
                    s: st for s, st in by_source.items()
                    if st["decisions"] >= min_decisions
                }
            return by_source
        except Exception as e:
            logger.warning(f"DecisionLogger.get_source_stats failed: {e}")
            return {}

    def get_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Tiny summary: count, win/loss/pending, total pnl. Cheap to compute."""
        if not self.enabled:
            return {}
        try:
            with self._lock, self._connect() as conn:
                where = "WHERE symbol = ?" if symbol else ""
                params: tuple = (symbol,) if symbol else ()
                row = conn.execute(
                    f"""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN outcome_pnl IS NULL THEN 1 ELSE 0 END) AS pending,
                        SUM(CASE WHEN outcome_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                        SUM(CASE WHEN outcome_pnl < 0 THEN 1 ELSE 0 END) AS losses,
                        SUM(CASE WHEN outcome_pnl = 0 AND outcome_recorded_at IS NOT NULL
                                 THEN 1 ELSE 0 END) AS breakeven,
                        COALESCE(SUM(outcome_pnl), 0.0) AS total_pnl,
                        COALESCE(AVG(outcome_pnl), 0.0) AS avg_pnl
                    FROM decisions
                    {where}
                    """,
                    params,
                ).fetchone()
                return dict(row)
        except Exception as e:
            logger.warning(f"DecisionLogger.get_stats failed: {e}")
            return {}

    def close(self) -> None:
        """No-op — sqlite3.Connection is opened per call and auto-closed.
        Kept for symmetry with future pooling."""
        pass


if __name__ == "__main__":
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test_decisions.db")
        logger.info(f"Testing DecisionLogger at {db}")
        dl = DecisionLogger(db)

        # log
        rid = dl.log_decision(
            symbol="XAUUSD", mode="paper", timeframe="M15",
            bar_time=datetime.utcnow(),
            upstream_signal="BUY", upstream_confidence=0.75,
            orchestrator_result={
                "final_signal": "BUY",
                "final_confidence": 0.85,
                "approved": True,
                "agent_results": {
                    "sentiment": {
                        "sentiment": {"type": "bullish", "score": 0.6, "strength": "moderate"},
                        "confidence_adjustment": 0.10,
                        "events": {"adjustment": 0.0},
                        "filtered": False,
                        "filter_reason": "",
                        "shadow_mode": True,
                        "shadow_decision": {
                            "would_signal": "BUY",
                            "would_confidence": 0.75,
                            "would_be_filtered": False,
                        },
                    }
                },
                "market_data": {"news_headlines": [
                    {"headline": "Gold rallies", "source": "web_search"},
                    {"headline": "Fed dovish on cuts", "source": "web_search"},
                ]},
            },
        )
        print(f"logged id={rid}")

        # outcome
        dl.record_outcome(rid, pnl=42.5, ticket=12345)

        # query
        recent = dl.get_recent(symbol="XAUUSD")
        print(f"recent count={len(recent)}; first row keys: {list(recent[0].keys())[:8]}")
        stats = dl.get_stats(symbol="XAUUSD")
        print(f"stats: {stats}")
        assert stats["total"] == 1
        assert stats["wins"] == 1
        assert stats["total_pnl"] == 42.5

        # === Sprint 4 #17: source performance scoring ===
        # Add a few more rows to make per-source averages meaningful.
        # web_search wins 2x (+50, +30), loses 1x (-20).
        # rss_alpha wins 1x (+15).
        rid2 = dl.log_decision(
            symbol="XAUUSD", mode="paper", timeframe="M15",
            bar_time=datetime.utcnow(),
            upstream_signal="BUY", upstream_confidence=0.70,
            orchestrator_result={
                "final_signal": "BUY", "final_confidence": 0.80, "approved": True,
                "agent_results": {"sentiment": {"sentiment": {"type": "bullish", "score": 0.4, "strength": "weak"}, "confidence_adjustment": 0.05, "events": {"adjustment": 0.0}, "filtered": False, "filter_reason": "", "shadow_mode": False}},
                "market_data": {"news_headlines": [
                    {"headline": "Asia markets rally", "source": "web_search"},
                    {"headline": "ECB hawkish", "source": "rss_alpha"},
                ]},
            },
        )
        dl.record_outcome(rid2, pnl=50.0, ticket=12346)

        rid3 = dl.log_decision(
            symbol="XAUUSD", mode="paper", timeframe="M15",
            bar_time=datetime.utcnow(),
            upstream_signal="SELL", upstream_confidence=0.65,
            orchestrator_result={
                "final_signal": "SELL", "final_confidence": 0.70, "approved": True,
                "agent_results": {"sentiment": {"sentiment": {"type": "bearish", "score": 0.3, "strength": "weak"}, "confidence_adjustment": 0.04, "events": {"adjustment": 0.0}, "filtered": False, "filter_reason": "", "shadow_mode": False}},
                "market_data": {"news_headlines": [
                    {"headline": "Dollar strength returns", "source": "web_search"},
                ]},
            },
        )
        dl.record_outcome(rid3, pnl=-20.0, ticket=12347)

        rid4 = dl.log_decision(
            symbol="XAUUSD", mode="paper", timeframe="M15",
            bar_time=datetime.utcnow(),
            upstream_signal="BUY", upstream_confidence=0.72,
            orchestrator_result={
                "final_signal": "BUY", "final_confidence": 0.78, "approved": True,
                "agent_results": {"sentiment": {"sentiment": {"type": "bullish", "score": 0.5, "strength": "moderate"}, "confidence_adjustment": 0.07, "events": {"adjustment": 0.0}, "filtered": False, "filter_reason": "", "shadow_mode": False}},
                "market_data": {"news_headlines": [
                    {"headline": "Inflation ticking up", "source": "rss_alpha"},
                ]},
            },
        )
        dl.record_outcome(rid4, pnl=15.0, ticket=12348)

        # Test get_source_stats
        src_stats = dl.get_source_stats(symbol="XAUUSD")
        print(f"source_stats: {src_stats}")
        # Attribution = per-occurrence: each source entry in the list
        # receives pnl/len(sources). So duplicates of the same source both
        # contribute (e.g. rid1 with 2 web_search headlines adds 42.5, not
        # 21.25). web_search breakdown:
        #   rid1: pnl=42.5, sources=["web_search","web_search"] → 2 × 21.25 = +42.5
        #   rid2: pnl=50.0, sources=["web_search","rss_alpha"]    → 1 × 25.0 = +25.0
        #   rid3: pnl=-20.0, sources=["web_search"]               → 1 × -20.0 = -20.0
        # web_search total = 42.5 + 25.0 - 20.0 = 47.5, 4 decisions, 3 wins
        assert abs(src_stats["web_search"]["total_pnl"] - 47.5) < 0.01, \
            f"web_search total_pnl={src_stats['web_search']['total_pnl']} != 47.5"
        assert src_stats["web_search"]["decisions"] == 4
        assert src_stats["web_search"]["wins"] == 3
        assert src_stats["web_search"]["losses"] == 1
        # rss_alpha: rid2 share=25.0, rid4 share=15.0 → total=40.0
        assert src_stats["rss_alpha"]["total_pnl"] == 40.0
        assert src_stats["rss_alpha"]["decisions"] == 2
        assert abs(src_stats["web_search"]["win_rate"] - 3/4) < 0.01

        # min_decisions filter
        # Add a single-row source to verify min_decisions pruning
        rid5 = dl.log_decision(
            symbol="XAUUSD", mode="paper", timeframe="M15",
            bar_time=datetime.utcnow(),
            upstream_signal="BUY", upstream_confidence=0.60,
            orchestrator_result={
                "final_signal": "BUY", "final_confidence": 0.65, "approved": True,
                "agent_results": {"sentiment": {"sentiment": {"type": "neutral", "score": 0.0, "strength": "none"}, "confidence_adjustment": 0.0, "events": {"adjustment": 0.0}, "filtered": False, "filter_reason": "", "shadow_mode": False}},
                "market_data": {"news_headlines": [
                    {"headline": "Quiet trading day", "source": "rss_beta"},
                ]},
            },
        )
        dl.record_outcome(rid5, pnl=10.0, ticket=12349)
        full = dl.get_source_stats(symbol="XAUUSD", min_decisions=1)
        pruned = dl.get_source_stats(symbol="XAUUSD", min_decisions=2)
        assert "rss_beta" in full, "single-decision source must show under min=1"
        assert "rss_beta" not in pruned, "single-decision source must drop under min=2"
        assert "web_search" in pruned, "multi-decision source must survive"

        # Backwards-compat: schema migration is idempotent — opening the
        # same DB twice must not crash on duplicate ALTER TABLE.
        dl2 = DecisionLogger(db)
        recent2 = dl2.get_recent(symbol="XAUUSD")
        assert len(recent2) == 5, f"expected 5 rows after re-open, got {len(recent2)}"
        # news_sources_json column must be present and parseable
        for row in recent2:
            src = json.loads(row.get("news_sources_json") or "[]")
            assert isinstance(src, list)

        print("DecisionLogger self-test PASS (incl. source stats + migration idempotency)")