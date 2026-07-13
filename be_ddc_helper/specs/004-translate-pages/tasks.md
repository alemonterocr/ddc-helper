---
description: "Task list for 004-translate-pages implementation"
---

# Tasks: Translate Page Widgets

**Input**: Design documents from `specs/004-translate-pages/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the spec file map and [quickstart.md](./quickstart.md) call for `test_widget_extract.py` and `test_translate_page_graph.py`. BE gets automated tests; FE is validated via the quickstart manual walkthrough.

**Organization**: Grouped by user story. Paths are repo-relative (`be_ddc_helper/…`, `fe_ddc_helper/…`).

## User stories (from spec)

- **US1 (P1, MVP)** — BE streaming translate-page graph: fetch-agnostic. Given both page HTMLs, extract widgets, decide what needs translating (LLM-assisted), fan out per-widget translation via `Send`, stream results as NDJSON. Independently testable offline (unit tests) + via the streaming smoke test with saved HTML fixtures.
- **US2 (P2)** — FE load + streaming review board (read-only): user enters a path, the extension fetches both renders and streams them to US1's endpoint, cards fill in progressively. Independently testable: cards populate from a live page (no save yet).
- **US3 (P3)** — Save + skip/force/retranslate: the two-save dance writes `es_US` then re-writes original `en_US`; skip, retranslate-one, and force-translate wired. Independently testable: save a widget, confirm both locales in DDC.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Add `beautifulsoup4` and `lxml` to `be_ddc_helper/pyproject.toml` dependencies and `be_ddc_helper/requirements.txt`, then `uv sync`
- [x] T002 [P] Create BE package `be_ddc_helper/src/application/translate_pages/` with `__init__.py` and a module-level `spec.md` (frontmatter: `type: graph`, `status: planned`, `layer: application`)
- [x] T003 [P] Create FE folders `fe_ddc_helper/src/components/organisms/PageTranslateTab/` and `fe_ddc_helper/src/components/molecules/WidgetRow/` each with a placeholder `spec.md` (frontmatter: `status: planned`)

---

## Phase 2: Foundational (Blocking Prerequisites for the FE stories)

**Purpose**: Shared FE type + helper layer that US2 and US3 both build on. **US1 (BE) does NOT depend on this phase** — it can start right after Setup.

- [x] T004 [P] Add page types to `fe_ddc_helper/src/types/index.ts`: `WidgetType`, `PageWidget`, `PageWidgetResult`, `TranslatePageRequest`, `PageLoadResult`, `PageStreamEvent` (per [data-model.md](./data-model.md) §5)
- [x] T005 [P] Add store types to `fe_ddc_helper/src/store/types.ts`: `WidgetRowStatus`, `SpanishWidgetRow`, and optional `pages?: Record<string, SpanishWidgetRow[]>` on `SpanishMigrationProject` (per [data-model.md](./data-model.md) §6)
- [x] T006 Extract shared `findComposerTabId` + `_extractUserId` into `fe_ddc_helper/src/services/adapters/ddcTab.ts` and refactor `LabelAdapter.ts` to import them (no behavior change)

**Checkpoint**: FE shared layer ready — US2/US3 can begin.

---

## Phase 3: User Story 1 - BE streaming translate-page graph (Priority: P1) 🎯 MVP

**Goal**: One streaming endpoint turns two page-HTML blobs into per-widget translations, streamed as they complete.

**Independent Test**: `pytest tests/test_widget_extract.py tests/test_translate_page_graph.py` pass; the [quickstart.md](./quickstart.md) §2 smoke test prints `extracted → skipped → widget… → done`.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL before implementation)

- [x] T007 [P] [US1] `be_ddc_helper/tests/test_widget_extract.py`: content+raw extraction, `widget_type` classification, `window_id` (with `-editable`), en/es pairing by id, missing-es → `es_html==""`, `decode_contents` inner-HTML round-trip stability, no-`div.main` → empty list
- [x] T008 [P] [US1] `be_ddc_helper/tests/test_translate_page_graph.py` (mock `LLMPort`): check three-way (empty→translate, es==en→translate, distinct+`judge ok`→skip, `not ok`→translate), fan-out count == `len(to_translate)`, event sequence `extracted→skipped→widget×N→done`, raised error → terminal `error` event

### Implementation for User Story 1

- [x] T009 [P] [US1] Add DTOs to `be_ddc_helper/src/adapters/inbound/http/translations_dtos.py`: `WidgetType(str, Enum)`, `PageWidget`, `TranslatePageRequest` (per [data-model.md](./data-model.md) §2)
- [x] T010 [P] [US1] Create `be_ddc_helper/src/application/translate_pages/state.py`: `PageTranslateState` TypedDict with `results: Annotated[list[dict], operator.add]`
- [x] T011 [US1] Create `be_ddc_helper/src/application/translate_pages/widget_extract.py`: `extract_widgets(en_html, es_html)` — bs4 `find(div.main)`, collect widgets by class, `decode_contents()`, pair by `window_id`; small helpers (`_find_main`, `_collect_widgets`, `_pair_by_id`). Application layer, NOT domain (constitution)
- [x] T012 [US1] Create `be_ddc_helper/src/application/translate_pages/extract_node.py`: node calling `widget_extract` → writes `candidates` (partial state update only)
- [x] T013 [US1] Create `be_ddc_helper/src/application/translate_pages/check_node.py`: three-way classify; `judge_translation` on ambiguous widgets under an `asyncio.Semaphore`; writes `to_translate` + `skipped`
- [x] T014 [US1] Create `be_ddc_helper/src/application/translate_pages/routing.py`: pure `route_to_widget_branches(state) -> list[Send]` (one `Send("translate_widget", {...})` per `to_translate` widget; no I/O)
- [x] T015 [US1] Create `be_ddc_helper/src/application/translate_pages/translate_widget_node.py`: invoke `translate_labels_graph` for one widget's `en_html`; return `{"results": [widget_result]}`
- [x] T016 [US1] Create `be_ddc_helper/src/application/translate_pages/translate_page_graph.py`: `build_translate_page_graph(llm)` wiring `extract → check → (conditional Send via routing) → translate_widget → END`
- [x] T017 [US1] Add `POST /translations/translate-page` to `be_ddc_helper/src/adapters/inbound/http/translations_router.py`: `StreamingResponse(media_type="application/x-ndjson")` driving `graph.astream(stream_mode="updates")`, mapping node updates → `extracted`/`skipped`/`widget`/`done` lines, wrapping errors as a terminal `error` line (per [contracts/translate-page.stream.md](./contracts/translate-page.stream.md))
- [x] T018 [US1] Wire provider via existing `get_llm_factory` dependency + `reset_usage`; run T007/T008 and the quickstart §2 smoke test to green

**Checkpoint**: US1 fully functional and testable with zero FE.

---

## Phase 4: User Story 2 - FE load + streaming review board (Priority: P2)

**Goal**: User enters a target path, the extension fetches both renders and streams them to US1; a review board fills in progressively.

**Independent Test**: Open the Translate Page tab, load a real page → placeholder cards appear on `extracted`, resolve as `widget` events arrive, skipped footer populates. No save yet.

### Implementation for User Story 2

- [x] T019 [US2] Create `fe_ddc_helper/src/services/ports/PagePort.ts`: `loadPage`, `translatePageStream`, `saveWidget` signatures (per [spec.md](./spec.md) §5.3)
- [x] T020 [US2] Implement `loadPage` in `fe_ddc_helper/src/services/adapters/PageAdapter.ts`: `loadPageInjected(slug, targetPath, locale)` self-contained render GET (`credentials:'include'`), via shared `findComposerTabId`
- [x] T021 [US2] Implement `translatePageStream` in `PageAdapter.ts`: `fetch` POST + `res.body.getReader()` + `TextDecoder`, buffer + split on `\n`, `JSON.parse` each line → `onEvent`, honor `AbortSignal` (per [research.md](./research.md) R3)
- [x] T022 [US2] Add store actions in `fe_ddc_helper/src/store/useMigrationStore.ts`: seed `pages[path]` placeholder rows on `extracted`, resolve a row on each `widget` event (match by `windowId`)
- [x] T023 [US2] Create `fe_ddc_helper/src/components/organisms/PageTranslateTab/PageTranslateTab.tsx`: path input + Load button → `Promise.all([loadPage(en_US), loadPage(es_US)])` → open stream → placeholder cards + counters + skipped footer; `ensureProvider` pattern reused from `NavTranslateTab`
- [x] T024 [US2] Create `fe_ddc_helper/src/components/molecules/WidgetRow/WidgetRow.tsx` (or adapt `LabelRow`): EN preview (collapsible), ES editor, `content`/`raw` badge, warnings + reasoning
- [x] T025 [US2] Wire the 3rd tab `[Translate Page]` in `fe_ddc_helper/src/components/pages/ProjectPage/ProjectPage.tsx` (Spanish branch `<Tabs>`)
- [x] T026 [US2] Register `PageAdapter`/`PagePort` in `fe_ddc_helper/src/services/ServicesContext` and export the organism from `organisms/index.ts`

**Checkpoint**: US1 + US2 — a page's widgets stream into a live review board.

---

## Phase 5: User Story 3 - Save (two-save) + skip/force/retranslate (Priority: P3)

**Goal**: Commit translations back to DDC with the two-save dance, plus per-card skip/retranslate and force-translate from the skipped footer.

**Independent Test**: [quickstart.md](./quickstart.md) §3 — click Save on a content and a raw widget, confirm two ordered DDC writes each and that English survives.

### Implementation for User Story 3

- [x] T027 [US3] Implement `saveWidget` in `PageAdapter.ts`: `saveWidgetInjected` doing the two-save — **content** → `SaveContent` ×2 (`currentLocale` es_US then en_US, `windowId` keeps `-editable`, includes `userId` from JWT); **raw** → `sitecontent` ×2 (`{"es_US":…}` then `{"en_US":…}`, `windowId` strips `-editable`); abort the English write if the Spanish write fails (per [contracts/ddc-endpoints.md](./contracts/ddc-endpoints.md))
- [x] T028 [US3] Wire handlers in `PageTranslateTab.tsx`: Save → `saveWidget` → `saved`; Retranslate → existing `POST /translations/translate` via `LabelPort.translateLabel`; Skip → `skipped`
- [x] T029 [US3] Force-translate in the skipped footer: move the row into the board (`translating`) and run translation (mirrors `NavTranslateTab.handleForceTranslate`)
- [ ] T030 [US3] Run [quickstart.md](./quickstart.md) §3 live walkthrough; confirm both-locale writes and English intact

**Checkpoint**: Full loop working end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T031 [P] Confirm/adjust concurrency caps: check-node judge `Semaphore` and fan-out width (default 5) in `check_node.py` / graph config
- [ ] T032 [P] Add stream-reader edge tests (partial-line buffering, mid-stream `error`, abort) for `PageAdapter.translatePageStream`
- [ ] T033 [P] Flip module `spec.md` statuses `planned → built` for `translate_pages` and the new FE components
- [ ] T034 Update `specs/004-translate-pages/spec.md` **Status: PLANNED → BUILT** and refresh both `CLAUDE.md` feature-spec one-liners if wording drifted

---

## Dependencies & Execution Order

### Phase dependencies
- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: after Setup; blocks **US2 + US3** only. **US1 does not depend on it.**
- **US1 (P1)**: after Setup (Phase 1). Fully independent of the FE.
- **US2 (P2)**: after Foundational + a running US1 endpoint (needs the stream to consume).
- **US3 (P3)**: after US2 (extends the same tab/adapter).
- **Polish**: after the stories it touches.

### Story independence
- US1 is standalone (BE only) — the MVP.
- US2 needs US1's endpoint live but is otherwise its own increment (read-only board).
- US3 layers write-back onto US2's board.

### Within US1
- Tests (T007–T008) written first and failing.
- DTOs/state (T009–T010) → extraction (T011) → nodes (T012–T015) → graph (T016) → route (T017) → wiring (T018).

---

## Parallel Opportunities

- **Setup**: T001, T002, T003 all [P].
- **Foundational**: T004, T005 [P] (T006 touches `LabelAdapter`, keep sequential).
- **US1 tests**: T007, T008 [P]. **US1 impl**: T009, T010 [P] (independent files); T011–T016 are largely sequential (same package, import chain).
- **Cross-story**: once US1's endpoint is up, a second developer can take US2 while US1 polish continues.
- **Polish**: T031, T032, T033 [P].

### Parallel example: US1 kickoff
```bash
Task: "T007 test_widget_extract.py"
Task: "T008 test_translate_page_graph.py"
Task: "T009 BE DTOs in translations_dtos.py"
Task: "T010 PageTranslateState in state.py"
```

---

## Implementation Strategy

### MVP (US1 only)
1. Phase 1 Setup → 2. Phase 3 US1 (skip Phase 2 — it's FE) → 3. **STOP & VALIDATE**: unit tests + streaming smoke test green. The backend is demonstrably correct before any extension work.

### Incremental delivery
1. US1 → validated BE stream (MVP).
2. + Foundational + US2 → live review board (read-only).
3. + US3 → full write-back loop.
Each increment is independently testable and adds user-visible value.

---

## Notes
- `[P]` = different files, no incomplete-task dependency.
- `[US#]` maps each task to its story for traceability.
- Per-widget translation is text-node based (`html_translate` + `translate_text_segments`) — it does NOT reuse `translate_labels_graph` (that truncated large widgets; see spec §3.4).
- The checker is the existing `judge_translation` — do not write a new judge prompt.
- Keep the graph browser-free; all DDC I/O stays in FE injected scripts.
- Commit after each task or logical group; validate at each checkpoint.
