"""Activity log data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """Activity log severity levels."""

    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EventType(str, Enum):
    """Activity log event types."""

    # Signal events
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    SIGNAL_EXECUTED = "SIGNAL_EXECUTED"
    SIGNAL_CLOSED = "SIGNAL_CLOSED"
    
    # Structure events
    STRUCTURE_CHOCH = "STRUCTURE_CHOCH"
    STRUCTURE_BOS = "STRUCTURE_BOS"
    STRUCTURE_LL = "STRUCTURE_LL"
    STRUCTURE_HH = "STRUCTURE_HH"
    
    # Position events
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    POSITION_MODIFIED = "POSITION_MODIFIED"
    
    # System events
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SYSTEM_WARNING = "SYSTEM_WARNING"
    SYSTEM_INFO = "SYSTEM_INFO"
    
    # Trade events
    TRADE_WIN = "TRADE_WIN"
    TRADE_LOSS = "TRADE_LOSS"
    TRADE_BREAKEVEN = "TRADE_BREAKEVEN"


class ActivityLog(BaseModel):
    """Activity log entry."""

    id: str = Field(..., description="Unique identifier")
    timestamp: datetime = Field(..., description="Event timestamp in UTC")
    event_id: str = Field(..., description="Related event/signal/trade ID")
    event_type: EventType = Field(..., description="Type of event")
    severity: SeverityLevel = Field(..., description="Severity level")
    icon: str = Field(..., description="Icon identifier for UI")
    title: str = Field(..., description="Short title/summary")
    message: str = Field(..., description="Detailed message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")

    class Config:
        """Pydantic config."""
        
        json_schema_extra = {
            "example": {
                "id": "LOG_20260505_131500_001",
                "timestamp": "2026-05-05T13:15:00Z",
                "event_id": "SMC_20260505_131500_SELL",
                "event_type": "SIGNAL_GENERATED",
                "severity": "INFO",
                "icon": "TrendingDown",
                "title": "SELL Signal Generated",
                "message": "New SELL signal for XAUUSD at 4553.16 with 75.58% confidence",
                "metadata": {
                    "symbol": "XAUUSD",
                    "direction": "SELL",
                    "entry_price": 4553.16,
                    "confidence": 75.58,
                    "tier": "GOOD"
                }
            }
        }


class ActivityLogResponse(BaseModel):
    """Activity logs API response."""

    success: bool = True
    total: int = Field(..., description="Total number of logs returned")
    logs: list[ActivityLog] = Field(..., description="Activity log entries")
    has_more: bool = Field(..., description="Whether more logs are available")
    
    class Config:
        """Pydantic config."""
        
        json_schema_extra = {
            "example": {
                "success": True,
                "total": 50,
                "logs": [],
                "has_more": True
            }
        }
