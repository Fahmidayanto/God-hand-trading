"""
BoS Event Listener - Instant Trigger for Structure Events

This module implements a real-time listener that detects new Break of Structure (BoS)
and Change of Character (CHoCH) events in the realtime_structures table and triggers
an immediate decision cycle instead of waiting for the next 60-second interval.

Benefits:
- Reduces latency from up to 60 seconds to milliseconds
- Prevents missed opportunities when BoS is detected late in cycle
- Deduplication ensures same BoS isn't processed twice

Architecture:
- Runs as background task alongside main 60-second loop
- Polls realtime_structures for unprocessed events every N seconds (configurable)
- Marks events as processed to prevent re-processing
- Signals main orchestrator to trigger instant cycle
"""

from __future__ import annotations

import asyncio
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass


@dataclass
class BoSEvent:
    """Represents a detected BoS or CHoCH event"""
    id: int
    timestamp: datetime
    symbol: str
    timeframe: str
    event_type: str  # 'BoS', 'CHoCH', 'HH', 'LL'
    direction: str  # 'Bullish', 'Bearish'
    price: float
    created_at: datetime


class BoSEventListener:
    """
    Listens for new BoS/CHoCH events in realtime_structures table
    and triggers immediate decision cycle.
    """

    def __init__(
        self,
        db_client: Any,  # Database client (psycopg2 or async driver)
        poll_interval: int = 5,  # Check for new events every N seconds
        event_age_threshold: int = 120,  # Only trigger for events < 120 seconds old
    ):
        """
        Args:
            db_client: Database connection (async preferred)
            poll_interval: How often to check for new events (seconds)
            event_age_threshold: Max age of event to trigger instant cycle (seconds)
        """
        self.db_client = db_client
        self.poll_interval = poll_interval
        self.event_age_threshold = event_age_threshold
        self.last_checked_id = 0
        self.on_event_callback: Optional[Callable] = None
        self._running = False

    def set_event_callback(self, callback: Callable[[BoSEvent], Any]) -> None:
        """Register callback to trigger instant cycle when BoS detected"""
        self.on_event_callback = callback

    async def start(self) -> None:
        """Start listening for new BoS events"""
        self._running = True
        logger.info("🎧 BoS Event Listener started (poll_interval={}s)", self.poll_interval)

        try:
            while self._running:
                try:
                    new_events = await self._fetch_unprocessed_events()

                    for event in new_events:
                        # Check if event is recent enough to trigger instant cycle
                        event_age = (datetime.utcnow() - event.created_at).total_seconds()

                        if event_age < self.event_age_threshold:
                            logger.info(
                                "⚡ INSTANT TRIGGER: New {} {} detected at {} (age={}s)",
                                event.event_type,
                                event.direction,
                                event.price,
                                int(event_age),
                            )

                            # Mark as processed BEFORE callback to avoid race condition
                            await self._mark_as_processed(event.id)

                            # Trigger callback if registered
                            if self.on_event_callback:
                                try:
                                    await self.on_event_callback(event)
                                except Exception as e:
                                    logger.exception(
                                        "Error in BoS event callback: {}", e
                                    )
                        else:
                            logger.debug(
                                "BoS event too old (age={}s > threshold={}s), skipping",
                                int(event_age),
                                self.event_age_threshold,
                            )

                    # Update last checked ID
                    if new_events:
                        self.last_checked_id = max(e.id for e in new_events)

                except Exception as e:
                    logger.exception("Error in BoS event listener loop: {}", e)
                    # Continue polling even on error
                    await asyncio.sleep(1)

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            logger.info("🎧 BoS Event Listener stopped")
            self._running = False

    async def stop(self) -> None:
        """Stop listening for events"""
        self._running = False
        logger.info("🎧 BoS Event Listener stopping...")

    async def _fetch_unprocessed_events(self) -> list[BoSEvent]:
        """
        Fetch unprocessed BoS/CHoCH events from realtime_structures table.

        Query:
            SELECT * FROM realtime_structures
            WHERE processed = FALSE
            AND event_type IN ('BoS', 'CHoCH')
            AND id > last_checked_id
            ORDER BY id ASC
            LIMIT 100

        Returns:
            List of unprocessed BoS events
        """
        try:
            # Execute query
            query = """
                SELECT 
                    id, timestamp, symbol, timeframe, 
                    event_type, direction, price, created_at
                FROM realtime_structures
                WHERE processed = FALSE
                AND event_type IN ('BoS', 'CHoCH')
                AND id > %s
                ORDER BY id ASC
                LIMIT 100
            """

            # This assumes async database client (e.g., asyncpg)
            # If using sync psycopg2, wrap in executor
            cursor = await self.db_client.cursor()
            await cursor.execute(query, (self.last_checked_id,))
            rows = await cursor.fetchall()

            events = [
                BoSEvent(
                    id=row[0],
                    timestamp=row[1],
                    symbol=row[2],
                    timeframe=row[3],
                    event_type=row[4],
                    direction=row[5],
                    price=row[6],
                    created_at=row[7],
                )
                for row in rows
            ]

            if events:
                logger.debug(
                    "Found {} unprocessed BoS events", len(events)
                )

            return events

        except Exception as e:
            logger.exception("Error fetching unprocessed events: {}", e)
            return []

    async def _mark_as_processed(self, event_id: int) -> None:
        """
        Mark event as processed in database.

        Query:
            UPDATE realtime_structures
            SET processed = TRUE, processed_at = NOW()
            WHERE id = %s
        """
        try:
            query = """
                UPDATE realtime_structures
                SET processed = TRUE, processed_at = NOW()
                WHERE id = %s
            """

            cursor = await self.db_client.cursor()
            await cursor.execute(query, (event_id,))
            await self.db_client.commit()

            logger.debug("Marked event {} as processed", event_id)

        except Exception as e:
            logger.exception("Error marking event {} as processed: {}", event_id, e)


class InstantCycleTrigger:
    """
    Manages instant cycle triggering when BoS events detected.
    Prevents duplicate cycles and manages cycle queue.
    """

    def __init__(self, max_pending_cycles: int = 5):
        """
        Args:
            max_pending_cycles: Max instant cycles to queue up
        """
        self.max_pending_cycles = max_pending_cycles
        self.pending_events: asyncio.Queue = asyncio.Queue(maxsize=max_pending_cycles)
        self.on_instant_cycle: Optional[Callable] = None

    def set_cycle_callback(self, callback: Callable[[BoSEvent], Any]) -> None:
        """Register callback for instant cycle trigger"""
        self.on_instant_cycle = callback

    async def queue_event(self, event: BoSEvent) -> bool:
        """
        Queue event for instant cycle processing.

        Returns:
            True if queued, False if queue full
        """
        try:
            self.pending_events.put_nowait(event)
            logger.info(
                "📌 Queued {} {} event (queue size: {})",
                event.event_type,
                event.direction,
                self.pending_events.qsize(),
            )
            return True
        except asyncio.QueueFull:
            logger.warning(
                "⚠️  Instant cycle queue full ({}), dropping event",
                self.max_pending_cycles,
            )
            return False

    async def process_pending_events(self) -> int:
        """
        Process all pending events and trigger instant cycles.

        Returns:
            Number of cycles triggered
        """
        cycles_triggered = 0

        while not self.pending_events.empty():
            try:
                event = self.pending_events.get_nowait()

                if self.on_instant_cycle:
                    logger.info(
                        "🔥 Triggering instant cycle for {} at {}",
                        event.event_type,
                        event.price,
                    )
                    try:
                        await self.on_instant_cycle(event)
                        cycles_triggered += 1
                    except Exception as e:
                        logger.exception("Error triggering instant cycle: {}", e)

            except asyncio.QueueEmpty:
                break

        return cycles_triggered
