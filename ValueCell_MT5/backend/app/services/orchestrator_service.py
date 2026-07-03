"""
Orchestrator Service - Bridge antara Track 1 Pipeline dan OrchestratorAgent nyata.

Mengimport OrchestratorAgent dari python/valuecell dan menjalankannya
dengan data real dari candles M15 yang sudah difetch oleh Track 1 Pipeline.

Fallback ke HOLD apabila:
- MT5 tidak terkoneksi (tidak ada candle)
- OrchestratorAgent gagal import/run
- Data tidak cukup untuk analisis
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# ─── Import service berita dan kalender ekonomi ────────────────────────────────
try:
    from app.services.news_feed_service import fetch_gold_news_headlines
    from app.services.economic_calendar_service import get_upcoming_events
    _SENTIMENT_SERVICES_AVAILABLE = True
except ImportError as _e:
    _SENTIMENT_SERVICES_AVAILABLE = False
    logging.getLogger(__name__).warning(
        f"[OrchestratorService] Sentiment services not available: {_e} "
        "— news_headlines dan upcoming_events akan kosong"
    )

logger = logging.getLogger(__name__)

# ─── Path injection agar python/valuecell bisa diimport dari backend ──────────
_PYTHON_PATH = Path(__file__).resolve().parents[3] / "python"
if str(_PYTHON_PATH) not in sys.path:
    sys.path.insert(0, str(_PYTHON_PATH))
    logger.info(f"[OrchestratorService] Added to sys.path: {_PYTHON_PATH}")

# ─── Lazy-load OrchestratorAgent agar startup backend tidak crash ─────────────
_orchestrator = None
_orchestrator_error: Optional[str] = None


def _get_orchestrator():
    """Singleton OrchestratorAgent — hanya diinit sekali."""
    global _orchestrator, _orchestrator_error

    if _orchestrator is not None:
        return _orchestrator

    if _orchestrator_error is not None:
        # sudah pernah gagal, jangan retry terus tiap cycle
        return None

    try:
        from valuecell.agents.orchestrator_agent import OrchestratorAgent

        _orchestrator = OrchestratorAgent(
            consensus_threshold=0.60,
            market_structure={"swing_length": 5, "timeframe": "M15"},
            risk_management={"account_balance": 1000.0},
        )
        logger.info("[OrchestratorService] OrchestratorAgent initialized OK")
        return _orchestrator

    except Exception as exc:
        _orchestrator_error = str(exc)
        logger.warning(
            f"[OrchestratorService] OrchestratorAgent init failed: {exc} "
            f"— will use fallback HOLD for agent_decisions"
        )
        return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _compute_ema_series(closes: List[float], period: int = 200) -> List[Optional[float]]:
    """Hitung EMA untuk list close prices."""
    if len(closes) < period:
        return [None] * len(closes)
    k = 2.0 / (period + 1)
    emas: List[Optional[float]] = [None] * (period - 1)
    ema = sum(closes[:period]) / period
    emas.append(ema)
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
        emas.append(ema)
    return emas


def _candles_to_dataframe(candles: List[Dict]) -> "pd.DataFrame":
    """Konversi list candle dict dari MT5Manager ke DataFrame untuk agents."""
    import pandas as pd

    if not candles:
        return pd.DataFrame()

    closes = [c["close"] for c in candles]
    emas = _compute_ema_series(closes, period=200)

    rows = []
    for i, c in enumerate(candles):
        rows.append({
            "time":   pd.Timestamp.utcfromtimestamp(c["time"]),
            "open":   float(c["open"]),
            "high":   float(c["high"]),
            "low":    float(c["low"]),
            "close":  float(c["close"]),
            "volume": int(c["volume"]),
            "ema200": round(emas[i], 2) if emas[i] is not None else closes[i],
        })

    return pd.DataFrame(rows)


def _get_session(ts: datetime) -> str:
    """Tentukan sesi trading dari jam UTC."""
    hour = ts.hour
    if 22 <= hour or hour < 8:
        return "Sydney"
    elif 8 <= hour < 12:
        return "London"
    elif 12 <= hour < 16:
        return "NewYork"
    else:
        return "Overlap"


def _fallback_decision() -> Dict[str, Any]:
    """Return decision dict fallback HOLD ketika orchestrator tidak tersedia."""
    return {
        "timestamp":        datetime.utcnow(),
        "symbol":           "XAUUSD",
        "timeframe":        "M15",
        "market_structure": json.dumps({"signal": "HOLD", "confidence": 0.0, "note": "orchestrator_unavailable"}),
        "ml_prediction":    json.dumps({"signal": "HOLD", "confidence": 0.0}),
        "risk_analysis":    json.dumps({"approved": False}),
        "sentiment":        json.dumps({"signal": "HOLD", "confidence": 0.0}),
        "consensus_score":  0.0,
        "final_decision":   "HOLD",
        "trade_executed":   False,
    }


def _fetch_recent_structures(symbol: str = "XAUUSD", count: int = 50) -> List[Dict]:
    """Fetch recent structure events from realtime_structures table."""
    from app.core.database import get_db_conn, is_pool_ready
    if not is_pool_ready():
        logger.debug("[OrchestratorService] DB pool not ready, cannot fetch structures")
        return []
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_type, direction, price, timestamp
                    FROM realtime_structures
                    WHERE symbol = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (symbol, count)
                )
                rows = cur.fetchall()
        
        events = []
        for r_type, r_dir, r_price, r_time in rows:
            # Format type as event_type_direction, e.g. BOS_BULLISH, CHOCH_BEARISH, etc.
            evt_type = f"{r_type.upper()}_{r_dir.upper()}" if r_dir else r_type.upper()
            events.append({
                "type": evt_type,
                "price": float(r_price),
                "time": r_time
            })
        # Reverse to chronological order (oldest -> newest)
        events.reverse()
        logger.debug(f"[OrchestratorService] Fetched {len(events)} structures from DB")
        return events
    except Exception as exc:
        logger.warning(f"[OrchestratorService] Failed to fetch structures: {exc}")
        return []


def _fetch_news_headlines_safe() -> List[str]:
    """Fetch news headlines with full fallback protection."""
    if not _SENTIMENT_SERVICES_AVAILABLE:
        return []
    try:
        return fetch_gold_news_headlines(max_age_hours=24, max_items=20)
    except Exception as exc:
        logger.warning(f"[OrchestratorService] News feed failed: {exc} — using empty headlines")
        return []


def _fetch_economic_events_safe() -> List[Dict[str, Any]]:
    """Fetch economic calendar events with full fallback protection."""
    if not _SENTIMENT_SERVICES_AVAILABLE:
        return []
    try:
        return get_upcoming_events(hours_ahead=24)
    except Exception as exc:
        logger.warning(f"[OrchestratorService] Economic calendar failed: {exc} — using empty events")
        return []


# ─── Public API ───────────────────────────────────────────────────────────────

def build_agent_decision(
    candles_m15: List[Dict],
    candles_h1: Optional[List[Dict]] = None,
    candles_h4: Optional[List[Dict]] = None,
    symbol: str = "XAUUSD",
) -> Dict[str, Any]:
    """
    Jalankan OrchestratorAgent dengan data candle real dan return dict
    yang siap diinsert ke tabel `agent_decisions`.

    Args:
        candles_m15: List candle M15 dari MT5Manager.get_candles()
        candles_h1:  List candle H1 (opsional, untuk ML Agent & H1 EMA scoring)
        candles_h4:  List candle H4 (opsional, untuk H4 EMA scoring di MSA v2)
        symbol:      Simbol trading

    Returns:
        Dict siap INSERT ke agent_decisions, atau fallback HOLD jika gagal.
    """
    orchestrator = _get_orchestrator()

    # Jika agent tidak bisa diinit, return fallback
    if orchestrator is None:
        logger.debug("[OrchestratorService] No orchestrator — returning fallback HOLD")
        return _fallback_decision()

    # Perlu minimal 30 candle untuk deteksi swing (swing_length*2 + buffer)
    if not candles_m15 or len(candles_m15) < 30:
        logger.debug(f"[OrchestratorService] Not enough candles ({len(candles_m15 or [])}) — fallback")
        return _fallback_decision()

    try:
        import pandas as pd

        df_m15 = _candles_to_dataframe(candles_m15)
        df_h1  = _candles_to_dataframe(candles_h1) if candles_h1 else None
        df_h4  = _candles_to_dataframe(candles_h4) if candles_h4 else None

        current_bar_raw = candles_m15[-1]
        current_bar = {
            "time":   pd.Timestamp.utcfromtimestamp(current_bar_raw["time"]),
            "open":   float(current_bar_raw["open"]),
            "high":   float(current_bar_raw["high"]),
            "low":    float(current_bar_raw["low"]),
            "close":  float(current_bar_raw["close"]),
            "volume": int(current_bar_raw["volume"]),
        }

        # ATR sederhana dari 14 candle terakhir
        highs  = [c["high"] for c in candles_m15[-14:]]
        lows   = [c["low"]  for c in candles_m15[-14:]]
        atr    = sum(h - l for h, l in zip(highs, lows)) / len(highs)

        session = _get_session(datetime.utcnow())

        market_data = {
            "df":               df_m15,
            "current_bar":      current_bar,
            "structure_events": _fetch_recent_structures(symbol, count=50),
            "m15_history":      df_m15,
            "h1_data":          df_h1,
            "h4_data":          df_h4,   # ← H4 EMA scoring untuk MSA v2
            "atr":              atr,
            "session":          session,
            "news_headlines":   _fetch_news_headlines_safe(),
            "upcoming_events":  _fetch_economic_events_safe(),
        }

        result = orchestrator.analyze(
            market_data=market_data,
            symbol=symbol,
            timeframe="M15",
        )

        # Petakan hasil orchestrator ke schema tabel agent_decisions
        agent_results = result.get("agent_results", {})

        def _dump(key: str) -> str:
            data = agent_results.get(key, {})
            # Hapus key yg tidak JSON-serializable (datetime, dll)
            clean = {k: v for k, v in data.items()
                     if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            return json.dumps(clean, default=str)

        decision: Dict[str, Any] = {
            "timestamp":        datetime.utcnow(),
            "symbol":           symbol,
            "timeframe":        "M15",
            "market_structure": _dump("market_structure"),
            "ml_prediction":    _dump("ml_prediction"),
            "risk_analysis":    _dump("risk_management"),
            "sentiment":        _dump("sentiment"),
            "consensus_score":  round(result.get("final_confidence", 0.0), 4),
            "final_decision":   result.get("final_signal", "HOLD"),
            "trade_executed":   False,
        }

        logger.info(
            f"[OrchestratorService] Decision: {decision['final_decision']} "
            f"| Score: {decision['consensus_score']:.4f} "
            f"| Level: {result.get('consensus_level', 'unknown')}"
        )
        return decision

    except Exception as exc:
        logger.warning(f"[OrchestratorService] build_agent_decision failed: {exc}", exc_info=True)
        return _fallback_decision()
