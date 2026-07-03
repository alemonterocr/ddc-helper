from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{dealer_id}")
async def websocket_endpoint(websocket: WebSocket, dealer_id: str) -> None:
    await websocket.accept()

    # Shared singletons are seeded on app.state by main.lifespan().
    registry = websocket.app.state.registry
    bridge = websocket.app.state.bridge

    registry.register(dealer_id, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            _handle_message(message, bridge)
    except WebSocketDisconnect:
        pass
    finally:
        registry.unregister(dealer_id)


def _handle_message(message: dict, bridge) -> None:
    if message.get("type") == "tool_result":
        request_id = message.get("id")
        if request_id:
            bridge.resolve(request_id, message)
