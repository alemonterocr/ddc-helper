---
name: http-adapter
type: adapter
status: planned
layer: adapter
---

## Purpose
FastAPI router that exposes the migration pipeline over HTTP. Translates HTTP
requests into domain calls and domain results into HTTP responses.

## Inputs
n/a (defines endpoints)

## Outputs
Endpoints:
- `POST /analyze` — body: `{ dom_skeleton, dealer_id, provider }` → returns `{ section_plan, warnings, page_alias, page_title }`
- `POST /analyze-deterministic` — body: `{ dom_skeleton }` → returns `{ plan }` (deterministic only, no LLM)
- `POST /execute` — body: `{ dealer_id, page_alias, page_title, section_plan }` → runs section injection via WS bridge
- `GET /health` — returns `{ status: "ok" }`

## `/analyze` pipeline (active flow)

The router is a thin caller: derive page metadata, build initial
`MigrationState`, invoke `build_migration_graph(...).ainvoke(state)`,
return the response.

All pipeline logic lives in the graph nodes; see
`application/migration/spec.md` for the full
`prune → chrome_review → build → image_split → convert → enrich` flow.

## Contracts
- Returns 422 on invalid input (Pydantic handles this automatically)
- Returns 500 with a structured error body on pipeline failure
- `_chrome_candidate` and `_slot_nodes` are internal fields — stripped before serialization
- LLM may be `None` (no provider configured); the graph no-ops LLM steps gracefully in that case

## Dependencies
- `application.migration.migration_graph`
- `domain.catalog`
- `ports.outbound.LLMPort`
- `adapters.outbound.browser_bridge`
