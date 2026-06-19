"""Dashboard API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.mt5_manager import MT5Manager
from app.dependencies import get_mt5_manager
from app.models.dashboard import AccountInfo, DashboardStats, SystemStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get dashboard statistics.
    
    Returns account balance, equity, margin, and position count.
    """
    try:
        # Get account info
        account = mt5.get_account_info()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch account data from MT5",
            )

        # Get positions
        positions = mt5.get_positions()

        return DashboardStats(
            balance=account["balance"],
            equity=account["equity"],
            margin=account["margin"],
            free_margin=account["free_margin"],
            margin_level=account["margin_level"],
            profit=account["profit"],
            open_positions=len(positions),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/account", response_model=AccountInfo)
async def get_account_info(
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get MT5 account information.
    
    Returns detailed account data including balance, leverage, etc.
    """
    try:
        account = mt5.get_account_info()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch account data",
            )

        return AccountInfo(**account)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get system health status.
    
    Returns connection status, version, mode, system resources, etc.
    """
    import psutil
    from app.config import get_settings

    settings = get_settings()
    
    # Get system resources
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.Process().memory_info()
    memory_mb = memory.rss / 1024 / 1024
    memory_percent = psutil.virtual_memory().percent
    
    # Get account info if connected
    account_number = None
    server_name = None
    if mt5.is_connected():
        account_info = mt5.get_account_info()
        if account_info:
            account_number = account_info.get("login")
            server_name = account_info.get("server")
    
    # Calculate system health (100% if MT5 connected, 0% if not)
    system_health = 100.0 if mt5.is_connected() else 0.0

    return SystemStatus(
        mt5_connected=mt5.is_connected(),
        api_version=settings.APP_VERSION,
        trading_mode=settings.TRADING_MODE,
        uptime_seconds=0,  # TODO: Calculate actual uptime
        last_update=datetime.now().isoformat(),
        account_number=account_number,
        server_name=server_name,
        system_health_percent=system_health,
        resources={
            "cpu_usage_percent": cpu_percent,
            "memory_usage_mb": memory_mb,
            "memory_usage_percent": memory_percent,
        },
    )
