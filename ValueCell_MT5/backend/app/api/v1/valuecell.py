"""
ValueCell compatibility endpoints
Provides dummy endpoints for ValueCell frontend components that are not used in MT5 dashboard
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["valuecell"])


@router.get("/agents/")
async def get_agents(enabled_only: bool = False, language: str = "en"):
    """
    Returns empty agent list for legacy sidebar compatibility
    MT5 dashboard uses different agent endpoints (/api/v1/mt5/agents/)
    """
    return {
        "success": True,
        "message": "No legacy agents configured",
        "data": {"agents": []}
    }


@router.get("/conversations/")
async def get_conversations():
    """
    Returns empty conversation list for legacy sidebar compatibility
    MT5 dashboard doesn't use conversations feature
    """
    return {
        "success": True,
        "message": "No conversations",
        "data": {"conversations": []}
    }
