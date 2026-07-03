# DDC Helper

Chrome extension + FastAPI backend that clones dealership websites into DDC
CMS. Captures a live dealer page's DOM in the browser, runs a
deterministic + LLM hybrid pipeline on the backend to produce a section
plan, and executes injection back into DDC CMS from the specialist's own
authenticated session.

Internal tool for DDC migration specialists at Cox Automotive.

## Repo layout

```
ddc-page-builder/
├── be_ddc_helper/       # Python 3.13 + FastAPI + LangGraph backend
├── fe_ddc_helper/       # React + TypeScript + Vite Chrome extension (Manifest v3)
└── scripts/             # Monorepo-wide helper scripts (pre-commit hook, etc.)
```

Each subproject has its own `README.md`, `CLAUDE.md` (agent navigation
guide, auto-loaded by Claude Code), `.specify/memory/constitution.md`
(clean-code + architecture rules), and `spec-schema.yaml` (module `spec.md`
frontmatter contract).

## Prerequisites

- **Python 3.13** — [`uv`](https://docs.astral.sh/uv/) will install it for you if you don't have it. If you prefer plain `pip`, a locked `requirements.txt` is provided.
- **Node 20+** and **npm**.
- **Chrome** (or Chromium-based browser with `chrome://extensions` support).
- **An LLM API key** — pick one provider: DeepSeek (recommended — cheap, fast), Anthropic, or Gemini. Signup links in the "First run" section below. You supply your own; no shared team key.

## Setup

### Backend (`be_ddc_helper/`)

Using `uv` (preferred):

```powershell
cd be_ddc_helper
uv sync
```

Or using `pip`:

```powershell
cd be_ddc_helper
python -m venv .venv
.venv\Scripts\activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend (`fe_ddc_helper/`)

```powershell
cd fe_ddc_helper
npm install
npm run build              # produces dist/ + rasterizes favicon → PNG icons
```

## Running

### 1. Start the backend

```powershell
cd be_ddc_helper
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Leave this running. The extension talks to it at `http://localhost:8000` for `/analyze` and `/execute`, and connects a WebSocket bridge for the browser-side RPC.

### 2. Load the extension in Chrome

1. Open `chrome://extensions`.
2. Toggle **Developer mode** on (top right).
3. Click **Load unpacked**.
4. Select `fe_ddc_helper/dist/`.

You should now see **DDC Helper** in your extensions list and a teal-on-ivory page icon in your Chrome toolbar.

## First run

Before the first migration you need three things wired up:

1. **Configure an LLM provider.** Click the extension icon → "Open DDC Helper" → click the ⚙ settings icon (top right of the projects screen) → pick a provider and paste your API key. Get one from:
   - DeepSeek — [platform.deepseek.com](https://platform.deepseek.com/) (recommended: cheapest, comparable quality)
   - Anthropic — [console.anthropic.com](https://console.anthropic.com/)
   - Gemini — [aistudio.google.com](https://aistudio.google.com/)

2. **Log into DDC CMS.** The extension uses your own DDC session cookies — it cannot log in for you. Open the DDC CMS tab you'd normally work in, log in as usual, then click any widget on any page (this seeds the `CC-IDT` token the backend needs).

3. **Verify credentials.** Open a project → the right sidebar has a **Credentials** section with a **Check** button. It should light up green for CC-IDT Token and LLM API key (and Media Library tab for CM / GM Prebuild projects — Spanish translation doesn't need it).

## Working with the code

Coding agents (Claude Code, Cursor, etc.) can navigate this repo autonomously — each subproject's `CLAUDE.md` explains the architecture, layer rules, and where to find module-level `spec.md` files. Just `cd` into `be_ddc_helper/` or `fe_ddc_helper/` and start.

### Backend

- Layered: `domain` → `ports` → `application` → `adapters`. Rules in `.specify/memory/constitution.md`.
- Uses **LangGraph** for the analyze pipeline (`application/migration/`), Salesforce intake, staff extraction, nav parsing, and label translation. Not to be deployed as autonomous agents — the extension is a required thin executor for auth reasons.
- Tests: `uv run python -m pytest -v`.

### Frontend

- Atomic Design (`atoms → molecules → organisms → templates → pages`) + Ports & Adapters (`services/ports` vs `services/adapters`). Rules in `.specify/memory/constitution.md`.
- **shadcn/ui first** — check `src/components/ui/` before writing anything new. `npx shadcn@latest add <name>` to add a primitive.
- Files in `src/scripts/` are injected into browser tabs via `chrome.scripting.executeScript` and must be self-contained (zero imports, zero closures over module-level variables).
- Type-check: `npx tsc --noEmit`. Tests: `npm test`.

### Pre-commit hooks

One-time setup per clone:

```powershell
pip install pre-commit
pre-commit install
```

Currently just one hook: **`uv-export-requirements`** regenerates
`be_ddc_helper/requirements.txt` from `pyproject.toml` + `uv.lock` when
either changes, and stages it into the same commit. This keeps the `pip`
path in sync with the `uv` path with zero manual step.

Run across the whole tree at any time:

```powershell
pre-commit run --all-files
```

### Feature specs (Spec Kit)

Feature-scoped work lives under `<subproject>/specs/NNN-feature-name/`. Authored via slash commands in Claude Code:

- `/speckit-specify` — draft a new feature spec
- `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` — plan and build
- `/speckit-converge` — audit code vs. spec/plan/tasks and append remaining work
- `/speckit-analyze` — cross-check spec/plan/tasks for drift

Module-level `spec.md` files (in each `src/**` folder) describe *current state*. Feature specs describe *proposed change*.

## Constraints worth knowing before you touch anything

- **Browser is a thin executor, backend is a coordinator.** Every DDC / Salesforce / dealer-site call must originate from the specialist's Chrome (session cookies, WAF, CSRF). The backend never calls those APIs directly. This is why the system can't be deployed as a headless service.
- **`sectionType` values must match `sectionName` in `be_ddc_helper/src/domain/catalog/ddc_catalog.json`.** The catalog is source of truth.
- **Design system is dark-mode-only** with Steady Teal as the single primary accent. Rules in `fe_ddc_helper/DESIGN.md`. Strategic principles in `fe_ddc_helper/PRODUCT.md`.
