"""Activity logs API endpoints."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_mt5_manager
from app.core.mt5_manager import MT5Manager
from app.models.activity_log import ActivityLogResponse
from app.services.activity_log_service import ActivityLogService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instance (singleton)
_activity_log_service: Optional[ActivityLogService] = None


def get_activity_log_service(
    mt5: MT5Manager = Depends(get_mt5_manager)
) -> ActivityLogService:
    """
    Get or create ActivityLogService instance (dependency injection).
    
    Args:
        mt5: MT5Manager instance
        
    Returns:
        ActivityLogService singleton instance
    """
    global _activity_log_service
    
    if _activity_log_service is None:
        _activity_log_service = ActivityLogService(mt5_manager=mt5, cache_size=200)
        logger.debug("[ActivityLogsAPI] ActivityLogService initialized")
    
    return _activity_log_service


@router.get("", response_model=ActivityLogResponse)
@router.get("/", response_model=ActivityLogResponse)
async def get_activity_logs(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of logs to return"),
    since: Optional[str] = Query(None, description="ISO timestamp - only return logs after this time"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO, SUCCESS, WARNING, ERROR)"),
    refresh: bool = Query(False, description="Force refresh from all collectors"),
    service: ActivityLogService = Depends(get_activity_log_service),
):
    """
    Get recent activity logs from all sources.
    
    This endpoint aggregates logs from:
    - Trading signals (live_signals_log.csv)
    - Market structure events (LLHHBOSData_*.csv)
    - MT5 positions and trades
    - System events
    
    Args:
        limit: Maximum number of logs (1-200)
        since: ISO timestamp to filter logs after this time
        event_type: Filter by specific event type
        severity: Filter by severity level
        refresh: Force refresh cache
        
    Returns:
        ActivityLogResponse with logs sorted by timestamp (newest first)
    """
    try:
        # Parse since timestamp if provided
        since_dt: Optional[datetime] = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid timestamp format: {since}. Use ISO format (e.g., 2024-05-05T13:15:00Z)",
                )
        
        # Get logs based on filters
        if event_type:
            logs = service.get_logs_by_type(
                event_type=event_type,
                limit=limit,
                since=since_dt
            )
        elif severity:
            logs = service.get_logs_by_severity(
                severity=severity.upper(),
                limit=limit,
                since=since_dt
            )
        else:
            logs = service.get_recent_logs(
                limit=limit,
                since=since_dt,
                refresh_cache=refresh
            )
        
        # Check if more logs are available
        # (if we got exactly the limit, assume there might be more)
        has_more = len(logs) == limit
        
        return ActivityLogResponse(
            success=True,
            total=len(logs),
            logs=logs,
            has_more=has_more
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ActivityLogsAPI] Error fetching activity logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch activity logs: {str(e)}",
        )


@router.get("/stats")
async def get_activity_log_stats(
    service: ActivityLogService = Depends(get_activity_log_service),
):
    """
    Get activity log service statistics.
    
    Returns:
        Cache statistics and service status
    """
    try:
        stats = service.get_cache_stats()
        
        return {
            "success": True,
            "stats": stats,
        }
    
    except Exception as e:
        logger.error(f"[ActivityLogsAPI] Error fetching stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}",
        )


@router.post("/clear-cache")
async def clear_activity_log_cache(
    service: ActivityLogService = Depends(get_activity_log_service),
):
    """
    Clear the activity log cache.
    
    Returns:
        Success response
    """
    try:
        service.clear_cache()
        
        return {
            "success": True,
            "message": "Activity log cache cleared successfully",
        }
    
    except Exception as e:
        logger.error(f"[ActivityLogsAPI] Error clearing cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )


@router.get("/event-types")
async def get_event_types():
    """
    Get list of available event types.
    
    Returns:
        List of event type values
    """
    from app.models.activity_log import EventType
    
    return {
        "success": True,
        "event_types": [event.value for event in EventType],
    }


@router.get("/severity-levels")
async def get_severity_levels():
    """
    Get list of available severity levels.
    
    Returns:
        List of severity level values
    """
    from app.models.activity_log import SeverityLevel
    
    return {
        "success": True,
        "severity_levels": [level.value for level in SeverityLevel],
    }
