from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    """
    Управляет активными WebSocket-соединениями.
    Группирует подключения по ID проекта (waqf_id).
    """
    def __init__(self):
        # Словарь для хранения подключений: {waqf_id: [WebSocket, ...]}
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, waqf_id: int):
        await websocket.accept()
        if waqf_id not in self.active_connections:
            self.active_connections[waqf_id] = []
        self.active_connections[waqf_id].append(websocket)

    def disconnect(self, websocket: WebSocket, waqf_id: int):
        if waqf_id in self.active_connections:
            self.active_connections[waqf_id].remove(websocket)

    async def broadcast_to_project(self, message: str, waqf_id: int):
        if waqf_id in self.active_connections:
            for connection in self.active_connections[waqf_id]:
                await connection.send_text(message)

# Создаем глобальный экземпляр менеджера
manager = ConnectionManager()