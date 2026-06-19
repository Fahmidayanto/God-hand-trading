"""Performance analytics models."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PerformanceStats(BaseModel):
    """Overall performance statistics."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float = Field(..., ge=0, le=100)
    total_profit: float
    total_loss: float
    net_profit: float
    profit_factor: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration: float = Field(..., description="In minutes")


class MonthlyPerformance(BaseModel):
    """Monthly performance breakdown."""

    month: str
    year: int
    trades: int
    win_rate: float
    profit: float
    return_pct: float
    max_dd: float
    sharpe: Optional[float] = None


class EquityCurve(BaseModel):
    """Equity curve data point."""

    timestamp: int
    balance: float
    equity: float
    profit: float


class TradeStatistics(BaseModel):
    """Trade statistics summary."""

    symbol: str
    total_trades: int
    win_rate: float
    net_profit: float
    avg_profit_per_trade: float
    best_trade: float
    worst_trade: float


class RiskMetrics(BaseModel):
    """Risk management metrics."""

    current_exposure: float = Field(..., description="Percentage of capital at risk")
    max_risk_allowed: float
    open_positions: int
    max_positions_allowed: int
    daily_loss: float
    max_daily_loss_allowed: float
    risk_status: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
