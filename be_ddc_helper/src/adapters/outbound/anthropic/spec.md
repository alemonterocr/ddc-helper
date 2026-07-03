---
name: anthropic-adapter
type: adapter
status: planned
layer: adapter
---

## Purpose
Concrete implementation of `LLMPort` using the Anthropic SDK + Claude Sonnet.
Builds the prompt from the catalog and planning rules, calls the API, parses
the structured output into a `SectionPlan`.

## Inputs
- `skeleton: DOMSkeleton`
- `catalog: dict` (from `domain.catalog`)
- `rules: str` (from `domain.rules`)

## Outputs
- `SectionPlan` — list of `SectionPlanItem`

## Contracts
- Must implement `LLMPort` exactly — no extra methods called by application layer
- Model: `claude-sonnet-4-6` (configurable via env var `ANTHROPIC_MODEL`)
- Output must be parsed as structured JSON — use tool_use or json mode, not regex
- If parsing fails, raise `LLMOutputParseError` (not a raw Anthropic exception)

## Dependencies
- `ports.outbound.LLMPort`
- `domain.models`
- `anthropic` SDK
