import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for pipeline status streaming."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, pipeline_id: str) -> None:
        await websocket.accept()
        if pipeline_id not in self._connections:
            self._connections[pipeline_id] = []
        self._connections[pipeline_id].append(websocket)
        logger.info("WebSocket connected for pipeline %s", pipeline_id)

    def disconnect(self, websocket: WebSocket, pipeline_id: str) -> None:
        if pipeline_id in self._connections:
            self._connections[pipeline_id] = [
                ws for ws in self._connections[pipeline_id] if ws != websocket
            ]
            if not self._connections[pipeline_id]:
                del self._connections[pipeline_id]
        logger.info("WebSocket disconnected for pipeline %s", pipeline_id)

    async def broadcast(self, pipeline_id: str, data: dict[str, Any]) -> None:
        """Send a message to all connected clients for a pipeline."""
        if pipeline_id not in self._connections:
            return
        message = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in self._connections[pipeline_id]:
            try:
                await ws.send_text(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, pipeline_id)


manager = ConnectionManager()
