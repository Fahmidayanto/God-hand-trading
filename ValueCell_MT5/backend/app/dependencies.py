"""Dependency injection for FastAPI."""

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings
from app.core.mt5_manager import MT5Manager

settings = get_settings()
security = HTTPBearer()

# Global MT5 manager instance (singleton)
_mt5_manager_instance: MT5Manager | None = None


def get_mt5_manager() -> MT5Manager:
    """Get MT5 manager dependency (singleton)."""
    global _mt5_manager_instance
    
    if _mt5_manager_instance is None:
        _mt5_manager_instance = MT5Manager()
        if not _mt5_manager_instance.connect():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MT5 connection unavailable",
            )
    
    # Check if still connected
    if not _mt5_manager_instance.is_connected():
        # Try to reconnect
        if not _mt5_manager_instance.connect():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MT5 connection lost",
            )
    
    return _mt5_manager_instance


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify JWT token (placeholder for future auth)."""
    # TODO: Implement JWT verification
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return token


# Optional authentication dependency
def get_current_user(token: str = Depends(verify_token)):
    """Get current authenticated user (placeholder)."""
    # TODO: Implement user retrieval from token
    return {"user_id": "demo_user"}
