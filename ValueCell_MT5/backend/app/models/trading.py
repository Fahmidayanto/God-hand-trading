"""Trading data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketSignal(BaseModel):
    """Trading signal."""

    symbol: str
    timeframe: str
    signal_type: str = Field(..., description="CHoCH, BoS, AI_SIGNAL, HOLD")
    direction: str = Field(..., description="BUY, SELL, HOLD")
    price: float
    confidence: float = Field(..., ge=0, le=100)
    stop_loss: float = Field(default=0.0, description="Stop loss price")
    take_profit: float = Field(default=0.0, description="Take profit price")
    timestamp: datetime


class CandleData(BaseModel):
    """OHLC candlestick data."""

    time: int = Field(..., description="Unix timestamp")
    open: float
    high: float
    low: float
    close: float
    volume: int


class Trade(BaseModel):
    """Trade information."""

    trade_id: str
    ticket: int
    symbol: str
    type: str = Field(..., description="BUY or SELL")
    volume: float
    entry_price: float
    current_price: Optional[float] = None
    exit_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    profit: float
    status: str = Field(..., description="OPEN or CLOSED")
    open_time: datetime
    close_time: Optional[datetime] = None
    comment: Optional[str] = None


class Position(BaseModel):
    """Open position."""

    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    swap: float
    time: datetime


class OrderRequest(BaseModel):
    """Order placement request."""

    symbol: str
    type: str = Field(..., description="BUY or SELL")
    volume: float = Field(..., gt=0, le=10.0)
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: Optional[str] = None


class OrderResponse(BaseModel):
    """Order placement response."""

    success: bool
    order_id: Optional[int] = None
    message: str
    ticket: Optional[int] = None
