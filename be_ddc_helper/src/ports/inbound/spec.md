---
name: inbound-ports
type: port
status: planned
layer: port
---

## Purpose
Abstract interfaces for everything that triggers the migration pipeline.
Adapters (FastAPI HTTP, WebSocket) implement these — the application layer
depends only on these abstractions.

## Inputs
n/a (interface definitions)

## Outputs
- `MigrationPort` — defines `analyze(skeleton: DOMSkeleton) -> SectionPlan`

## Contracts
- No framework imports (no FastAPI, no Starlette)
- Defined as Python ABCs or Protocols

## Dependencies
- `domain.models`
