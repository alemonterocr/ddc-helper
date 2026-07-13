---
name: translate_pages
type: graph
status: built
layer: application
---

# `application/translate_pages/`

Streaming fan-out graph that translates a DDC page's editable widgets EN→es_US.
Feature spec: `specs/004-translate-pages/spec.md`.

## Purpose

Given both locale renders of a page (fetched by the FE), extract the editable
content + RAW-HTML widgets, decide which still need translation (LLM-assisted),
fan out one translation per widget, and stream results back as they complete.

## Inputs

`PageTranslateState`:
- `en_page_html`, `es_page_html` — full rendered page HTML per locale.
- `dealer_name` — so brand/model names stay untranslated.
- `provider` — LLM provider id.

## Outputs

Streamed NDJSON events (see `contracts/translate-page.stream.md`):
`extracted` → `skipped` → `widget` × N → `done` | `error`.

## Flow

```
extract_widgets → check → route_to_widget_branches (Send) → translate_widget → END
```

- `widget_extract.py` — pure bs4 extraction (application layer, NOT domain: the
  constitution forbids external imports in `domain/`).
- `extract_node.py` — wraps extraction → `candidates`.
- `check_node.py` — three-way classify; `judge_translation` on ambiguous widgets
  (concurrent, semaphore).
- `routing.py` — pure `route_to_widget_branches(state) → list[Send]` fan-out.
- `html_translate.py` — `translate_widget_html(html, translate_batch)`: extract
  text nodes (bs4) → batch translate → reinsert into untouched markup.
- `translate_widget_node.py` — translates one widget's text nodes via
  `html_translate` + `LLMPort.translate_text_segments`.
- `translate_page_graph.py` — graph wiring.

## Contracts

- Per-widget translation sends only **text nodes** to the LLM
  (`translate_text_segments`), never markup — robust to widget size, structurally
  exact. It does NOT reuse `translate_labels_graph` (that truncated large widgets
  to empty; see feature spec §3.4).
- The checker reuses `LLMPort.judge_translation`.
- The graph never touches DDC — the FE performs all render GETs and save POSTs.

## Dependencies

- `LLMPort` (ports/outbound, incl. `translate_text_segments` + `judge_translation`),
  `translate_labels/validator` (defensive check), `beautifulsoup4`/`lxml`.
