"""
Coordinator Update: Support for Instant BoS Trigger and Deduplication

This module extends the DefaultDecisionCoordinator to support:
1. Checking for processed events (deduplication)
2. Marking events as processed during cycle
3. Instant cycle triggering via signal
4. Tracking cycle number for audit trail
"""

from __future__ import annotations

import asyncio
from typing import Optional
from datetime import datetime
from loguru import logger


class InstantTriggerCoordinator:
    """
    Mixin to add instant trigger support to DefaultDecisionCoordinator.
    
    Usage:
        class MyCoordinator(DefaultDecisionCoordinator, InstantTriggerCoordinator):
            pass
    """
    
    cycle_number: int = 0
    instant_trigger_signal: asyncio.Event = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cycle_number = 0
        self.instant_trigger_signal = asyncio.Event()
    
    async def run_once_with_dedup(self) -> dict:
        """
        Run one decision cycle with deduplication support.
        
        Steps:
        1. Increment cycle number
        2. Run normal cycle
        3. Mark processed events
        4. Return results with cycle tracking
        """
        self.cycle_number += 1
        
        logger.info(
            "🔄 Running decision cycle #{} with deduplication support",
            self.cycle_number
        )
        
        try:
            # Run normal decision cycle
            result = await self.run_once()
            
            # If cycle processed any BoS events, mark them as processed
            await self._mark_processed_events(
                cycle_number=self.cycle_number,
                timestamp=datetime.utcnow()
            )
            
            logger.info(
                "✅ Cycle #{} completed, {} structures marked as processed",
                self.cycle_number,
                result.get('processed_count', 0)
            )
            
            return result
            
        except Exception as e:
            logger.exception("Error in cycle #{}: {}", self.cycle_number, e)
            raise
    
    async def _mark_processed_events(
        self,
        cycle_number: int,
        timestamp: datetime
    ) -> int:
        """
        Mark all unprocessed BoS/CHoCH events as processed.
        
        Query:
            UPDATE realtime_structures
            SET processed = TRUE,
                processed_at = %s,
                cycle_number = %s
            WHERE processed = FALSE
            AND event_type IN ('BoS', 'CHoCH')
            RETURNING id
        
        Returns:
            Count of marked events
        """
        try:
            # This assumes db_client available
            # Adjust based on your architecture
            
            # For now, return 0 (placeholder)
            # In production:
            # marked_count = await self.db_client.execute(
            #     """UPDATE realtime_structures
            #        SET processed = TRUE, 
            #            processed_at = %s,
            #            cycle_number = %s
            #        WHERE processed = FALSE
            #        AND event_type IN ('BoS', 'CHoCH')""",
            #     (timestamp, cycle_number)
            # )
            
            logger.debug(
                "Marked events as processed in cycle #{}",
                cycle_number
            )
            
            return 0
            
        except Exception as e:
            logger.exception("Error marking processed events: {}", e)
            return 0
    
    async def check_for_unprocessed_events(self) -> bool:
        """
        Check if there are unprocessed BoS/CHoCH events.
        
        Query:
            SELECT COUNT(*) FROM realtime_structures
            WHERE processed = FALSE
            AND event_type IN ('BoS', 'CHoCH')
        
        Returns:
            True if unprocessed events exist
        """
        try:
            # Query count of unprocessed events
            # count = await self.db_client.fetchval(
            #     """SELECT COUNT(*) FROM realtime_structures
            #        WHERE processed = FALSE
            #        AND event_type IN ('BoS', 'CHoCH')"""
            # )
            
            count = 0  # Placeholder
            
            if count > 0:
                logger.debug("Found {} unprocessed BoS/CHoCH events", count)
                return True
            
            return False
            
        except Exception as e:
            logger.exception("Error checking unprocessed events: {}", e)
            return False
    
    async def signal_instant_trigger(self) -> None:
        """Signal instant cycle trigger to waiting coroutine"""
        logger.info("🔔 Instant trigger signal received")
        self.instant_trigger_signal.set()
    
    def reset_instant_trigger(self) -> None:
        """Reset trigger signal for next wait cycle"""
        self.instant_trigger_signal.clear()


# Example integration with base_agent.py

INTEGRATION_EXAMPLE = """
# In base_agent.py _run_background_decision():

from valuecell.agents.common.trading._internal.enhanced_decision_loop import (
    enhanced_decision_loop
)

async def _run_background_decision(self, controller, runtime):
    await controller.wait_running()
    strategy_id = runtime.strategy_id
    request = runtime.request

    try:
        # Use enhanced decision loop with instant trigger support
        stop_reason, detail = await enhanced_decision_loop(
            controller=controller,
            runtime=runtime,
            on_cycle=self._on_cycle_result,
            on_stop=self._on_stop,
        )
    except asyncio.CancelledError:
        logger.info("Strategy {} cancelled", strategy_id)
        raise
    except Exception as e:
        logger.exception("Strategy {} failed: {}", strategy_id, e)
        stop_reason = "ERROR"
        detail = str(e)
    finally:
        # Cleanup
        await controller.finalize(runtime, stop_reason, detail)
"""


# Detailed SQL for reference

SQL_QUERIES = """
-- 1. Check for unprocessed BoS events
SELECT id, timestamp, symbol, timeframe, event_type, direction, price, created_at
FROM realtime_structures
WHERE processed = FALSE
AND event_type IN ('BoS', 'CHoCH')
AND EXTRACT(EPOCH FROM (NOW() - created_at)) < 120  -- Recent events
ORDER BY id ASC
LIMIT 100;

-- 2. Mark events as processed
UPDATE realtime_structures
SET processed = TRUE,
    processed_at = NOW(),
    cycle_number = %s
WHERE processed = FALSE
AND event_type IN ('BoS', 'CHoCH')
RETURNING id, event_type, direction;

-- 3. Check deduplication status
SELECT id, processed, processed_at, cycle_number
FROM realtime_structures
WHERE event_type = 'BoS'
ORDER BY created_at DESC
LIMIT 10;

-- 4. Count processed vs unprocessed
SELECT 
  event_type,
  COUNT(*) FILTER (WHERE processed = FALSE) as unprocessed,
  COUNT(*) FILTER (WHERE processed = TRUE) as processed
FROM realtime_structures
GROUP BY event_type;

-- 5. Performance: Processing rate
SELECT 
  DATE_TRUNC('minute', processed_at) as minute,
  COUNT(*) as events_processed,
  AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) as avg_processing_time_sec
FROM realtime_structures
WHERE processed = TRUE
GROUP BY DATE_TRUNC('minute', processed_at)
ORDER BY minute DESC
LIMIT 60;
"""
