"""
Track 1 Real-Time Pipeline

Background worker that periodically:
1. Fetches OHLCV rates from MT5 (M15, H1, H4)
2. Calculates EMA-200 dynamically
3. Upserts data into `realtime_ohlcv` table in Neon PostgreSQL
4. Detects market structure events (HH/LL/CHoCH/BoS) via simple swing detection
5. Inserts new structure events into `realtime_structures`
6. Syncs open MT5 positions into `trades`
7. Records agent decision snapshots into `agent_decisions`

This module is started as an asyncio background task during FastAPI lifespan startup
and stopped gracefully during shutdown.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import os
import glob
import csv

logger = logging.getLogger(__name__)

# ─── Timeframes tracked by Track 1 ───────────────────────────────────────────
TIMEFRAMES = ["M15", "H1", "H4"]
CANDLE_COUNT = 250  # Enough candles to compute EMA-200 reliably

# ─── EMA helper ──────────────────────────────────────────────────────────────

def _compute_ema(closes: List[float], period: int = 200) -> List[Optional[float]]:
    """
    Compute Exponential Moving Average (EMA) for a list of close prices.

    Returns a list of the same length; the first (period-1) entries are None.
    """
    if len(closes) < period:
        return [None] * len(closes)

    k = 2.0 / (period + 1)
    emas: List[Optional[float]] = [None] * (period - 1)
    ema = sum(closes[:period]) / period  # seed with SMA
    emas.append(ema)

    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
        emas.append(ema)

    return emas


# ─── Simple swing structure detector ─────────────────────────────────────────

class _SwingDetector:
    """
    Lightweight Market Structure detector.

    Tracks Higher-Highs (HH), Higher-Lows (HL), Lower-Lows (LL), Lower-Highs (LH),
    CHoCH (Change of Character), and BoS (Break of Structure).

    State is kept per-timeframe so each timeframe has independent context.
    """

    def __init__(self):
        # Per-timeframe state: last swing high/low
        self._state: Dict[str, Dict] = {}

    def _get_state(self, timeframe: str) -> Dict:
        if timeframe not in self._state:
            self._state[timeframe] = {
                "last_hh": None,
                "last_ll": None,
                "last_hl": None,
                "last_lh": None,
                "phase": "ACCUMULATION",
            }
        return self._state[timeframe]

    def detect(
        self,
        candles: List[Dict],
        timeframe: str,
        symbol: str,
        swing_lookback: int = 5,
    ) -> List[Dict]:
        """
        Detect new swing events from the latest candle data.

        Args:
            candles: Ordered list of OHLCV dicts (oldest → newest).
            timeframe: e.g. "M15"
            symbol: e.g. "XAUUSD"
            swing_lookback: Candles on each side to qualify as a swing pivot.

        Returns:
            List of newly detected structure events (may be empty).
        """
        if len(candles) < swing_lookback * 2 + 1:
            return []

        state = self._get_state(timeframe)
        events: List[Dict] = []

        # Analyse all candles except the most recent (not yet confirmed)
        window = candles[-(swing_lookback * 2 + 10):-1]

        for i in range(swing_lookback, len(window) - swing_lookback):
            candle = window[i]
            left = window[i - swing_lookback: i]
            right = window[i + 1: i + swing_lookback + 1]

            hi = candle["high"]
            lo = candle["low"]
            ts = datetime.utcfromtimestamp(candle["time"])

            # ── Swing High ────────────────────────────────────────────────
            if all(hi > c["high"] for c in left) and all(hi > c["high"] for c in right):
                event_type = None
                if state["last_hh"] is None or hi > state["last_hh"]:
                    event_type = "HH"
                    state["last_hh"] = hi
                    state["phase"] = "BULLISH"
                elif state["last_hh"] is not None and hi < state["last_hh"]:
                    # Lower High — potential CHoCH if we had a bullish phase
                    event_type = "LH"
                    state["last_lh"] = hi
                    if state["phase"] == "BULLISH":
                        events.append(
                            _make_event(ts, symbol, timeframe, "CHoCH", "BEARISH", hi)
                        )
                        state["phase"] = "BEARISH"

                if event_type in ("HH", "LH"):
                    events.append(
                        _make_event(ts, symbol, timeframe, event_type, "BULLISH" if event_type == "HH" else "BEARISH", hi)
                    )

            # ── Swing Low ─────────────────────────────────────────────────
            if all(lo < c["low"] for c in left) and all(lo < c["low"] for c in right):
                event_type = None
                if state["last_ll"] is None or lo < state["last_ll"]:
                    event_type = "LL"
                    state["last_ll"] = lo
                    state["phase"] = "BEARISH"
                elif state["last_ll"] is not None and lo > state["last_ll"]:
                    # Higher Low — potential CHoCH if we had a bearish phase
                    event_type = "HL"
                    state["last_hl"] = lo
                    if state["phase"] == "BEARISH":
                        events.append(
                            _make_event(ts, symbol, timeframe, "CHoCH", "BULLISH", lo)
                        )
                        state["phase"] = "BULLISH"

                if event_type in ("LL", "HL"):
                    events.append(
                        _make_event(ts, symbol, timeframe, event_type, "BEARISH" if event_type == "LL" else "BULLISH", lo)
                    )

        return events


def _make_event(
    ts: datetime,
    symbol: str,
    timeframe: str,
    event_type: str,
    direction: str,
    price: float,
) -> Dict:
    """Build a structure event dict ready for DB insertion."""
    return {
        "timestamp": ts,
        "symbol": symbol,
        "timeframe": timeframe,
        "event_type": event_type,
        "direction": direction,
        "price": price,
        "phase": None,
        "session": _get_session(ts),
        "source": "python_detector",
        "triggered_trade": False,
    }


def _get_session(ts: datetime) -> str:
    """Classify UTC hour into trading session."""
    hour = ts.hour
    if 22 <= hour or hour < 8:
        return "SYDNEY"
    elif 8 <= hour < 12:
        return "LONDON"
    elif 12 <= hour < 16:
        return "NEW_YORK"
    else:
        return "OVERLAP"


def _read_new_csv_events(filepath: Path, last_processed_time: Optional[datetime]) -> List[Dict]:
    """Read new market structure events from LLHHBOSData CSV file."""
    events = []
    if not filepath.exists():
        return events

    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        # Find header index
        header_idx = -1
        for idx, line in enumerate(lines):
            if line.startswith("Type,Direction/Action"):
                header_idx = idx
                break

        if header_idx == -1:
            return events

        # Parse lines after header_idx
        reader = csv.DictReader(lines[header_idx:])
        for row in reader:
            # Clean keys/values
            row = {k.strip(): v.strip() for k, v in row.items() if k is not None and v is not None}

            time_str = row.get("Time")
            if not time_str:
                continue

            try:
                # Format: 2026.01.05 04:45:00
                event_time = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
            except ValueError:
                continue

            # If we already processed this event, skip
            if last_processed_time and event_time <= last_processed_time:
                continue

            raw_type = row.get("Type", "")
            raw_dir = row.get("Direction/Action", "")

            # Normalize event_type
            event_type = "BoS"
            if "choch" in raw_type.lower():
                event_type = "CHoCH"
            elif "hh" in raw_type.lower():
                event_type = "HH"
            elif "ll" in raw_type.lower():
                event_type = "LL"

            # Normalize direction
            direction = "Bullish"
            if "bearish" in raw_dir.lower() or "bearish" in raw_type.lower():
                direction = "Bearish"
            elif "update" in raw_dir.lower():
                if "bullish" in raw_type.lower() or "hh" in raw_type.lower():
                    direction = "Bullish"
                elif "bearish" in raw_type.lower() or "ll" in raw_type.lower():
                    direction = "Bearish"

            try:
                price = float(row.get("Price", 0.0))
            except ValueError:
                price = 0.0

            tf = row.get("Timeframe", "M15")

            events.append({
                "timestamp": event_time,
                "symbol": "XAUUSD",
                "timeframe": tf,
                "event_type": event_type,
                "direction": direction,
                "price": price,
                "phase": None,
                "session": _get_session(event_time),
                "source": "csv_polling",
                "triggered_trade": False
            })

    except Exception as e:
        logger.error(f"[Track1] Error parsing CSV structure file {filepath}: {e}")

    return events


# ─── DB insertion helpers ─────────────────────────────────────────────────────

def _upsert_ohlcv(cur, rows: List[Dict]) -> int:
    """Bulk-upsert rows into `realtime_ohlcv`. Returns inserted count."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        cur.execute(
            """
            INSERT INTO realtime_ohlcv
                (timestamp, symbol, timeframe, open, high, low, close, volume, ema200, source)
            VALUES
                (%(timestamp)s, %(symbol)s, %(timeframe)s,
                 %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(ema200)s, %(source)s)
            ON CONFLICT (timestamp, symbol, timeframe, source) DO UPDATE SET
                open   = EXCLUDED.open,
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume,
                ema200 = EXCLUDED.ema200
            """,
            row,
        )
        inserted += 1

    return inserted


def _insert_structures(cur, events: List[Dict]) -> int:
    """Insert structure events that don't already exist. Returns inserted count."""
    if not events:
        return 0

    inserted = 0
    for ev in events:
        # Avoid duplicate event at same timestamp/symbol/timeframe/event_type
        cur.execute(
            """
            INSERT INTO realtime_structures
                (timestamp, symbol, timeframe, event_type, direction, price,
                 phase, session, source, triggered_trade)
            SELECT %(timestamp)s, %(symbol)s, %(timeframe)s, %(event_type)s,
                   %(direction)s, %(price)s, %(phase)s, %(session)s, %(source)s,
                   %(triggered_trade)s
            WHERE NOT EXISTS (
                SELECT 1 FROM realtime_structures
                WHERE timestamp = %(timestamp)s
                  AND symbol    = %(symbol)s
                  AND timeframe = %(timeframe)s
                  AND event_type= %(event_type)s
            )
            """,
            ev,
        )
        if cur.rowcount:
            inserted += 1

    return inserted


def _upsert_trades(cur, positions: List[Dict]) -> int:
    """Upsert open MT5 positions into `trades`. Returns upserted count."""
    if not positions:
        return 0

    upserted = 0
    for pos in positions:
        ticket = pos.get("ticket")
        if ticket is None:
            continue

        cur.execute(
            """
            INSERT INTO trades
                (ticket, timestamp, symbol, type, entry_price, stop_loss, take_profit, lot_size)
            VALUES
                (%(ticket)s, %(time)s, %(symbol)s, %(type)s,
                 %(price_open)s, %(sl)s, %(tp)s, %(volume)s)
            ON CONFLICT (ticket) DO UPDATE SET
                stop_loss   = EXCLUDED.stop_loss,
                take_profit = EXCLUDED.take_profit,
                lot_size    = EXCLUDED.lot_size
            """,
            {
                "ticket":     ticket,
                "time":       pos.get("time", datetime.utcnow()),
                "symbol":     pos.get("symbol", "XAUUSD"),
                "type":       pos.get("type", "BUY"),
                "price_open": pos.get("price_open"),
                "sl":         pos.get("sl") or None,
                "tp":         pos.get("tp") or None,
                "volume":     pos.get("volume"),
            },
        )
        upserted += 1

    return upserted


def _insert_agent_decision(cur, decision: Dict) -> None:
    """Insert one agent decision snapshot into `agent_decisions`."""
    # Derive session from timestamp if not already set
    if "session" not in decision or not decision.get("session"):
        ts = decision.get("timestamp")
        if ts:
            decision["session"] = _get_session(ts) if isinstance(ts, datetime) else "UNKNOWN"
        else:
            decision["session"] = "UNKNOWN"

    cur.execute(
        """
        INSERT INTO agent_decisions
            (timestamp, symbol, timeframe, market_structure, ml_prediction,
             risk_analysis, sentiment, consensus_score, final_decision, trade_executed,
             session)
        VALUES
            (%(timestamp)s, %(symbol)s, %(timeframe)s,
             %(market_structure)s, %(ml_prediction)s,
             %(risk_analysis)s, %(sentiment)s,
             %(consensus_score)s, %(final_decision)s, %(trade_executed)s,
             %(session)s)
        """,
        decision,
    )



def _insert_sentiment_log(cur, timestamp, symbol, sentiment_json_str: str) -> None:
    """Parse sentiment JSON and insert into `agent_sentiment_logs`."""
    if not sentiment_json_str:
        return
    try:
        data = json.loads(sentiment_json_str)
        if not data or "sentiment" not in data or "events" not in data:
            return
            
        sent_details = data["sentiment"]
        evt_details = data["events"]
        
        sentiment_score = float(sent_details.get("score", 0.0))
        sentiment_label = str(sent_details.get("type", "NEUTRAL")).upper()
        sentiment_strength = str(sent_details.get("strength", "none"))
        
        # Count news categories from keyword matches
        bullish_news_count = sum(1 for item in sent_details.get("keyword_matches", []) if isinstance(item, (list, tuple)) and len(item) > 0 and item[0] == "bullish")
        bearish_news_count = sum(1 for item in sent_details.get("keyword_matches", []) if isinstance(item, (list, tuple)) and len(item) > 0 and item[0] == "bearish")
        
        keywords = [item[1] for item in sent_details.get("keyword_matches", []) if isinstance(item, (list, tuple)) and len(item) > 1]
        
        upcoming_events_count = int(evt_details.get("upcoming", 0))
        high_impact_events_count = int(evt_details.get("high_impact", 0))
        avoid_trading_triggered = bool(evt_details.get("should_avoid", False)) or bool(data.get("filtered", False))
        
        next_event_name = None
        next_event_time = None
        next_event = evt_details.get("next_event")
        if next_event:
            next_event_name = next_event.get("name")
            next_event_time = next_event.get("time")
            
        cur.execute(
            """
            INSERT INTO agent_sentiment_logs (
                timestamp, symbol, sentiment_score, sentiment_label, sentiment_strength,
                bullish_news_count, bearish_news_count, triggered_keywords,
                upcoming_events_count, high_impact_events_count, avoid_trading_triggered,
                next_event_name, next_event_time
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            """,
            (
                timestamp,
                symbol,
                sentiment_score,
                sentiment_label,
                sentiment_strength,
                bullish_news_count,
                bearish_news_count,
                keywords,
                upcoming_events_count,
                high_impact_events_count,
                avoid_trading_triggered,
                next_event_name,
                next_event_time
            )
        )
    except Exception as exc:
        logger.warning(f"[Track1] Failed to insert sentiment log: {exc}", exc_info=True)



# ─── Main pipeline class ──────────────────────────────────────────────────────

class Track1Pipeline:
    """
    Asyncio background pipeline for Track 1 real-time data persistence.

    Start with `await pipeline.start()`.
    Stop with `await pipeline.stop()`.
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._swing_detector = _SwingDetector()
        self._cycle = 0
        # Simpan candle terakhir per timeframe agar _record_agent_decision bisa pakai
        self._last_candles: Dict[str, List[Dict]] = {}
        # Simpan timestamp terakhir dari event CSV yang berhasil di-insert
        self._last_csv_timestamp: Optional[datetime] = None

    # ── Public API ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background loop."""
        if self._running:
            logger.warning("[Track1] Pipeline already running.")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop(), name="track1_pipeline")
        logger.info(f"[Track1] [OK] Pipeline started (interval={self.interval}s)")

    async def stop(self) -> None:
        """Gracefully stop the background loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[Track1] Pipeline stopped.")

    # ── Internal loop ─────────────────────────────────────────────────────

    async def _loop(self) -> None:
        """Main background loop — runs until cancelled."""
        # Brief startup delay so FastAPI finishes starting up
        await asyncio.sleep(5)

        while self._running:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._run_cycle)
            except Exception as exc:
                logger.error(f"[Track1] Unhandled cycle error: {exc}", exc_info=True)

            await asyncio.sleep(self.interval)

    def _run_cycle(self) -> None:
        """Synchronous cycle executed in a thread pool executor."""
        self._cycle += 1
        cycle_start = datetime.utcnow()
        # logger.info(f"[Track1] Cycle {self._cycle} start at {cycle_start.isoformat()}")

        try:
            # Scheduled orchestrator run disabled to reduce logs; triggered on-demand via CSV Watcher structure events
            # from app.services.orchestrator_service import run_orchestrator_from_db
            # run_orchestrator_from_db("XAUUSD")
            
            elapsed = (datetime.utcnow() - cycle_start).total_seconds()
            # logger.info(f"[Track1] Cycle {self._cycle} completed in {elapsed:.1f}s")
            pass
        except Exception as exc:
            logger.error(f"[Track1] DB cycle error: {exc}", exc_info=True)
