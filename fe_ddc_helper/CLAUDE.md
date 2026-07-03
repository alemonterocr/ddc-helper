# CLAUDE.md — fe_ddc_helper

Navigation guide for AI agents working in this subproject. Auto-loaded by
Claude Code. Read this before touching any file.

## What this is

Chrome extension (React + TypeScript, Manifest v3, Vite) that captures a DOM
skeleton from a live dealer website, sends it to the `be_ddc_helper`
backend, and executes the returned section plan in the active DDC CMS tab.

## Architecture

Two orthogonal patterns:

- **UI layer**: Atomic Design (atoms → molecules → organisms → templates → pages)
- **Service layer**: Ports & adapters (interfaces vs implementations)

```
src/
├── components/
│   ├── ui/            — shadcn primitives (Button, Input, Dialog, etc.)
│   ├── atoms/         — custom base elements not covered by shadcn
│   ├── molecules/     — composed atoms (UrlInputCard, CredentialChecker)
│   ├── organisms/     — composed molecules with state (MigrationForm, PlanPreview)
│   ├── templates/     — layout wrappers
│   └── pages/         — full views wired to services
├── services/
│   ├── ports/         — TypeScript interfaces only
│   └── adapters/      — concrete implementations (chrome.*, fetch, WS)
├── scripts/           — self-contained injected scripts (NO imports, ever)
├── store/             — Zustand store with chrome.storage persistence
├── types/             — shared TypeScript types
└── lib/               — shadcn utilities (cn helper, etc.)
```

Full clean-code, styling, and shadcn-first rules live in
`.specify/memory/constitution.md`. Do not violate them.

## Design context

- `PRODUCT.md` (repo root) — strategic design context: register, users, personality (precise, quiet, reliable), anti-references, 5 design principles.
- `DESIGN.md` (repo root) — visual system: OKLCH token frontmatter, "The Quiet Console" north star, palette / typography / elevation / component specs, Do's and Don'ts.
- Every UI change must respect both. Impeccable slash commands (`/impeccable audit`, `/impeccable critique`, `/impeccable polish`) read them automatically.

## Critical constraint on `scripts/`

Files in `scripts/` are serialized (`.toString()`) and injected into browser
tabs via `chrome.scripting.executeScript`. They MUST be fully self-contained:
zero imports, zero closures over module-level variables. Vite minifies
module-level names, so external references break silently in production. All
helpers must be defined as named functions **inside** the script function body.

## `extractSkeleton` pruning model

Class-based pruning (`isChromeByClass`) is not final — it is overridden by
`subtreeHasContentAnchor` when the subtree contains high-value content signals
(forms, DDC dotagging attributes, CTA buttons, phone numbers, hours tables).
This rescue check exists because dealer sites often place content-heavy widgets
inside divs with chrome-sounding class names (e.g. `sideBar`). See
`src/scripts/spec.md` for the full pruning order.

## Before writing a component

1. **Check `src/components/ui/` first** — this is a shadcn/ui consumer. If a
   shadcn primitive fits, use it or add it via `npx shadcn@latest add <name>`.
   Do not hand-roll an equivalent.
2. Read the component's `spec.md`.
3. Check that all dependency components exist and are at least `built`.
4. Components must not call `chrome.*` APIs directly — go through a service port.

## Before writing a service adapter

1. Read the port interface first (`services/ports/`).
2. Adapters must implement the port exactly — no extra public methods.
3. `CMSInjectionAdapter` delegates to files in `scripts/` — it does not
   contain injection logic itself.

## Spec file format (module-level `spec.md`)

Every module has a `spec.md` with YAML frontmatter. Schema lives in
`spec-schema.yaml` at the subproject root.

```yaml
---
name: ComponentName
type: atom | molecule | organism | template | page | port | adapter | script | model
status: planned | in-progress | built | tested
atomic-layer: atom | molecule | organism | template | page   # UI only
---
```

Same status ladder as the backend: a module's status cannot exceed the status
of any dependency.

## Feature-level specs (Spec Kit)

Feature-scoped work lives under `specs/NNN-feature-name/` and is authored via
the `/speckit-*` slash commands. Module-level `spec.md` files describe current
state; feature specs describe *proposed change*. Both coexist.

## Key contracts (do not violate)

- Components never import from `services/adapters/` directly — only from `services/ports/`. Only `pages/` may import adapters.
- Files in `scripts/` have zero imports (see the critical constraint above).
- All DDC API calls use `credentials: 'include'` and the `x-coxauto-traffic-group` header.
