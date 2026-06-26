from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_alert(self, alert_data: Dict[str, Any]):
        message = json.dumps({
            "type": "alert",
            "data": alert_data
        })
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    async def send_transaction_update(self, tx_data: Dict[str, Any]):
        message = json.dumps({
            "type": "transaction",
            "data": tx_data
        })
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending transaction update: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast(self, message: Dict[str, Any]):
        text = json.dumps(message)
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


ws_manager = WebSocketManager()
