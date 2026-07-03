---
name: pages
type: page
status: built
atomic-layer: page
---

## Purpose
Top-level views — one per screen of the extension. Pages compose organisms
and forward service ports down from the composition root.

## Contracts
- Read service ports via `useServices()` from `services/ServicesContext`
- Forward needed ports to organisms as **props** — never let organisms
  reach into context themselves (keeps the dependency graph explicit)
- Each page is its own folder, `PageName/PageName.tsx`
- May read/write the Zustand store directly

## Composition root note

The atomic spec convention has historically said "pages are the composition
root". In this repo the composition root is hoisted up one level to
`App.tsx` — App is a thin router that picks which page to render, and
hosts the single `ServicesProvider` so adapters are constructed exactly
once across all pages. Pages still own the wiring between ports and the
organisms they render.

## Dependencies
- organisms
- `services/ServicesContext` (`useServices`)
- `store/useMigrationStore`

## Pages

| Page | What it does | Ports it forwards |
|---|---|---|
| `ProjectListPage` | Landing screen — list of dealer projects, new-project form, AI provider configuration. | `backendPort`, `credentialPort` |
| `ProjectPage` | Active-project workspace — three columns: left (Settings + page list), center (MigrationFlow), right (LinkReplacements when reviewing). | `backendPort`, `credentialPort`, `extractorPort`, `createWSClient` |

`MigrationPage` previously lived here as the original single-page design;
it was deleted as dead code in the S1.2 taxonomic cleanup. The active
routing is in `App.tsx` and picks between the two pages above based on the
store's `view` field.
