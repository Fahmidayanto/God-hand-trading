"""AI Agent models."""

from typing import List

from pydantic import BaseModel, Field


class AgentStatus(BaseModel):
    """Individual agent status."""
    
    model_config = {"populate_by_name": True}

    name: str = Field(..., serialization_alias="agent_name")
    type: str = Field(..., description="technical, structure, ml, risk, sentiment")
    status: str = Field(..., description="ACTIVE, INACTIVE, ERROR")
    signal: str = Field(..., description="BUY, SELL, HOLD, PENDING", serialization_alias="prediction")
    confidence: float = Field(..., ge=0, le=100)
    accuracy: float = Field(..., ge=0, le=100, description="Historical accuracy")
    signals_today: int = Field(..., ge=0)
    last_update: str


class AgentConsensus(BaseModel):
    """Agent consensus result."""

    consensus: str = Field(..., description="BUY, SELL, HOLD")
    confidence: float = Field(..., ge=0, le=100)
    threshold: float = Field(..., ge=0, le=100)
    agents: List[AgentStatus]
    total_weight: float
    weighted_score: float


class AgentMetrics(BaseModel):
    """Agent performance metrics."""

    agent_name: str
    total_signals: int
    correct_signals: int
    accuracy: float
    avg_confidence: float
    best_timeframe: str
    win_rate: float
