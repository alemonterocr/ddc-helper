# Implementation Plan: Translate Page Widgets

**Branch**: `master` (feature dir `specs/004-translate-pages`) | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-translate-pages/spec.md`

## Summary

Automate the manual two-composer page-translation workflow with a **streaming fan-out LangGraph workflow**. The FE fetches a page's rendered HTML in both `en_US` and `es_US` (browser session, injected scripts) and streams both into a new BE endpoint. A graph extracts the editable content + RAW-HTML widgets (BeautifulSoup), uses the existing `judge_translation` to decide which already carry a genuine Spanish translation, fans out one `translate_labels_graph` invocation per remaining widget via LangGraph's `Send` API, and streams each result back as NDJSON as it lands. The FE renders a live-filling review board; on save it writes `es_US` then re-writes the original `en_US` (DDC wipes English otherwise). The graph is pure compute over the two HTML blobs passed in — it never touches DDC.

## Technical Context

**Language/Version**: Python 3.13 (BE); TypeScript/React (FE, `fe_ddc_helper`)

**Primary Dependencies**: FastAPI, LangGraph (`Send` + `astream`), `beautifulsoup4` + `lxml` (NEW), existing `LLMPort` providers (Anthropic / Gemini / DeepSeek). FE: `chrome.scripting`, `fetch` ReadableStream.

**Storage**: N/A — stateless request/stream. FE persists rows in the Zustand store (`chrome.storage`).

**Testing**: pytest + pytest-asyncio (`asyncio_mode = "auto"`), mock `LLMPort`.

**Target Platform**: Local uvicorn server (BE) + Chrome MV3 extension (FE).

**Project Type**: Cross-cutting feature spanning a web-service backend + a browser-extension frontend. This plan is authored in `be_ddc_helper`; FE contracts are referenced, FE implementation follows the same spec.

**Performance Goals**: First `widget` event streamed as soon as the fastest branch resolves; fan-out concurrency capped (default 5) to respect provider rate limits; `extracted` event emitted before the check LLM calls so the board is never blank.

**Constraints**: Graph stays browser-free (no WS-RPC tool nodes); domain layer keeps zero external imports (bs4 lives in application); request bodies up to ~4 MB (two page renders).

**Scale/Scope**: A page carries ~5–30 editable widgets; each render is 0.5–2 M chars. One page translated per stream invocation.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Names reveal intent | PASS | `extract_widgets`, `check_translations_node`, `route_to_widget_branches`, `translate_widget_node`, `build_translate_page_graph`. |
| II. Small functions | PASS | Each node does one thing; extraction split into `find_main` / `collect_widgets` / `pair_by_id`. |
| III. Small classes | PASS | No new classes beyond Pydantic DTOs + a `TypedDict` state. |
| IV. Explicit errors | PASS | Extraction returns an empty widget list for "no `.main`" (a valid result, not a failure sentinel); transport/LLM failures surface as a terminal `error` stream event; `judge_translation` already fails open. No bare `except`. |
| V. Code over comments | PASS | Comment only the DDC quirks (two-save, `-editable` suffix) — the WHY. |
| **Hexagonal: domain zero external imports** | **PASS (by relocation)** | `widget_extract.py` moves from `domain/` → **`application/translate_pages/`**. bs4 must not enter `src/domain/`. |
| Ports import only domain | PASS | No new port needed on BE (reuses `LLMPort`). |
| Application imports ports/domain only | PASS | `translate_pages/` imports `LLMPort`, reuses `translate_labels_graph`; no adapter imports. |
| Adapters don't import each other | PASS | New streaming route (inbound http) imports the graph (application) + DTOs; imports no other adapter. |
| **LangGraph: I/O in nodes, routing pure** | **PASS (by split)** | The LLM check runs in `check_translations_node`; the `Send` fan-out is a **separate pure routing function** `route_to_widget_branches(state) -> list[Send]` (reads state only). |
| LangGraph: partial state updates | PASS | Nodes return only changed keys; fan-in via `Annotated[list, operator.add]`. |

**Result: no violations.** Complexity Tracking omitted. The one gate that would have failed (bs4 in domain) is resolved by placing extraction in the application layer — the spec's §7 file map is updated to match.

## Project Structure

### Documentation (this feature)

```text
specs/004-translate-pages/
├── spec.md              # Feature spec (already written)
├── plan.md              # This file
├── research.md          # Phase 0 — Send/streaming/bs4 decisions
├── data-model.md        # Phase 1 — DTOs, graph state, events, FE store types
├── quickstart.md        # Phase 1 — end-to-end validation scenarios
├── contracts/
│   ├── translate-page.stream.md   # POST /translations/translate-page (NDJSON)
│   └── ddc-endpoints.md           # FE↔DDC: render GET, SaveContent, sitecontent
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code

```text
be_ddc_helper/
├── src/
│   ├── application/
│   │   └── translate_pages/            # NEW use-case package
│   │       ├── spec.md                 # module-level spec (frontmatter)
│   │       ├── state.py                # PageTranslateState TypedDict
│   │       ├── widget_extract.py       # bs4 extraction (application, NOT domain)
│   │       ├── extract_node.py         # node: extract → to_translate/skipped candidates
│   │       ├── check_node.py           # node: judge_translation on ambiguous widgets
│   │       ├── routing.py              # pure route_to_widget_branches → list[Send]
│   │       ├── translate_widget_node.py# node: invoke translate_labels_graph per widget
│   │       └── translate_page_graph.py # build_translate_page_graph(llm)
│   ├── adapters/inbound/http/
│   │   ├── translations_router.py      # + POST /translations/translate-page (streaming)
│   │   └── translations_dtos.py        # + WidgetType, PageWidget, TranslatePageRequest
│   └── application/translate_labels/   # REUSED unchanged (subgraph + judge)
├── tests/
│   ├── test_widget_extract.py          # extraction, pairing, -editable, round-trip
│   └── test_translate_page_graph.py    # check logic, fan-out count, event order (mock LLM)
└── pyproject.toml                      # + beautifulsoup4, lxml

fe_ddc_helper/                          # (implemented per spec §5, tracked in tasks.md)
└── src/
    ├── services/ports/PagePort.ts
    ├── services/adapters/PageAdapter.ts + ddcTab.ts (shared tab/JWT helpers)
    ├── components/organisms/PageTranslateTab/
    ├── components/molecules/WidgetRow/            # if LabelRow reuse insufficient
    ├── store/ (pages, SpanishWidgetRow)
    └── components/pages/ProjectPage/ProjectPage.tsx  # 3rd tab
```

**Structure Decision**: Backend work lands in a new cohesive `application/translate_pages/` package (graph + nodes + extraction) plus additive routes/DTOs in the existing translations adapter — mirroring how `translate_labels/` is organized. Extraction lives in the application layer, not domain, to honor the zero-external-imports rule. FE follows the atomic-design + ports/adapters layout already used by 002/003.

## Phase 0 — Research

See [research.md](./research.md). Resolves: `Send` fan-out + fan-in accumulator pattern; LangGraph `astream` → FastAPI `StreamingResponse` NDJSON; `fetch` ReadableStream consumption on MV3; bs4 inner-HTML fidelity (`decode_contents`); check-node concurrency.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — `PageWidget`, `TranslatePageRequest`, `PageTranslateState`, stream event union, FE store types.
- [contracts/translate-page.stream.md](./contracts/translate-page.stream.md) — request + NDJSON event schema + ordering/abort semantics.
- [contracts/ddc-endpoints.md](./contracts/ddc-endpoints.md) — FE-side DDC contracts (render GET, SaveContent, sitecontent) with the `-editable` rule and two-save order, sourced from the HARs.
- [quickstart.md](./quickstart.md) — runnable BE validation + manual FE walkthrough.

Agent-context update: the repo has no `update-agent-context` script; the `CLAUDE.md` feature-spec indices were updated by hand when the spec landed.

## Complexity Tracking

No constitution violations — section intentionally empty.
