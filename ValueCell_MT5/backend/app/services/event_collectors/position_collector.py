"""Position event collector."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.core.mt5_manager import MT5Manager
from app.models.activity_log import ActivityLog, EventType, SeverityLevel

logger = logging.getLogger(__name__)


class PositionCollector:
    """Collects position/trade events from MT5."""

    def __init__(self, mt5_manager: Optional[MT5Manager] = None):
        """
        Initialize position collector.
        
        Args:
            mt5_manager: MT5Manager instance (optional, will create new if None)
        """
        self.mt5_manager = mt5_manager
        
        # Track processed deals to avoid duplicates
        self._processed_tickets: set[int] = set()
        self._last_check: Optional[datetime] = None
    
    def _get_mt5_manager(self) -> Optional[MT5Manager]:
        """Get or create MT5Manager instance."""
        if self.mt5_manager is None:
            try:
                self.mt5_manager = MT5Manager()
                if not self.mt5_manager.connect():
                    logger.warning("[PositionCollector] MT5 connection failed")
                    return None
            except Exception as e:
                logger.error(f"[PositionCollector] Error creating MT5Manager: {e}")
                return None
        
        return self.mt5_manager
    
    def collect(self, limit: int = 50, since: Optional[datetime] = None) -> List[ActivityLog]:
        """
        Collect position/trade events from MT5.
        
        Args:
            limit: Maximum number of events to return
            since: Only return events after this timestamp
            
        Returns:
            List of ActivityLog entries
        """
        logs: List[ActivityLog] = []
        
        try:
            mt5 = self._get_mt5_manager()
            if mt5 is None:
                logger.warning("[PositionCollector] MT5 not available")
                return logs
            
            # Get recent history deals (last 7 days)
            deals = mt5.get_history_deals(days=7)
            
            if not deals:
                logger.debug("[PositionCollector] No deals found")
                return logs
            
            # Process deals in reverse (newest first)
            for deal in reversed(deals):
                try:
                    ticket = deal.get("ticket", 0)
                    
                    # Skip if already processed
                    if ticket in self._processed_tickets:
                        continue
                    
                    # Parse timestamp
                    time_value = deal.get("time")
                    if isinstance(time_value, str):
                        timestamp = datetime.fromisoformat(time_value.replace("Z", "+00:00"))
                    elif isinstance(time_value, datetime):
                        timestamp = time_value
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                    else:
                        # Skip invalid timestamp
                        continue
                    
                    # Ensure UTC
                    timestamp = timestamp.astimezone(timezone.utc)
                    
                    # Filter by since parameter
                    if since and timestamp <= since:
                        continue
                    
                    # Extract deal data
                    symbol = deal.get("symbol", "XAUUSD")
                    deal_type = deal.get("type", 0)
                    entry = deal.get("entry", 0)
                    volume = float(deal.get("volume", 0))
                    price = float(deal.get("price", 0))
                    profit = float(deal.get("profit", 0))
                    comment = deal.get("comment", "")
                    
                    # Determine event type
                    if entry == 0:  # Entry deal (position opened)
                        event_type = EventType.POSITION_OPENED
                        severity = SeverityLevel.INFO
                        icon = "Play"
                        direction = "BUY" if deal_type == 0 else "SELL"
                        title = f"{direction} Position Opened"
                        message = f"Opened {direction} position on {symbol} at {price:.2f} (Volume: {volume:.2f})"
                    elif entry == 1:  # Exit deal (position closed)
                        event_type = EventType.POSITION_CLOSED
                        direction = "BUY" if deal_type == 0 else "SELL"
                        
                        if profit > 0:
                            severity = SeverityLevel.SUCCESS
                            icon = "CheckCircle"
                            title = f"{direction} Position Closed - Profit"
                            message = f"Closed {direction} position on {symbol} at {price:.2f} with profit: ${profit:.2f}"
                        elif profit < 0:
                            severity = SeverityLevel.ERROR
                            icon = "XCircle"
                            title = f"{direction} Position Closed - Loss"
                            message = f"Closed {direction} position on {symbol} at {price:.2f} with loss: ${profit:.2f}"
                        else:
                            severity = SeverityLevel.INFO
                            icon = "Minus"
                            title = f"{direction} Position Closed - Breakeven"
                            message = f"Closed {direction} position on {symbol} at {price:.2f} at breakeven"
                    else:
                        # Other deal types (balance operations, etc.)
                        continue
                    
                    # Create activity log
                    log = ActivityLog(
                        id=f"POSITION_{ticket}_{timestamp.strftime('%Y%m%d%H%M%S')}",
                        timestamp=timestamp,
                        event_id=f"TICKET_{ticket}",
                        event_type=event_type,
                        severity=severity,
                        icon=icon,
                        title=title,
                        message=message,
                        metadata={
                            "ticket": ticket,
                            "symbol": symbol,
                            "type": "BUY" if deal_type == 0 else "SELL",
                            "volume": volume,
                            "price": price,
                            "profit": profit,
                            "comment": comment,
                        }
                    )
                    
                    logs.append(log)
                    self._processed_tickets.add(ticket)
                    
                    # Stop if we have enough
                    if len(logs) >= limit:
                        break
                
                except Exception as e:
                    logger.warning(f"[PositionCollector] Error parsing deal: {e}")
                    continue
            
            logger.info(f"[PositionCollector] Collected {len(logs)} position events")
            return logs
        
        except Exception as e:
            logger.error(f"[PositionCollector] Error collecting positions: {e}", exc_info=True)
            return logs
