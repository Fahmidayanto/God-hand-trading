"""Base Pydantic models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model."""

    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: str
    message: str
    path: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
