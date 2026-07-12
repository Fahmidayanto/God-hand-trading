"""Activity log service for aggregating events from multiple sources."""

import logging
from collections import deque
from datetime import datetime
from typing import Deque, List, Optional

from app.core.mt5_manager import MT5Manager
from app.models.activity_log import ActivityLog
from app.services.event_collectors import (
    PositionCollector,
    StructureCollector,
    SystemCollector,
)

logger = logging.getLogger(__name__)


class ActivityLogService:
    """
    Service for managing activity logs from multiple event sources.
    
    Aggregates events from:
    - Signal collector (live_signals_log.csv)
    - Structure collector (LLHHBOSData_*.csv)
    - Position collector (MT5 trades)
    - System collector (system events)
    """

    def __init__(
        self,
        mt5_manager: Optional[MT5Manager] = None,
        cache_size: int = 200
    ):
        """
        Initialize activity log service.
        
        Args:
            mt5_manager: Optional MT5Manager instance for position collector
            cache_size: Maximum number of logs to cache in memory
        """
        self.cache_size = cache_size
        
        # Initialize event collectors
        self.structure_collector = StructureCollector()
        self.position_collector = PositionCollector(mt5_manager)
        self.system_collector = SystemCollector(max_events=cache_size)
        
        # In-memory cache for aggregated logs
        self._cache: Deque[ActivityLog] = deque(maxlen=cache_size)
        self._last_update: Optional[datetime] = None
        
        logger.debug("[ActivityLogService] Initialized with cache size: {cache_size}")
        
        # Log initialization
        self.system_collector.log_info(
            title="Activity Log Service Started",
            message="Activity log aggregation service initialized successfully",
            metadata={"cache_size": cache_size}
        )
    
    def _merge_and_sort_logs(self, *log_lists: List[ActivityLog]) -> List[ActivityLog]:
        """
        Merge multiple log lists and sort by timestamp (newest first).
        
        Args:
            *log_lists: Variable number of log lists to merge
            
        Returns:
            Merged and sorted list of ActivityLog entries
        """
        merged: List[ActivityLog] = []
        
        for log_list in log_lists:
            merged.extend(log_list)
        
        # Sort by timestamp descending (newest first)
        merged.sort(key=lambda x: x.timestamp, reverse=True)
        
        return merged
    
    def _deduplicate_logs(self, logs: List[ActivityLog]) -> List[ActivityLog]:
        """
        Remove duplicate logs based on unique ID.
        
        Args:
            logs: List of ActivityLog entries
            
        Returns:
            Deduplicated list
        """
        seen_ids = set()
        unique_logs = []
        
        for log in logs:
            if log.id not in seen_ids:
                seen_ids.add(log.id)
                unique_logs.append(log)
        
        return unique_logs
    
    def get_recent_logs(
        self,
        limit: int = 50,
        since: Optional[datetime] = None,
        refresh_cache: bool = False
    ) -> List[ActivityLog]:
        """
        Get recent activity logs from all sources.
        
        Args:
            limit: Maximum number of logs to return (default: 50)
            since: Only return logs after this timestamp
            refresh_cache: Force refresh from all collectors
            
        Returns:
            List of ActivityLog entries sorted by timestamp (newest first)
        """
        try:
            logger.debug(f"[ActivityLogService] Fetching logs (limit={limit}, since={since}, refresh={refresh_cache})")
            
            # Collect from all sources
            structure_logs = self.structure_collector.collect(limit=limit // 3, since=since)
            position_logs = self.position_collector.collect(limit=limit // 3, since=since)
            system_logs = self.system_collector.collect(limit=limit // 3, since=since)
            
            # Merge all logs
            all_logs = self._merge_and_sort_logs(
                structure_logs,
                position_logs,
                system_logs
            )
            
            # Deduplicate
            all_logs = self._deduplicate_logs(all_logs)
            
            # Apply limit
            all_logs = all_logs[:limit]
            
            # Update cache
            self._cache.clear()
            self._cache.extend(all_logs)
            self._last_update = datetime.now()
            
            logger.debug(
                f"[ActivityLogService] Returned {len(all_logs)} logs "
                f"(structure={len(structure_logs)}, "
                f"positions={len(position_logs)}, system={len(system_logs)})"
            )
            
            return all_logs
        
        except Exception as e:
            logger.error(f"[ActivityLogService] Error fetching logs: {e}", exc_info=True)
            
            # Log error event
            self.system_collector.log_error(
                title="Activity Log Fetch Error",
                message=f"Failed to fetch activity logs: {str(e)}",
                metadata={"error_type": type(e).__name__}
            )
            
            # Return cached logs as fallback
            return list(self._cache)[:limit]
    
    def get_logs_by_type(
        self,
        event_type: str,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[ActivityLog]:
        """
        Get logs filtered by event type.
        
        Args:
            event_type: Event type to filter by (e.g., "SIGNAL_GENERATED")
            limit: Maximum number of logs to return
            since: Only return logs after this timestamp
            
        Returns:
            Filtered list of ActivityLog entries
        """
        all_logs = self.get_recent_logs(limit=limit * 2, since=since)
        filtered = [log for log in all_logs if log.event_type.value == event_type]
        return filtered[:limit]
    
    def get_logs_by_severity(
        self,
        severity: str,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[ActivityLog]:
        """
        Get logs filtered by severity level.
        
        Args:
            severity: Severity level to filter by (INFO, SUCCESS, WARNING, ERROR)
            limit: Maximum number of logs to return
            since: Only return logs after this timestamp
            
        Returns:
            Filtered list of ActivityLog entries
        """
        all_logs = self.get_recent_logs(limit=limit * 2, since=since)
        filtered = [log for log in all_logs if log.severity.value == severity]
        return filtered[:limit]
    
    def clear_cache(self) -> None:
        """Clear the in-memory log cache."""
        self._cache.clear()
        self._last_update = None
        logger.info("[ActivityLogService] Cache cleared")
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "cache_size": len(self._cache),
            "cache_max_size": self.cache_size,
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }
