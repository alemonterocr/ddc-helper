import asyncio
import uuid

from src.adapters.inbound.websocket.connection_registry import ConnectionRegistry
from src.domain.errors import BridgeNotConnectedError, BridgeTimeoutError

_TOOL_TIMEOUT_SECONDS = 30

# Tools whose operations can take arbitrarily long — media uploads,
# large image encoding, slow S3 polling, etc. These get a generous
# timeout (5 min) instead of the default 30 s.
_LONG_TIMEOUT_SECONDS = 300
_LONG_TIMEOUT_TOOLS: set[str] = {
    "upload_media_image",
}


class WsBridgeAdapter:
    """Sends tool-call requests to the frontend over WebSocket and awaits results."""

    def __init__(self, registry: ConnectionRegistry) -> None:
        self._registry = registry
        self._pending: dict[str, asyncio.Future] = {}

    async def call_tool(
        self, dealer_id: str, tool: str, args: dict, timeout: int | None = None,
    ) -> dict:
        ws = self._registry.get(dealer_id)
        if ws is None:
            raise BridgeNotConnectedError(
                f"No WebSocket connection for dealer '{dealer_id}'. "
                "The frontend must connect before executing."
            )

        if timeout is None:
            timeout = _LONG_TIMEOUT_SECONDS if tool in _LONG_TIMEOUT_TOOLS else _TOOL_TIMEOUT_SECONDS

        request_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future

        await ws.send_json({
            "type": "tool_call",
            "id": request_id,
            "tool": tool,
            "args": args,
        })

        try:
            result: dict = await asyncio.wait_for(
                asyncio.shield(future), timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            raise BridgeTimeoutError(
                f"Tool '{tool}' did not respond within {timeout}s"
            )
        finally:
            self._pending.pop(request_id, None)

    async def send_progress(self, dealer_id: str, message: str) -> None:
        """Push a progress event to the frontend (fire-and-forget, no response expected)."""
        ws = self._registry.get(dealer_id)
        if ws is not None:
            await ws.send_json({"type": "progress", "message": message})

    def resolve(self, request_id: str, payload: dict) -> None:
        """Called by the WS handler when the frontend sends a tool_result message."""
        future = self._pending.get(request_id)
        if future and not future.done():
            future.set_result(payload)
