---
name: service-adapters
type: adapter
status: built
---

## Purpose
Concrete implementations of the service ports. Each adapter talks to one
external system: the BE API, the DDC CMS, the browser tab, the Media
Library tab, or Chrome storage.

## Contracts
- Must implement the corresponding port interface exactly
- All `chrome.*` API calls live here (or in `scripts/` for injected functions)
- Imported **only by `App.tsx`** — the single composition root
  (verified by grep: `from '.../services/adapters'` returns no matches
  outside `App.tsx`)
- Re-exported from `index.ts` so the composition root has one import site

## Dependencies
- `services/ports` (implements)
- `scripts/` (CMSInjectionAdapter and DOMExtractorAdapter use injected functions)
- `types/`
- `chrome` types (where needed)

## Adapters

| Adapter | Implements | Talks to | Notes |
|---|---|---|---|
| `BackendHttpAdapter` | `BackendPort` | FastAPI BE at `VITE_BACKEND_URL` | Stateless — calls `POST /analyze`, `/execute`, `/analyze-deterministic`, `/configure-key` |
| `CMSInjectionAdapter` | `CMSPort` | Active DDC CMS tab | Executes scripts via `chrome.scripting.executeScript` using the self-contained functions in `scripts/cmsTools.ts` |
| `ChromeStorageCredentialAdapter` | `CredentialPort` | `chrome.storage.local` | Stateless — reads/writes the stored API key + provider |
| `DOMExtractorAdapter` | `DOMExtractorPort` | Live dealership site tab | Opens a tab, runs `extractSkeleton`, closes the tab |
| `WSClientAdapter` | `WSClientPort` | BE WebSocket at `${VITE_BACKEND_URL.replace(/^http/, 'ws')}/ws/{dealerId}` | Per-operation lifecycle — a fresh instance is created via the `createWSClient` factory for each analyze/execute call |

## Lifecycle

`BackendHttpAdapter`, `CMSInjectionAdapter`, `ChromeStorageCredentialAdapter`,
and `DOMExtractorAdapter` are stateless and constructed once at app
startup. `WSClientAdapter` holds an active WebSocket; a new instance is
constructed per migration run via the `createWSClient` factory exposed in
the services bundle.

See `services/ServicesContext.tsx` for the full bundle shape and `App.tsx`
for the instantiation site.
