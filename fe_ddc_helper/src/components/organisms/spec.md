---
name: organisms
type: organism
status: built
atomic-layer: organism
---

## Purpose
Composed molecules that own a feature slice. May hold async state and call
service ports. Ports are received as props from the page (composition root)
— organisms never import concrete adapters.

## Contracts
- Service ports injected as **props**, never imported from `services/adapters`
- May call `useMigrationStore` directly for shared state
- Handles loading, error, and success states locally where appropriate
- No direct `chrome.*` calls (delegated to service ports)
- One component per folder, folder name matches the component name

## Dependencies
- molecules
- atoms
- `services/ports` (types only)

## Components

| Component | What it does | Ports it receives |
|---|---|---|
| `LinkReplacementsPanel` | Right-sidebar editor for swapping hrefs in the section plan before execute. Reads/writes `linkReplacements` on the active page. | none — uses store only |
| `MigrationFlowPanel` | Center panel — drives analyze → review → execute for the active page. Renders state-appropriate sub-views (`PendingView`, `ExecutionLog`, `StructurePlanPreview`, success/error). | `backendPort`, `credentialPort`, `extractorPort`, `createWSClient` |
| `MigrationForm` | Standalone migration form (dealer ID + URL + credential check). Used by the deprecated MigrationPage flow; not on the current live path. | (see component) |
| `PageListPanel` | Left-sidebar — project header, page list with `PageListItem`s, inline add-page form. | none — uses store only |
| `SettingsPanel` | Left-sidebar — credential checker + per-row refresh handlers. | `backendPort`, `credentialPort` |
| `StructurePlanPreview` | Renders the full section plan with `SectionPlanCard` rows + execute button. | none — pure display |

## Composition root reminder

The four adapter instances + WS factory are created once in `App.tsx` and
exposed via `services/ServicesContext`. Pages read the bundle via
`useServices()` and forward ports to organisms as props. If an organism
needs a port that isn't in the prop list above, the page that hosts it is
where the wiring change goes — not the organism's import statements.
