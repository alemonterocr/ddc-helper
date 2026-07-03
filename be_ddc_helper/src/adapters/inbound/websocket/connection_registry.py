from fastapi import WebSocket


class ConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    def register(self, dealer_id: str, websocket: WebSocket) -> None:
        self._connections[dealer_id] = websocket

    def unregister(self, dealer_id: str) -> None:
        self._connections.pop(dealer_id, None)

    def get(self, dealer_id: str) -> WebSocket | None:
        return self._connections.get(dealer_id)

    def is_connected(self, dealer_id: str) -> bool:
        return dealer_id in self._connections
