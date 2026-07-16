"""System event collector."""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Deque, List, Optional

from app.models.activity_log import ActivityLog, EventType, SeverityLevel

logger = logging.getLogger(__name__)


class SystemCollector:
    """Collects system-level events."""

    def __init__(self, max_events: int = 200):
        """
        Initialize system collector.
        
        Args:
            max_events: Maximum number of events to keep in memory
        """
        self._events: Deque[ActivityLog] = deque(maxlen=max_events)
        self._initialized = False
        
        # Log initialization
        self._log_startup()
    
    def _log_startup(self) -> None:
        """Log system startup event."""
        if not self._initialized:
            startup_log = ActivityLog(
                id=f"SYSTEM_STARTUP_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                event_id="SYSTEM_001",
                event_type=EventType.SYSTEM_STARTUP,
                severity=SeverityLevel.SUCCESS,
                icon="Power",
                title="System Started",
                message="God Hand Trading MT5 system initialized successfully",
                metadata={
                    "version": "1.0.0",
                    "component": "activity_log_service"
                }
            )
            self._events.append(startup_log)
            self._initialized = True
            from loguru import logger as loguru_logger
            loguru_logger.info("[SystemCollector] Startup event logged")
    
    def log_event(
        self,
        event_type: EventType,
        severity: SeverityLevel,
        title: str,
        message: str,
        icon: str = "Info",
        metadata: Optional[dict] = None
    ) -> ActivityLog:
        """
        Log a system event.
        
        Args:
            event_type: Type of event
            severity: Severity level
            title: Event title
            message: Event message
            icon: Icon identifier
            metadata: Additional metadata
            
        Returns:
            Created ActivityLog entry
        """
        timestamp = datetime.now(timezone.utc)
        
        log = ActivityLog(
            id=f"SYSTEM_{timestamp.strftime('%Y%m%d%H%M%S%f')}",
            timestamp=timestamp,
            event_id=f"SYS_{timestamp.strftime('%Y%m%d%H%M%S')}",
            event_type=event_type,
            severity=severity,
            icon=icon,
            title=title,
            message=message,
            metadata=metadata or {}
        )
        
        self._events.append(log)
        logger.debug(f"[SystemCollector] Logged event: {title}")
        
        return log
    
    def log_info(self, title: str, message: str, metadata: Optional[dict] = None) -> ActivityLog:
        """Log an info event."""
        return self.log_event(
            event_type=EventType.SYSTEM_INFO,
            severity=SeverityLevel.INFO,
            title=title,
            message=message,
            icon="Info",
            metadata=metadata
        )
    
    def log_warning(self, title: str, message: str, metadata: Optional[dict] = None) -> ActivityLog:
        """Log a warning event."""
        return self.log_event(
            event_type=EventType.SYSTEM_WARNING,
            severity=SeverityLevel.WARNING,
            title=title,
            message=message,
            icon="AlertTriangle",
            metadata=metadata
        )
    
    def log_error(self, title: str, message: str, metadata: Optional[dict] = None) -> ActivityLog:
        """Log an error event."""
        return self.log_event(
            event_type=EventType.SYSTEM_ERROR,
            severity=SeverityLevel.ERROR,
            title=title,
            message=message,
            icon="AlertCircle",
            metadata=metadata
        )
    
    def collect(self, limit: int = 50, since: Optional[datetime] = None) -> List[ActivityLog]:
        """
        Collect system events.
        
        Args:
            limit: Maximum number of events to return
            since: Only return events after this timestamp
            
        Returns:
            List of ActivityLog entries
        """
        logs = list(self._events)
        
        # Filter by since parameter
        if since:
            logs = [log for log in logs if log.timestamp > since]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply limit
        logs = logs[:limit]
        
        logger.debug(f"[SystemCollector] Collected {len(logs)} system events")
        return logs
    
    def clear(self) -> None:
        """Clear all collected events."""
        self._events.clear()
        logger.info("[SystemCollector] Events cleared")
