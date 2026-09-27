"""
Real-Time WebSocket Connection and Event Broadcasting Service
"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from app.core.constants import EventType
from app.core.logging import logger


class WebSocketManager:
    """Manages real-time WebSocket client connections and event dispatch."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any], session_id: Optional[str] = None):
        """Broadcast an event payload to all active WebSocket clients."""
        payload = {
            "type": event_type,
            "session_id": session_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        json_msg = json.dumps(payload)
        
        async with self._lock:
            disconnected_sockets = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(json_msg)
                except Exception as e:
                    logger.warning(f"Error sending message to websocket: {e}")
                    disconnected_sockets.append(connection)

            for sock in disconnected_sockets:
                if sock in self.active_connections:
                    self.active_connections.remove(sock)

    def broadcast_sync(self, event_type: str, data: Dict[str, Any], session_id: Optional[str] = None):
        """Non-blocking helper to broadcast from synchronous worker threads."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data, session_id), loop)
        except RuntimeError:
            pass


ws_manager = WebSocketManager()
