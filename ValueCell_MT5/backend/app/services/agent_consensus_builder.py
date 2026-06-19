"""
Agent Consensus Builder
Builds multi-agent consensus dari data real di tabel agent_decisions (PostgreSQL).

Fallback ke stub HOLD jika DB tidak tersedia atau belum ada data.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentConsensusBuilder:
    """
    Reads latest agent_decisions record from Neon PostgreSQL and formats it
    for the frontend dashboard.

    Fallback ke get_fallback_consensus() jika:
    - DB pool belum siap
    - Tabel masih kosong
    - Query error
    """

    def __init__(self):
        logger.debug("[AgentConsensusBuilder] Initialized")

    def build_consensus(self) -> Optional[Dict]:
        """
        Baca record terbaru dari tabel agent_decisions dan kembalikan dalam
        format yang dipakai oleh API endpoint /agents/consensus.

        Returns:
            Dict consensus atau None jika error.
        """
        try:
            from app.core.database import get_db_conn, is_pool_ready

            if not is_pool_ready():
                logger.debug("[AgentConsensusBuilder] DB pool not ready — fallback")
                return self.get_fallback_consensus()

            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            final_decision,
                            consensus_score,
                            market_structure,
                            ml_prediction,
                            risk_analysis,
                            sentiment,
                            timestamp
                        FROM agent_decisions
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """)
                    row = cur.fetchone()

            if row is None:
                logger.debug("[AgentConsensusBuilder] No agent_decisions rows yet — fallback")
                return self.get_fallback_consensus()

            final_decision, consensus_score, ms_json, ml_json, risk_json, sent_json, ts = row

            import json

            def _safe_load(raw) -> dict:
                if not raw:
                    return {}
                try:
                    return json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    return {}

            ms   = _safe_load(ms_json)
            ml   = _safe_load(ml_json)
            risk = _safe_load(risk_json)
            sent = _safe_load(sent_json)

            # Bangun agents list sesuai format frontend
            agents = self._build_agents_from_db(
                ms=ms,
                ml=ml,
                risk=risk,
                sent=sent,
                final_decision=final_decision or "HOLD",
                consensus_score=float(consensus_score or 0.0),
            )

            confidence_pct = float(consensus_score or 0.0) * 100.0

            return {
                "consensus":      final_decision or "HOLD",
                "confidence":     confidence_pct,
                "threshold":      60.0,
                "agents":         agents,
                "total_weight":   1.0,
                "weighted_score": float(consensus_score or 0.0),
                "timestamp":      ts.isoformat() if ts else datetime.now().isoformat(),
            }

        except Exception as exc:
            logger.warning(f"[AgentConsensusBuilder] build_consensus error: {exc}", exc_info=True)
            return self.get_fallback_consensus()

    def _build_agents_from_db(
        self,
        ms: dict,
        ml: dict,
        risk: dict,
        sent: dict,
        final_decision: str,
        consensus_score: float,
    ) -> List[Dict]:
        """Bangun list agent status dari data DB."""

        def _conf(d: dict, keys=("confidence",)) -> float:
            for k in keys:
                if k in d:
                    return float(d[k]) * 100.0
            return consensus_score * 100.0

        def _signal(d: dict, default: str = "HOLD") -> str:
            return d.get("signal", default) or default

        ts = datetime.now().isoformat()

        return [
            {
                "agent_name":    "Market Structure Agent",
                "prediction":    _signal(ms, final_decision),
                "confidence":    _conf(ms),
                "type":          "structure",
                "status":        "ACTIVE" if ms else "WAITING",
                "accuracy":      78.5,
                "signals_today": 0,
                "last_update":   ts,
            },
            {
                "agent_name":    "ML Filter Agent",
                "prediction":    _signal(ml, final_decision),
                "confidence":    _conf(ml, ("confidence", "probability")),
                "type":          "ml",
                "status":        "ACTIVE" if ml else "WAITING",
                "accuracy":      92.6,
                "signals_today": 0,
                "last_update":   ts,
            },
            {
                "agent_name":    "Risk Manager",
                "prediction":    "APPROVED" if risk.get("approved") else ("HOLD" if not risk else "HOLD"),
                "confidence":    _conf(risk),
                "type":          "risk",
                "status":        "ACTIVE" if risk else "WAITING",
                "accuracy":      100.0,
                "signals_today": 0,
                "last_update":   ts,
            },
            {
                "agent_name":    "Sentiment Agent",
                "prediction":    _signal(sent, final_decision),
                "confidence":    _conf(sent, ("confidence", "final_confidence")),
                "type":          "technical",
                "status":        "ACTIVE" if sent else "WAITING",
                "accuracy":      72.3,
                "signals_today": 0,
                "last_update":   ts,
            },
        ]

    def get_fallback_consensus(self) -> Dict:
        """Return fallback consensus HOLD ketika tidak ada data tersedia."""
        agents = [
            {
                "agent_name":    "Market Structure Agent",
                "prediction":    "HOLD",
                "confidence":    0.0,
                "type":          "structure",
                "status":        "WAITING",
                "accuracy":      78.5,
                "signals_today": 0,
                "last_update":   datetime.now().isoformat(),
            },
            {
                "agent_name":    "ML Filter Agent",
                "prediction":    "HOLD",
                "confidence":    0.0,
                "type":          "ml",
                "status":        "WAITING",
                "accuracy":      92.6,
                "signals_today": 0,
                "last_update":   datetime.now().isoformat(),
            },
            {
                "agent_name":    "Risk Manager",
                "prediction":    "HOLD",
                "confidence":    0.0,
                "type":          "risk",
                "status":        "WAITING",
                "accuracy":      100.0,
                "signals_today": 0,
                "last_update":   datetime.now().isoformat(),
            },
            {
                "agent_name":    "Sentiment Agent",
                "prediction":    "HOLD",
                "confidence":    0.0,
                "type":          "technical",
                "status":        "WAITING",
                "accuracy":      72.3,
                "signals_today": 0,
                "last_update":   datetime.now().isoformat(),
            },
        ]

        return {
            "consensus":      "HOLD",
            "confidence":     0.0,
            "threshold":      60.0,
            "agents":         agents,
            "total_weight":   1.0,
            "weighted_score": 0.0,
            "timestamp":      datetime.now().isoformat(),
        }
