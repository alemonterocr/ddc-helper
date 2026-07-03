---
name: browser-bridge-adapter
type: adapter
status: planned
layer: adapter
---

## Purpose
Concrete implementation of `BrowserBridgePort`. Sends section execution commands
to the browser extension over the active WebSocket connection and awaits the
result using asyncio Futures.

## Inputs
- `cmd: SectionCommand` — the section to create (sectionType, position, dealer_id)

## Outputs
- `SectionResult` — success flag + DDC response payload

## Contracts
- Must implement `BrowserBridgePort` exactly
- Each command gets a unique `command_id` (UUID)
- Timeout: 30 seconds per command before raising `BridgeTimeoutError`
- If no active connection for `dealer_id`, raises `BridgeNotConnectedError`

## Dependencies
- `ports.outbound.BrowserBridgePort`
- `adapters.inbound.websocket` (shares the connection registry)
- `domain.models`
