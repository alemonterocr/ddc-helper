---
name: websocket-adapter
type: adapter
status: planned
layer: adapter
---

## Purpose
WebSocket endpoint that maintains a persistent connection with the browser
extension. Receives execution results from the extension and dispatches section
build commands to it (RPC over WebSocket pattern).

## Inputs
- WebSocket messages from extension: `{ type: "result", command_id, payload }`

## Outputs
- WebSocket messages to extension: `{ type: "execute", command_id, command }`

## Contracts
- One connection per `dealer_id` (connection keyed by dealer_id)
- Pending commands tracked as asyncio Futures — resolved when extension responds
- If extension disconnects mid-build, Builder receives a BridgeDisconnectedError

## Dependencies
- `ports.outbound.BrowserBridgePort`
- `domain.models`

## Notes
This adapter IS the `BrowserBridgePort` implementation. The WS connection is the
transport; the port interface hides it from the application layer.
