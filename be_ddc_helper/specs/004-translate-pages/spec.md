# Translate Page Widgets

**Status:** PLANNED
**Date:** 2026-07-06
**Purpose:** Automate the manual "two-composer" page-translation dance with a streaming fan-out LangGraph workflow. The FE pulls a page's rendered HTML in both `en_US` and `es_US`; a new graph extracts the editable content + RAW-HTML widgets, uses an LLM to decide which already have a genuine Spanish translation, fans out one translate branch per remaining widget, and streams each result back as it finishes. The user batch-reviews every card and saves — the extension writes `es_US`, then re-writes the original `en_US` (DDC's quirk: saving only the Spanish side wipes the English).

---

## 1. Goal

Replace the human workflow — open two DDC composers side by side, copy an English content widget, paste into a Gemini chat, copy the answer, paste into the Spanish composer, Save on Spanish, Save on English — with a one-button-per-page flow inside the extension, where all of a page's widgets translate in parallel and stream into a review board.

For a target page (e.g. `/new-inventory/index.htm`) the specialist:
1. Loads the page's editable widgets (both locales) with one click.
2. Watches cards appear and fill in as translations stream back.
3. Batch-reviews each machine translation; retranslates any single card independently.
4. Saves per card — the extension writes `es_US`, then re-writes the original `en_US`.

**Anti-goals:**
- Do NOT auto-save. Every widget translation gets human review, same as 002/003.
- Do NOT re-translate widgets that already have a *genuine* Spanish translation. Detection is deterministic where it can be and LLM-assisted where it can't (see §3.3), with a "force translate" escape hatch.
- Do NOT make DDC calls from the Python backend. The browser holds session cookies. The graph operates purely on the two HTML blobs the FE hands it; the FE performs every DDC render GET and save POST.
- Do NOT change the English content. The second save re-writes the *original* English verbatim; it exists only to defeat DDC's wipe-on-Spanish-save behavior.

---

## 2. Why a LangGraph workflow here (when 002/003 deliberately avoided one)

002 and 003 use a flat endpoint because their skip-check is pure regex and their translation is a single call per item. **This feature is different on both counts:**

1. **Detection needs an LLM.** DDC auto-injects Spanish *placeholder* text (Spanish lorem-ipsum) into untranslated `es_US` widgets. That text is non-empty and `!= en`, so no regex can tell it apart from a real translation. Deciding "does this existing `es` faithfully translate this `en`?" is an LLM judgment — reusing the existing `judge_translation`.
2. **Fan-out + streaming.** A page has many widgets; the user wants them translated in parallel and streamed into a batch-review board. That is a map-reduce shape with per-branch progress — exactly what LangGraph's `Send` API + streaming express cleanly.

So a graph is warranted. Crucially, it stays **pure compute over state passed in** — like every other graph in this repo (`migration_graph`, `translate_labels_graph`), it never touches the browser. The FE fetches the renders and passes both HTML strings in as initial state.

---

## 3. Architecture & pipeline

```
FE (injected scripts, browser session)                 BE — build_translate_page_graph (NEW, streaming)
──────────────────────────────────────                 ─────────────────────────────────────────────────
loadPage(path, en_US) ─┐  (Promise.all, parallel)
loadPage(path, es_US) ─┴─► POST /translations/translate-page  (NDJSON StreamingResponse)
                             { en_page_html, es_page_html, dealer_name, provider }
                                          │
                             ┌─ extract_widgets ─ bs4: find div.main, collect widgets by class,
                             │                     pair en/es by id            → emits "extracted"
                             │        │
                             │      check ─ per widget: empty|es==en ⇒ translate (no LLM);
                             │        │      else judge_translation(en,es) ⇒ skip|translate
                             │        │                                        → emits "checked"{to_translate,skipped}
                             │        ▼
                             │   Send(one branch per to_translate widget)  ← true fan-out
                             │        │
                             │   translate_widget ─ invokes translate_labels_graph (REUSED)
                             │        │              per widget                → emits "widget" (streamed)
                             │        ▼
                             └─ END                                           → emits "done"
   cards fill in progressively (keyed by window_id) ◄──── stream ────────────────┘

   [Save on a card] ─► saveWidget(): 1) write es_US   2) write en_US (original)   (injected script)
```

### 3.1 Load page renders — FE injected script (`loadPage`), fired twice in parallel

```
GET https://{dealerId}.website.dealercenter.coxautoinc.com{targetPath}
      ?_renderer=desktop&buildingPage=false&useAjaxWrap=true
      &locale={en_US|es_US}&_toggleBasePageCache=false
```

- `dealerId` — project dealer slug (also the composer hostname's first label).
- `targetPath` — user-entered, e.g. `/new-inventory/index.htm`.

Response is a large HTML doc (≈500k–2M chars). The FE fires both locales concurrently (`Promise.all`) inside the composer tab (`chrome.scripting.executeScript`, `credentials:'include'`) and passes **both raw HTML strings** into the streaming endpoint. No FE-side parsing — extraction is a BE graph node. Injected-script constraints unchanged (self-contained, zero imports).

### 3.2 `extract_widgets` node — bs4 (`application/translate_pages/widget_extract.py`)

> Extraction lives in the **application** layer, not `domain/` — the constitution forbids external imports (bs4) in `domain/`. See plan.md Constitution Check.

1. For each locale, `BeautifulSoup(html, "lxml")` → find `div.main`. Absent ⇒ empty result (FE shows "no editable content found").
2. Within `.main`, collect editable widgets by class:
   - `div.text-content-container.editable.content` → `widget_type="content"`
   - `div.content.editable-raw-content` → `widget_type="raw"`
   - Each carries `id` like `SITEBUILDER_ALE_MONTERO_1:content1-editable` — both the extraction key and the save `windowId`.
3. Pair en/es by `id`. `en_html`/`es_html` = **inner** HTML of each widget (via `decode_contents()`; `es_html=""` if the id is missing on the es side).
4. Emit an **`extracted`** event with the widget count immediately (before the check LLM calls) so the FE can show "found N widgets, checking…"; the placeholder cards are laid out on the subsequent **`checked`** event, which carries the `to_translate` list.

### 3.3 `check` node — three-way, LLM only where needed (reuses `judge_translation`)

Per paired widget:
- `es_html` empty → **to_translate** (deterministic)
- `es_html.strip() == en_html.strip()` → **to_translate** (English fallback, deterministic)
- else (`es` has distinct content) → `judge_translation(en_html, es_html, dealer_name)`:
  - `ok:true` (faithful) → **skipped**
  - `ok:false` (placeholder / unrelated Spanish) → **to_translate**

The judge calls for ambiguous widgets run concurrently (`asyncio.gather`). Emit a **`skipped`** event carrying the full skipped list (known before fan-out).

### 3.4 Fan-out (`Send`) → `translate_widget` branch — reuses `translate_labels_graph`

The check node returns `Send("translate_widget", {widget})` per to-translate widget — LangGraph's true map-reduce fan-out, one independently-observable branch each. `translate_widget` invokes the **existing** `translate_labels_graph` with `en_html = widget.en_html`, `dealer_name`, so the widget flows through the unchanged pipeline (glossary tool → structural validator → semantic judge → 1 retry). As each branch finishes, its result is streamed as a **`widget`** event. Order is non-deterministic; the FE keys by `window_id`.

> The per-widget "subagent" the user asked for **is** `translate_labels_graph`, reused verbatim. Retranslate-one-card stays a single `POST /translations/translate` call from the FE — no graph needed for that path.

### 3.5 Streaming transport — NDJSON over a POST (`StreamingResponse`)

The endpoint returns `text/event-stream`-style **newline-delimited JSON** via FastAPI `StreamingResponse`, driven by LangGraph `astream(stream_mode="updates")`. The FE reads it with `fetch()` + `response.body.getReader()` + `TextDecoder`, splitting on `\n`. A POST body (needed for the ~4MB of HTML) rules out `EventSource`; the fetch-ReadableStream path handles both a large request body and a streamed response. (The existing WS RPC bridge was the alternative — rejected to keep 004 in the HTTP family of 002/003.)

**Event types (one JSON object per line):**
```
{ "type": "extracted", "total": <int> }                    # widget count, before check
{ "type": "checked",   "to_translate": [ PageWidget, ... ],
                       "skipped":      [ PageWidget, ... ] }
{ "type": "widget",    "widget": { window_id, widget_type, en_html, es_html,
                                    status, warnings, raw, reasoning } }
{ "type": "done" }
{ "type": "error",     "message": <str> }        # terminal, on graph failure
```

### 3.6 Save — FE injected script (`saveWidget`), the two-save dance

Per widget on user **Save**: write Spanish, then re-write the original English. The two widget types use different endpoints, and `windowId` differs by an `-editable` suffix:

| | **Content widget** (`text-content-container`) | **RAW HTML widget** (`editable-raw-content`) |
|---|---|---|
| endpoint | `POST /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/commandExecutor/{slug}?cmd=SaveContent` | `POST /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/sites/{slug}/sitecontent?windowId={id}` |
| `windowId` | **keeps** `-editable` → `SITEBUILDER_…_1:content1-editable` | **strips** `-editable` → `SITEBUILDER_…_1:content2` |
| body | `{ javaClass:"com.dealer.composer.commands.SaveContent", siteId, windowId, currentLocale, content, accountId, userId, siteType:"primary" }` | `{ "<locale>": "<html>" }`, e.g. `{"es_US":"<p>…</p>"}` |
| needs `userId`? | **yes** (+ `accountId`=slug, `siteType:"primary"`) | no |

Save order (both types): **(1) Spanish** — content: `SaveContent currentLocale:"es_US" content:es_html`; RAW: `{"es_US":es_html}`. **(2) English** — content: `SaveContent currentLocale:"en_US" content:en_html` (original, unchanged); RAW: `{"en_US":en_html}`.

Contracts captured from `UpdateContentExample.har` (SaveContent → 200 `{contentId,…}`) and `UpdateRAWHTMLContent.har` (sitecontent → 201 `{}`). `userId` = `ccIdtToken` JWT `sub` (reuse `_extractUserId`); `siteId`/`slug` from composer hostname — same discovery as 003.

### 3.7 Skipped list & force-translate (FE)
Collapsible footer from the `skipped` event; each row shows `window_id`, `widget_type`, a preview, and **[Force translate]** which POSTs that one widget through `/translations/translate`. Same pattern as `NavTranslateTab`.

---

## 4. Data model

### 4.1 BE DTOs & graph state

```python
# translations_dtos.py (new)
from enum import Enum

class WidgetType(str, Enum):
    CONTENT = "content"
    RAW = "raw"

class PageWidget(BaseModel):
    window_id: str          # raw div id, WITH -editable suffix
    widget_type: WidgetType
    en_html: str            # inner HTML of en_US widget
    es_html: str            # inner HTML of es_US widget ("" if absent)

class TranslatePageRequest(BaseModel):
    en_page_html: str
    es_page_html: str
    dealer_name: str
    provider: LLMProvider = LLMProvider.ANTHROPIC

# Streaming events are emitted as raw JSON lines (see §3.5), not a single response_model.
```

```python
# application/translate_pages/state.py (new)
class PageTranslateState(TypedDict, total=False):
    en_page_html: str
    es_page_html: str
    dealer_name: str
    to_translate: list[dict]      # PageWidget-shaped, drives Send fan-out
    skipped: list[dict]
    results: Annotated[list[dict], operator.add]   # fan-in accumulator
```

The per-widget branch reuses `TranslateLabelState` (unchanged) inside `translate_labels_graph`.

### 4.2 FE types (`types/index.ts` — new)

```ts
type WidgetType = "content" | "raw"
interface PageWidget { window_id: string; widget_type: WidgetType; en_html: string; es_html: string }
interface TranslatePageRequest { en_page_html: string; es_page_html: string; dealer_name: string; provider: LLMProvider }
interface PageLoadResult { html: string | null; error?: string }

type PageStreamEvent =
  | { type: "extracted"; to_translate: number; total: number }
  | { type: "skipped"; widgets: PageWidget[] }
  | { type: "widget"; widget: PageWidgetResult }
  | { type: "done" }
  | { type: "error"; message: string }
```

### 4.3 FE store types (`store/types.ts` — new)

```ts
type WidgetRowStatus = "queued" | "translating" | "ready" | "error" | "saved" | "skipped"
interface SpanishWidgetRow {
  windowId: string; widgetType: WidgetType; status: WidgetRowStatus
  enHtml: string; esHtml: string
  warnings: string[]; raw: string | null; error: string | null; reasoning: string
}
```
`SpanishMigrationProject` gains an optional `pages` map (`targetPath → SpanishWidgetRow[]`); `labels` untouched. Final shape settled in the plan.

---

## 5. Frontend workflow

### 5.1 PageTranslateTab (new organism, 3rd Spanish tab)
`ProjectPage.tsx` Spanish branch: `[Simple Labels] [Translate Nav] [Translate Page]`.

### 5.2 Flow
1. Target-path input + **Load Page Widgets**.
2. `Promise.all([loadPage(path,"en_US"), loadPage(path,"es_US")])`.
3. Open the NDJSON stream `POST /translations/translate-page`.
4. On `extracted` → show "found N widgets, checking…". On `checked` → lay out placeholder cards (from `to_translate`) in `translating` state + counters, and fill the skipped footer. On each `widget` → resolve that card (match by `window_id`). On `done` → finalize.
5. **WidgetRow** review card — EN preview (collapsible), ES editor, `widget_type` badge, warnings, reasoning, save/skip/retranslate.
6. Save via `saveWidget` (two-save); retranslate via `/translations/translate`; force-translate from footer.

### 5.3 PagePort (new)
```ts
export interface PagePort {
  loadPage(targetPath: string, locale: "en_US" | "es_US"): Promise<PageLoadResult>
  translatePageStream(req: TranslatePageRequest, onEvent: (e: PageStreamEvent) => void, signal?: AbortSignal): Promise<void>
  saveWidget(w: { windowId: string; widgetType: WidgetType; enHtml: string; esHtml: string }): Promise<{ success: boolean; error?: string }>
}
```
Single-widget retranslate reuses `LabelPort.translateLabel`.

### 5.4 PageAdapter (new)
`translatePageStream` = `fetch` POST + `response.body.getReader()` + `TextDecoder`, buffering and splitting on `\n`, `JSON.parse` each line → `onEvent`. Injected scripts `loadPageInjected(slug, path, locale)` and `saveWidgetInjected(...)` (two-save, `-editable` suffix rule). Reuses `findComposerTabId`/`_extractUserId` extracted to a shared `ddcTab.ts`.

---

## 6. Key design decisions

1. **A graph is warranted here (reversing the 002/003 default).** The LLM checker (placeholder-vs-real-translation) plus the parallel fan-out + streamed batch review are genuine multi-step LLM/map-reduce work — not a plain loop. See §2.
2. **Reuse, don't rebuild:** the per-widget "subagent" is `translate_labels_graph` invoked per `Send` branch; the checker is the existing `judge_translation`. Zero new translate/judge logic.
3. **Graph stays browser-free.** Like every graph in this repo, it computes over state passed in. The FE performs all DDC render GETs and save POSTs. No WS-RPC tool-nodes — the FE fetches both renders in parallel and hands them in.
4. **Extraction on the BE (BeautifulSoup).** Reuses the specialist's `extract_main_content` logic, unit-testable, consistent with parsing living in Python. Cost: adds `beautifulsoup4`+`lxml`; ships two multi-MB blobs to localhost.
5. **True `Send` fan-out + NDJSON streaming.** One observable branch per widget; results stream as each lands so the user sees a live-filling board rather than one long spinner. Streaming rides a `StreamingResponse` NDJSON over POST (not the WS bridge), keeping 004 in the HTTP family.
6. **Two-save dance replicated faithfully**, encapsulated in one `saveWidget` so callers can't forget the English re-save. English content unchanged.
7. **`-editable` suffix asymmetry is load-bearing** — content saves keep it in `windowId`; RAW saves strip it. Enforced in one place; covered by a fixture test.
8. **Deterministic-first detection.** LLM (judge) fires only on widgets whose `es` is non-empty and `!= en`. Empty / fallback cases skip the LLM. Force-translate covers false negatives.

---

## 7. File reference (complete map)

### BE — New
| File | What it does |
|------|-------------|
| `src/application/translate_pages/widget_extract.py` | Pure `extract_widgets(en_html, es_html)` → paired, typed widgets (bs4). Application layer, not domain (constitution: no external imports in domain). |
| `src/application/translate_pages/state.py` | `PageTranslateState` TypedDict (fan-in accumulator) |
| `src/application/translate_pages/extract_node.py` | Node wrapping `widget_extract` + emits `extracted` |
| `src/application/translate_pages/check_node.py` | Three-way check; `judge_translation` on ambiguous widgets (concurrent) |
| `src/application/translate_pages/routing.py` | Pure `route_to_widget_branches(state) → list[Send]` fan-out (I/O stays in the check node) |
| `src/application/translate_pages/translate_widget_node.py` | Invokes `translate_labels_graph` for one widget |
| `src/application/translate_pages/translate_page_graph.py` | `build_translate_page_graph(llm)` — extract → check → Send → translate_widget → END |
| `src/adapters/inbound/http/translations_router.py` | Add `POST /translations/translate-page` (`StreamingResponse`, NDJSON) |
| `src/adapters/inbound/http/translations_dtos.py` | `WidgetType`, `PageWidget`, `TranslatePageRequest` |
| `pyproject.toml` / `requirements.txt` | Add `beautifulsoup4`, `lxml` |
| `tests/test_widget_extract.py` | Extraction, pairing, `-editable`, inner-HTML round-trip |
| `tests/test_translate_page_graph.py` | Check three-way logic, fan-out count, event sequence (mock LLM) |

### BE — Reused (unchanged)
`translate_labels_graph.py`, `translate_label_node.py`, `validator.py`, `glossary_*`, `prompts.py` + provider adapters (incl. `judge_translation`).

### FE — New
| File | What it does |
|------|-------------|
| `src/services/ports/PagePort.ts` | `loadPage`, `translatePageStream`, `saveWidget` |
| `src/services/adapters/PageAdapter.ts` | Injected `loadPageInjected` + `saveWidgetInjected` (two-save); NDJSON stream reader |
| `src/services/adapters/ddcTab.ts` | Shared `findComposerTabId` + `_extractUserId` (extracted from `LabelAdapter`) |
| `src/types/index.ts` | Page types + `PageStreamEvent` union |
| `src/store/types.ts` | `WidgetRowStatus`, `SpanishWidgetRow`, `pages` on project |
| `src/components/organisms/PageTranslateTab/PageTranslateTab.tsx` | Path input → load → stream → progressive review board |
| `src/components/molecules/WidgetRow/WidgetRow.tsx` | Per-widget card (if `LabelRow` reuse proves insufficient) |

### FE — Modified
`ProjectPage.tsx` (3rd tab), `LabelAdapter.ts` (import shared `ddcTab.ts`), `useMigrationStore.ts` (`pages` actions).

---

## 8. Risks & open questions

- **8.1 Widget size vs. LLM/validator limits.** RAW widgets can be large; a single translate call may hit token limits or noisy structural warnings. Measure first; consider a content-tuned prompt or chunking later. Not blocking v1.
- **8.2 `div.main` assumption.** Templates without it yield nothing → clean "no editable content" message; log for template analysis; consider fallback selectors.
- **8.3 Inner-HTML fidelity.** bs4 re-serialization can normalize quotes/entities; use `decode_contents()` and a round-trip fixture. The translate validator also guards drift.
- **8.4 Check-node latency / cost.** Many ambiguous widgets ⇒ many judge calls before fan-out. They run concurrently; cap concurrency. Emit `extracted` before the checks so the UI isn't blank while checking.
- **8.5 `Send` is new to this repo.** No existing fan-out precedent; the `translate_labels_graph`-as-subroutine + `Annotated[list, operator.add]` accumulator pattern needs a focused test.
- **8.6 Streaming plumbing.** NDJSON-over-POST + fetch-ReadableStream is new to the FE; needs an abort path and partial-line buffering. Errors mid-stream arrive as an `error` event, not an HTTP status.
- **8.7 `siteType`/`accountId` beyond "primary".** SaveContent hardcodes `siteType:"primary"`, `accountId==siteId`; parameterize if a secondary-site dealer appears.
- **8.8 Multi-page store shape.** `pages` keyed-by-path needs persistence + a page switcher; v1 may scope to one page at a time.
