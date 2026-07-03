# fe_ddc_helper

Chrome extension (React + TypeScript + Vite, Manifest v3) for the DDC Agentic
Page Cloner. Captures a DOM skeleton from a live dealer website, hands it to
the backend for analysis, lets the specialist review the plan, then drives
DDC CMS via `chrome.scripting.executeScript` under the specialist's own
session.

Companion backend: [`../be_ddc_helper/`](../be_ddc_helper/).

## User flow

1. Specialist opens the extension and enters a dealer ID → credentials verify.
2. Specialist pastes a live site URL → extension opens the page in a new tab, extracts the DOM skeleton, closes the tab.
3. Extension `POST /analyze` on the backend → receives a `section_plan`.
4. Plan renders in the side panel; specialist reviews and swaps legacy hrefs for DDC URLs in the right sidebar.
5. Specialist clicks **Execute** → extension injects sections and widgets into the active DDC CMS tab.

## Architecture (two orthogonal patterns)

- **UI layer**: Atomic Design — `atoms → molecules → organisms → templates → pages`, plus `ui/` for shadcn primitives.
- **Service layer**: Ports & adapters — `services/ports/` defines interfaces, `services/adapters/` implements them.

Full rules live in [`.specify/memory/constitution.md`](./.specify/memory/constitution.md).

## Run locally

Requires Node 20+ and npm.

```powershell
npm install
npm run build            # produces dist/
```

Load the extension:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** → select the `dist/` folder.

For iteration:

```powershell
npm run test             # vitest, single run
npm run test:watch       # vitest, watch mode
npx tsc --noEmit         # typecheck
```

## Critical constraint on `src/scripts/`

Files in `src/scripts/` are serialized with `.toString()` and injected into
browser tabs. They MUST be fully self-contained — zero imports, zero
closures over module-level variables. Vite minifies module-level names, so
external references break silently in production. Every helper must be a
named function defined **inside** the script function body.

## shadcn/ui first

This project consumes shadcn/ui (`components.json`). Before creating any new
UI primitive, check `src/components/ui/` and add via
`npx shadcn@latest add <component>` if a fit exists. Only fall back to custom
components in `atoms/` when shadcn has no equivalent. See constitution
Principle VI for the full rule.

## How this repo is organized (agent reading order)

1. `CLAUDE.md` — auto-loaded navigation guide.
2. `.specify/memory/constitution.md` — clean-code + shadcn-first + ports/adapters rules.
3. `spec-schema.yaml` — frontmatter contract for module-level `spec.md` files.
4. `src/**/spec.md` — per-module current-state description.
5. `specs/NNN-*/` — feature-scoped work (authored via `/speckit-*` commands).

## Slash commands

Same set as the backend. See [`../be_ddc_helper/README.md`](../be_ddc_helper/README.md#slash-commands).
