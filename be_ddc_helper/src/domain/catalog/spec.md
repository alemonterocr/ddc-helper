---
name: ddc-catalog
type: domain-rule
status: planned
layer: domain
---

## Purpose
Authoritative registry of DDC sections available for injection. Inlined into
the LLM system prompt — not retrieved via RAG. Full visibility to the Planner
is non-negotiable (missing a widget = wrong plan).

## Inputs
n/a (static JSON asset)

## Outputs
- `ddc_catalog.json` — machine-readable catalog consumed by the Planner prompt
- `load_catalog() -> dict` — helper that reads and returns the catalog

## Contracts
- Every entry must have: `sectionName`, `description`, `use_when`, `columns`, `category`
- `sectionName` values are the source of truth — all `sectionType` fields in the
  pipeline must match exactly
- `map-hours` must be flagged as `pre_wired: true` (no widget injection needed)

## Dependencies
None

## Notes
POC catalog covers: empty-one, empty-fifty-fifty, empty-66-33, empty-33-66,
empty-fifths, map-hours. Expand per page type milestone.
