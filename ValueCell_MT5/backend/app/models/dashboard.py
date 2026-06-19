"""Dashboard data models."""

from typing import Optional
from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    """Dashboard statistics."""

    balance: float = Field(..., description="Account balance")
    equity: float = Field(..., description="Account equity")
    margin: float = Field(..., description="Used margin")
    free_margin: float = Field(..., description="Free margin")
    margin_level: float = Field(..., description="Margin level percentage")
    profit: float = Field(..., description="Current profit/loss")
    open_positions: int = Field(..., description="Number of open positions")


class AccountInfo(BaseModel):
    """MT5 account information."""

    login: int
    server: str
    name: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    currency: str


class SystemResources(BaseModel):
    """System resource usage."""

    cpu_usage_percent: float = Field(..., description="CPU usage percentage")
    memory_usage_mb: float = Field(..., description="Memory usage in MB")
    memory_usage_percent: float = Field(..., description="Memory usage percentage")


class SystemStatus(BaseModel):
    """System health status."""

    mt5_connected: bool
    api_version: str
    trading_mode: str
    uptime_seconds: int
    last_update: str
    account_number: Optional[int] = None
    server_name: Optional[str] = None
    system_health_percent: float = 100.0
    resources: Optional[SystemResources] = None
