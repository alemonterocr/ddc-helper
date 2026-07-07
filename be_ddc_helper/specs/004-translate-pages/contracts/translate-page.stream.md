# Contract: `POST /translations/translate-page`

Streaming NDJSON endpoint. Extracts a page's editable widgets, decides which need translation, fans out per-widget translation, and streams results as they complete.

---

## Request

```
POST /translations/translate-page
Content-Type: application/json
```

```json
{
  "en_page_html": "<html>… full en_US render …</html>",
  "es_page_html": "<html>… full es_US render …</html>",
  "dealer_name": "Go Hyundai Renton",
  "provider": "anthropic"
}
```

- `en_page_html` / `es_page_html` — the raw HTML the FE fetched from the DDC render endpoint (see [ddc-endpoints.md](./ddc-endpoints.md)), one per locale. Up to ~2 MB each.
- `dealer_name` — passed to the translator so brand/model names are preserved.
- `provider` — `anthropic` | `gemini` | `deepseek`; defaults to `anthropic`. The API key must already be configured via the existing `configureApiKey` flow.

## Response

```
200 OK
Content-Type: application/x-ndjson
Transfer-Encoding: chunked
```

Body: newline-delimited JSON, **one event object per line**, streamed as work completes.

### Event sequence

1. `extracted` — emitted once, right after bs4 extraction (before the check LLM
   calls). `total` = number of editable widgets found on the page. Lets the FE
   show "Found N widgets, checking…" instantly:
   ```json
   { "type": "extracted", "total": 9 }
   ```
2. `checked` — emitted once, after the check step. Carries both classified lists
   (each a `PageWidget`). The FE lays out placeholder cards from `to_translate`
   and fills the skipped footer from `skipped`:
   ```json
   { "type": "checked",
     "to_translate": [
       { "window_id": "SITEBUILDER_…:content2-editable", "widget_type": "raw",
         "en_html": "<p>This is a RAW HTML content</p>", "es_html": "" }
     ],
     "skipped": [
       { "window_id": "SITEBUILDER_…:content5-editable", "widget_type": "content",
         "en_html": "<p>…</p>", "es_html": "<p>…ya traducido…</p>" }
     ] }
   ```
3. `widget` — emitted once per to-translate widget, in **completion order** (non-deterministic):
   ```json
   { "type": "widget", "widget": {
     "window_id": "SITEBUILDER_…:content2-editable", "widget_type": "raw",
     "en_html": "<p>This is a RAW HTML content</p>",
     "es_html": "<p>Este es un contenido HTML sin formato</p>",
     "status": "ready", "warnings": [], "raw": null,
     "reasoning": "Direct rendering; preserved the <p> wrapper." } }
   ```
4. Terminal — exactly one of:
   ```json
   { "type": "done" }
   { "type": "error", "message": "…" }
   ```

### Semantics

- **Ordering**: `extracted` → `checked` → `widget`×N → (`done` | `error`). Clients key widgets by `window_id`; do not rely on `widget` order.
- **Empty page**: if no `div.main` or no editable widgets, `extracted` reports `total:0`, `checked` has empty `to_translate`/`skipped`, then `done`. The FE shows "no editable content found on this page".
- **Failure mid-stream**: any exception in extraction/check/translation yields a terminal `error` event (HTTP status is already 200 by then). `judge_translation` failures do not abort — they fail open (widget treated as needing translation / passing, per existing behavior).
- **Abort**: the client may cancel via `AbortController`; the server stops streaming when the connection drops.
- **`status`**: `ready` (passed structural + semantic checks) or `error` (needs review; `raw` holds the unvalidated output for hand-editing) — identical semantics to `/translations/translate`.

## Reuse

- Per-widget translation is the existing `translate_labels_graph` (glossary tool → structural validator → semantic judge → 1 retry), invoked once per `Send` branch.
- The check step reuses `LLMPort.judge_translation`.
- No change to `/translations/translate`; single-widget **retranslate** and **force-translate** call that existing endpoint.
