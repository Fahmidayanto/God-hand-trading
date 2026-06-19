"""WebSocket endpoint for real-time updates."""

import asyncio
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.mt5_manager import MT5Manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.add(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time trading data.
    
    Streams:
    - Account balance updates
    - Position changes
    - New signals
    - Price updates
    
    Usage:
        const ws = new WebSocket('ws://localhost:8000/api/v1/ws/live');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data);
        };
    """
    await manager.connect(websocket)
    
    mt5 = MT5Manager()
    connected = mt5.connect()
    
    if not connected:
        await websocket.send_json({
            "type": "error",
            "message": "MT5 connection failed",
        })
        await websocket.close()
        return

    try:
        # Send initial data
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connection established",
        })

        # Start streaming loop
        while True:
            try:
                # Get current data
                account = mt5.get_account_info()
                positions = mt5.get_positions()

                if account:
                    # Send account update
                    await websocket.send_json({
                        "type": "account_update",
                        "data": {
                            "balance": account["balance"],
                            "equity": account["equity"],
                            "profit": account["profit"],
                            "margin_level": account["margin_level"],
                        },
                    })

                # Send position count
                await websocket.send_json({
                    "type": "positions_update",
                    "data": {
                        "count": len(positions),
                        "positions": positions[:5],  # Send only first 5
                    },
                })

                # Wait before next update
                await asyncio.sleep(2)  # Update every 2 seconds

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket stream error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })
                await asyncio.sleep(5)

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    finally:
        manager.disconnect(websocket)
        mt5.disconnect()


@router.get("/clients")
async def get_connected_clients():
    """Get number of connected WebSocket clients."""
    return {
        "clients": len(manager.active_connections),
        "status": "active",
    }
