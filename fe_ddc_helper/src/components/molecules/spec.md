---
name: molecules
type: molecule
status: built
atomic-layer: molecule
---

## Purpose
Composed atoms that handle a single focused UI responsibility. May hold
local UI state (controlled inputs, error states) but no async service calls
and no service-port references.

## Contracts
- No `chrome.*` API calls
- No service-port references (those live at the organism layer)
- May emit callbacks upward (`onSubmit`, `onChange`, `onSave`)
- One component per folder, folder name matches the component name

## Dependencies
- atoms

## Components

| Component | What it does |
|---|---|
| `ApiKeySetup` | Provider dropdown + API key input + validate button. Emits `(provider, apiKey)` on save. |
| `CredentialChecker` | Renders credential status (CC-IDT, LLM key, Media Library tab) with per-row refresh buttons. Pure display — refresh callbacks emit upward. |
| `PageListItem` | One row in the page list — page title/URL, status badge, click handler, delete handler. |
| `ProjectCard` | One dealer project card — dealer ID, page count, last-activity timestamp, open + delete actions. |
| `SectionPlanCard` | One section of the migration plan — section type, slot column chips with widget previews. Used inside the StructurePlanPreview organism. |
| `UrlInputCard` | URL text input + submit button with client-side http(s) validation. |
