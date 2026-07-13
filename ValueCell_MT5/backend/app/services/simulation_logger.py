"""
Simulation decision logger → NeonDB table `simulation_decisions`.
Ponytail: minimal wrapper around existing psycopg2 pool.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

_TABLE = "simulation_decisions"

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    id                     SERIAL PRIMARY KEY,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    symbol                 VARCHAR(10),
    timeframe              VARCHAR(10),
    event_time             TIMESTAMPTZ,
    event_type             VARCHAR(10),
    event_price            NUMERIC(12,5),
    session                VARCHAR(50),
    entry_session          VARCHAR(50),
    final_signal           VARCHAR(10),
    final_confidence       NUMERIC(5,3),
    consensus_level        VARCHAR(20),
    approved               BOOLEAN,
    reject_reason          VARCHAR(200),
    close_reason           VARCHAR(50),
    reasoning              TEXT,
    ms_signal              VARCHAR(10),
    ms_confidence          NUMERIC(5,3),
    ml_signal              VARCHAR(10),
    ml_confidence          NUMERIC(5,3),
    sent_signal            VARCHAR(10),
    sent_confidence        NUMERIC(5,3),
    ml_model_version       VARCHAR(50),
    news_context           JSONB,
    calendar_context       JSONB,
    top_sentiment_headlines JSONB,
    market_structure_state JSONB,
    entry_price            NUMERIC(12,5),
    sl_price               NUMERIC(12,5),
    tp_price               NUMERIC(12,5),
    lot_size               NUMERIC(5,2),
    sl_distance_pips       NUMERIC(8,1),
    tp_distance_pips       NUMERIC(8,1),
    outcome                VARCHAR(10),
    outcome_bar_time       TIMESTAMPTZ,
    pnl_pips               NUMERIC(8,1),
    spread_cost            NUMERIC(6,2),
    commission             NUMERIC(6,2),
    net_profit_usd         NUMERIC(10,2)
);
"""

_COLS = [
    "symbol", "timeframe", "event_time", "event_type", "event_price",
    "session", "entry_session", "final_signal", "final_confidence",
    "consensus_level", "approved", "reject_reason", "close_reason", "reasoning",
    "ms_signal", "ms_confidence", "ml_signal", "ml_confidence",
    "sent_signal", "sent_confidence", "ml_model_version",
    "news_context", "calendar_context", "top_sentiment_headlines",
    "market_structure_state", "entry_price", "sl_price", "tp_price",
    "lot_size", "sl_distance_pips", "tp_distance_pips",
    "outcome", "outcome_bar_time", "pnl_pips",
    "spread_cost", "commission", "net_profit_usd",
]

_INSERT_SQL = (
    f"INSERT INTO {_TABLE} ({', '.join(_COLS)}) "
    f"VALUES ({', '.join(['%s'] * len(_COLS))})"
)

_PIP = 0.1  # 1 pip for XAUUSD


def _pips(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(abs(a - b) / _PIP, 1)


def _jsonb(v: Any) -> Optional[str]:
    if v is None:
        return None
    return json.dumps(v) if not isinstance(v, str) else v


def _row(data: Dict[str, Any]) -> tuple:
    ep = data.get("entry_price")
    sl = data.get("sl_price")
    tp = data.get("tp_price")
    sl_pips = data.get("sl_distance_pips") or _pips(ep, sl)
    tp_pips = data.get("tp_distance_pips") or _pips(ep, tp)
    return tuple([
        data.get("symbol"),
        data.get("timeframe"),
        data.get("event_time"),
        data.get("event_type"),
        data.get("event_price"),
        data.get("session"),
        data.get("entry_session"),
        data.get("final_signal"),
        data.get("final_confidence"),
        data.get("consensus_level"),
        data.get("approved"),
        data.get("reject_reason"),
        data.get("close_reason"),
        data.get("reasoning"),
        data.get("ms_signal"),
        data.get("ms_confidence"),
        data.get("ml_signal"),
        data.get("ml_confidence"),
        data.get("sent_signal"),
        data.get("sent_confidence"),
        data.get("ml_model_version"),
        _jsonb(data.get("news_context")),
        _jsonb(data.get("calendar_context")),
        _jsonb(data.get("top_sentiment_headlines")),
        _jsonb(data.get("market_structure_state")),
        ep,
        sl,
        tp,
        data.get("lot_size"),
        sl_pips,
        tp_pips,
        data.get("outcome"),
        data.get("outcome_bar_time"),
        data.get("pnl_pips"),
        data.get("spread_cost"),
        data.get("commission"),
        data.get("net_profit_usd"),
    ])


from pathlib import Path

_QUEUE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sim_fallback_queue.json"


def _serialize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    res = {}
    for k, v in d.items():
        if isinstance(v, datetime):
            res[k] = {"__type__": "datetime", "value": v.isoformat()}
        else:
            res[k] = v
    return res


def _deserialize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    res = {}
    for k, v in d.items():
        if isinstance(v, dict) and v.get("__type__") == "datetime":
            res[k] = datetime.fromisoformat(v["value"])
        else:
            res[k] = v
    return res


class SimulationLogger:
    """Insert simulation decisions into NeonDB. Never raises — failures are logged to a local fallback queue."""

    _initialized = False

    def ensure_table(self) -> None:
        if self._initialized:
            return
        try:
            from app.core.database import get_db_conn, is_pool_ready
            if not is_pool_ready():
                return
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(_CREATE_SQL)
                conn.commit()
            SimulationLogger._initialized = True
            logger.info(f"[SimLogger] Table `{_TABLE}` ready.")
        except Exception as e:
            logger.warning(f"[SimLogger] ensure_table failed: {e}")

    def _write_to_queue(self, rows: List[Dict[str, Any]]) -> None:
        try:
            _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if _QUEUE_FILE.exists():
                try:
                    with open(_QUEUE_FILE, "r") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            
            existing.extend([_serialize_dict(r) for r in rows])
            with open(_QUEUE_FILE, "w") as f:
                json.dump(existing, f, indent=4)
            logger.info(f"[SimLogger] Wrote {len(rows)} failed decisions to local queue buffer.")
        except Exception as e:
            logger.error(f"[SimLogger] Failed to write to fallback queue: {e}")

    def _flush_queue(self) -> None:
        from app.core.database import is_pool_ready
        if not is_pool_ready() or not _QUEUE_FILE.exists():
            return
        try:
            with open(_QUEUE_FILE, "r") as f:
                raw_rows = json.load(f)
            if not raw_rows:
                return
            
            rows = [_deserialize_dict(r) for r in raw_rows]
            logger.info(f"[SimLogger] Database reconnected. Flushing {len(rows)} queued decisions...")
            self.ensure_table()
            
            from app.core.database import get_db_conn
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.executemany(_INSERT_SQL, [_row(r) for r in rows])
                conn.commit()
                
            _QUEUE_FILE.unlink(missing_ok=True)
            logger.info(f"[SimLogger] Successfully flushed {len(rows)} queued decisions to NeonDB.")
        except Exception as e:
            logger.warning(f"[SimLogger] Failed to flush fallback queue: {e}")

    def log_decision(self, data: Dict[str, Any]) -> None:
        try:
            self._flush_queue()
            from app.core.database import get_db_conn, is_pool_ready
            if not is_pool_ready():
                self._write_to_queue([data])
                return
            self.ensure_table()
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(_INSERT_SQL, _row(data))
                conn.commit()
        except Exception as e:
            logger.warning(f"[SimLogger] log_decision failed, buffering: {e}")
            self._write_to_queue([data])

    def log_decisions_bulk(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            self._flush_queue()
            from app.core.database import get_db_conn, is_pool_ready
            if not is_pool_ready():
                self._write_to_queue(rows)
                return
            self.ensure_table()
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.executemany(_INSERT_SQL, [_row(r) for r in rows])
                conn.commit()
            logger.info(f"[SimLogger] Bulk logged {len(rows)} decisions.")
        except Exception as e:
            logger.warning(f"[SimLogger] log_decisions_bulk failed, buffering: {e}")
            self._write_to_queue(rows)


# ponytail: module-level singleton, avoids re-instantiation overhead
_sim_logger = SimulationLogger()
