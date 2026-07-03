# be_ddc_helper

Backend for the DDC Agentic Page Cloner. FastAPI + LangGraph service that
turns a captured DOM skeleton into an ordered DDC section plan, then
orchestrates execution back to the Chrome extension over WebSocket RPC.

Companion frontend: [`../fe_ddc_helper/`](../fe_ddc_helper/).

## Pipeline

```
prune → chrome_review → build → typify → image_split → convert → enrich → END
```

Deterministic algorithm (split across `src/domain/migration/{_atoms,chrome,
tree_cleanup,buttons,chunking,discovery}.py`, with a re-export shim at
`src/domain/deterministic_migrate.py`) handles layout structure. LLM gates
only resolve bounded uncertainty (KEEP/DROP, widget-type classification,
image promotion, HTML beautify + intent). See
`src/application/migration/spec.md` for the full architecture note.

## Run locally

Requires Python 3.13 + [`uv`](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Test

```powershell
uv run python -m pytest -v
```

## How this repo is organized (agent reading order)

1. `CLAUDE.md` — auto-loaded navigation guide.
2. `.specify/memory/constitution.md` — clean-code + hexagonal layer rules.
3. `spec-schema.yaml` — frontmatter contract for module-level `spec.md` files.
4. `src/*/spec.md` — per-module current-state description.
5. `specs/NNN-*/` — feature-scoped work (authored via `/speckit-*` commands).

## Slash commands

Installed by Spec Kit; work when Claude Code is running in this subproject:

| Command | Use |
|---|---|
| `/speckit-constitution` | Author or amend the project constitution (clean-code + layer rules) |
| `/speckit-specify` | Draft a new feature spec |
| `/speckit-clarify` | Force ambiguity resolution before planning |
| `/speckit-plan` | Turn spec into a technical plan |
| `/speckit-tasks` | Break plan into ordered tasks |
| `/speckit-taskstoissues` | Convert task list into tracker issues |
| `/speckit-implement` | Execute the tasks |
| `/speckit-converge` | Audit code vs. spec/plan/tasks; append leftover work |
| `/speckit-analyze` | Cross-check spec/plan/tasks for drift |
| `/speckit-checklist` | Generate quality checklists |
