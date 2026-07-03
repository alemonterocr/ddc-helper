---
name: atoms
type: atom
status: built
atomic-layer: atom
---

## Purpose
Base UI elements with no internal state and no service dependencies.
Styled with Tailwind. Fully reusable across the extension.

## Contracts
- No `chrome.*` API calls
- No service imports
- Props-only, no internal async logic
- Single component per file, file name matches export

## Dependencies
None

## Components

| Component | What it does |
|---|---|
| `Badge` | Small label chip — used for section type tags, widget type indicators |
| `Button` | Primary action button — variants (primary/secondary), sizes, loading state |
| `Input` | Text input with optional label, error state, keyboard handlers |
| `StatusDot` | Coloured indicator dot (green/yellow/red) for credential status display |
