# Data Model: Translate Page Widgets

Entities, graph state, and stream events. BE types are Python (Pydantic/TypedDict); FE types are TypeScript. Field-level contracts here; wire framing in [contracts/translate-page.stream.md](./contracts/translate-page.stream.md).

---

## 1. Widget (core entity)

A single editable region on a DDC page, present in both locales, paired by `window_id`.

| Field | Type | Notes |
|-------|------|-------|
| `window_id` | str | Raw div id, e.g. `SITEBUILDER_ALE_MONTERO_1:content1-editable`. Pairing key + save `windowId` (see suffix rule below). |
| `widget_type` | `"content" \| "raw"` | `text-content-container` → content; `editable-raw-content` → raw. |
| `en_html` | str | Inner HTML of the en_US widget (`decode_contents()`). Translation source + English re-save payload. |
| `es_html` | str | Inner HTML of the es_US widget; `""` when the id is absent in the es render. |

**`-editable` suffix rule (save time):** content saves keep the suffix in `windowId`; raw saves strip it (`…:content1-editable` → `…:content1`... for raw only). Extraction always stores the raw id **with** the suffix; stripping happens in the FE save script.

**Classification (populated by the check step, not stored on the widget):**
- `es_html` empty **OR** `es_html.strip() == en_html.strip()` → **to_translate** (deterministic)
- else → `judge_translation(en, es)`: `ok` → **skipped**; not `ok` → **to_translate**

---

## 2. BE DTOs (`adapters/inbound/http/translations_dtos.py`, new)

```python
from enum import Enum
from pydantic import BaseModel
from src.domain.models import LLMProvider

class WidgetType(str, Enum):
    CONTENT = "content"
    RAW = "raw"

class PageWidget(BaseModel):
    window_id: str
    widget_type: WidgetType
    en_html: str
    es_html: str

class TranslatePageRequest(BaseModel):
    en_page_html: str          # full en_US render (~0.5–2 MB)
    es_page_html: str          # full es_US render
    dealer_name: str           # so brand/model names stay untranslated
    provider: LLMProvider = LLMProvider.ANTHROPIC
```

Stream events are emitted as raw NDJSON lines (no single `response_model`).

---

## 3. Graph state (`application/translate_pages/state.py`, new)

```python
import operator
from typing import Annotated, TypedDict

class PageTranslateState(TypedDict, total=False):
    # inputs
    en_page_html: str
    es_page_html: str
    dealer_name: str
    provider: str
    # produced by extract_node
    candidates: list[dict]        # all paired widgets (PageWidget-shaped dicts)
    # produced by check_node
    to_translate: list[dict]      # drives the Send fan-out
    skipped: list[dict]
    # fan-in accumulator (parallel-safe)
    results: Annotated[list[dict], operator.add]
```

Each `translate_widget_node` translates the widget's text nodes (`html_translate` + `LLMPort.translate_text_segments`) and returns `{"results": [widget_result]}`. (It does not run the label graph — see spec §3.4.)

**`widget_result` shape** (what a branch appends; becomes a `widget` event):
```
{ window_id, widget_type, en_html, es_html, status, warnings, raw, reasoning }
```
where `es_html` is the widget's HTML with its text nodes translated; `status` is `ready` (or `error` if the translator returned a mismatched segment count); `warnings` are any residual structural-validator notes; `reasoning` records the segment count.

---

## 4. Stream events (NDJSON, one JSON object per line)

```
{ "type": "extracted", "total": <int> }                    # widget count, before check
{ "type": "checked",   "to_translate": [ PageWidget, ... ],
                       "skipped":      [ PageWidget, ... ] }
{ "type": "widget",    "widget": { window_id, widget_type, en_html, es_html,
                                    status, warnings, raw, reasoning } }
{ "type": "done" }
{ "type": "error",     "message": <str> }     # terminal; replaces done on failure
```

Ordering: `extracted` first, then `checked`, then `widget` × N in completion order (non-deterministic — FE keys by `window_id`), then exactly one terminal `done` **or** `error`.

---

## 5. FE types (`fe_ddc_helper/src/types/index.ts`, new)

```ts
type WidgetType = "content" | "raw"

interface PageWidget { window_id: string; widget_type: WidgetType; en_html: string; es_html: string }

interface PageWidgetResult extends PageWidget {
  status: "ready" | "error"
  warnings: string[]
  raw: string | null
  reasoning: string
}

interface TranslatePageRequest {
  en_page_html: string; es_page_html: string
  dealer_name: string; provider: LLMProvider
}

interface PageLoadResult { html: string | null; error?: string }

type PageStreamEvent =
  | { type: "extracted"; total: number }
  | { type: "checked"; to_translate: PageWidget[]; skipped: PageWidget[] }
  | { type: "widget"; widget: PageWidgetResult }
  | { type: "done" }
  | { type: "error"; message: string }
```

---

## 6. FE store types (`fe_ddc_helper/src/store/types.ts`, new)

```ts
type WidgetRowStatus =
  | "queued"       // placeholder card shown after `extracted`
  | "translating"  // awaiting its `widget` event
  | "ready"        // translated, awaiting save
  | "error"        // translation failed validation/judge
  | "saved"        // two-save completed
  | "skipped"      // user skipped (or force-translate source)

interface SpanishWidgetRow {
  windowId: string
  widgetType: WidgetType
  status: WidgetRowStatus
  enHtml: string            // original English — re-saved verbatim
  esHtml: string            // model output, user-editable
  warnings: string[]
  raw: string | null
  error: string | null
  reasoning: string
}
```

`SpanishMigrationProject` gains `pageWidgets: SpanishWidgetRow[]` + `pageTargetPath?: string` — **v1 holds one page at a time** (spec §8.8), which is simpler than a per-path map and sufficient for the workflow. The existing `labels` array is untouched. (A `Record<string, SpanishWidgetRow[]>` keyed by path is the future multi-page shape.)

---

## 7. Relationships

```
TranslatePageRequest ──(extract_node: bs4)──► candidates: PageWidget[]
candidates ──(check_node: judge on ambiguous)──► to_translate[] + skipped[]
to_translate[] ──(route_to_widget_branches: Send)──► translate_widget_node × N
translate_widget_node ──(text-node translate: translate_text_segments)──► results[] (widget events)
skipped[] ──────────────────────────────────────────────► FE skipped footer (force-translate)
```
