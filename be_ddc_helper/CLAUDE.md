# CLAUDE.md — be_ddc_helper

Navigation guide for AI agents working in this subproject. Auto-loaded by
Claude Code. Read this before touching any file.

## What this is

FastAPI + LangGraph backend for the DDC Agentic Page Cloner. Analyzes a DOM
skeleton captured by the Chrome extension and produces an ordered DDC section
plan; also orchestrates execution back to the extension over WebSocket RPC.

## Architecture: hexagonal

```
src/domain/       — pure business logic, zero framework imports
src/ports/        — abstract interfaces (Python ABCs), no implementations
src/application/  — use cases, LangGraph graph wiring, execute orchestrator
src/adapters/     — concrete implementations (FastAPI, Anthropic/Gemini/DeepSeek, WS bridge, SQLite)
src/main.py       — the only place the dependency graph is assembled
tests/            — mirrors src/ structure
```

Full clean-code and layer rules live in `.specify/memory/constitution.md`.
Do not violate them.

## Before writing code in any module

1. Read the module's `spec.md` (every logic folder has one).
2. Read `src/domain/catalog/ddc_catalog.json` — section names are the source of truth.
3. Read `src/domain/rules/planning_rules.md` — planner constraints.
4. Check the port interface exists before writing an adapter for it.

## Spec file format (module-level `spec.md`)

Every module has a `spec.md` with YAML frontmatter. Schema lives in
`spec-schema.yaml` at the subproject root.

```yaml
---
name: <module-name>
type: use-case | port | adapter | model | domain-rule | graph | config
status: planned | in-progress | built | tested
layer: domain | port | application | adapter | infrastructure
---
```

**Status ladder** (a module's status cannot exceed the status of its dependencies):
- `planned` — spec written, no code yet
- `in-progress` — code partially written, spec may be ahead of implementation
- `built` — code matches spec, no dedicated tests yet
- `tested` — code + tests pass

## When to use which spec format

### Module-level `spec.md` (next to the code it describes)

- For a single module, adapter, domain rule, or application use case
- Describes **current state**: what it does, inputs, outputs, contracts, dependencies
- Must include YAML frontmatter per `spec-schema.yaml`
- Required sections: Purpose, Inputs, Outputs, Contracts, Dependencies

### Feature-level `specs/NNN-feature-name/spec.md` (under `specs/`)

- For **cross-cutting features** spanning multiple modules or both subprojects (BE + FE)
- Freeform narrative format — no YAML frontmatter required
- Numbered sequentially: `001-`, `002-`, …
- Covers architecture, pipeline, data model, design decisions, and a complete file map
- Examples: `specs/001-salesforce-intake/spec.md`, `specs/002-spanish-translation/spec.md`

**Existing feature specs:**

- `specs/001-salesforce-intake/spec.md` — Salesforce intake wizard (4 UI API GETs + parser + LLM classifier)
- `specs/002-spanish-translation/spec.md` — Spanish label translation workflow (glossary, validation, FE components, data model)

## Key contracts (do not violate)

- `sectionType` values in any output must match a `sectionName` in `ddc_catalog.json`.
- The LLM port interface (`src/ports/outbound/llm_port.py`) must not import Anthropic.
- The application layer (`src/application/`) must not import FastAPI or Anthropic directly.
- All DDC-bound operations must go through `BrowserBridgePort` — the browser holds session cookies; backend never calls DDC directly.

## Entry point

`src/main.py` — starts FastAPI with uvicorn. See `src/adapters/inbound/http/spec.md`
for the current API surface.
