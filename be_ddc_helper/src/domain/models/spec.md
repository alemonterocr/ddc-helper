---
name: domain-models
type: model
status: planned
layer: domain
---

## Purpose
Pydantic models and TypedDicts that define the data shapes flowing through the
pipeline. No business logic here — pure structure.

## Inputs
n/a (definitions, not transformations)

## Outputs
- `DOMSkeleton` — cleaned HTML tree received from the browser extension
- `SectionPlanItem` — a single DDC section to be created (`sectionType`, `position`, `intent`)
- `MigrationState` — LangGraph state dict carrying all pipeline data between nodes
- `VerifierResult` — score + feedback from the Verifier node

## Contracts
- `SectionPlanItem.sectionType` must be a valid `sectionName` from `ddc_catalog.json`
- `MigrationState.iteration` starts at 0, max 3
- All models use Pydantic v2

## Dependencies
None (domain layer has no dependencies)
