# Research: Translate Page Widgets

Phase 0 — resolving the unknowns flagged in the plan's Technical Context. Each item: **Decision / Rationale / Alternatives**.

---

## R1. Fan-out with LangGraph `Send` + fan-in accumulator

**Decision.** The `check_translations_node` computes `state.to_translate`; a **pure routing function** `route_to_widget_branches(state) -> list[Send]` returns one `Send("translate_widget", {"widget": w, "dealer_name": ..., "provider": ...})` per widget. `translate_widget_node` invokes the existing `translate_labels_graph` for its single widget and returns `{"results": [one_result]}`. Fan-in accumulates via `results: Annotated[list[dict], operator.add]` on the state.

**Rationale.** Matches LangGraph's canonical map-reduce. Keeping the `Send` list in a routing function (not the node) satisfies the constitution: *side effects only in nodes, routing pure*. The `operator.add` reducer is the standard concurrent-safe accumulator for parallel branches writing the same key.

**Alternatives.** (a) `asyncio.gather` inside one node — simpler but not true per-branch observability, and the user explicitly chose `Send`. (b) Returning `Send` from the check node itself — rejected: the node does LLM I/O, and mixing I/O with routing violates the routing-purity rule.

---

## R2. Streaming graph output → FastAPI response

**Decision.** Run `graph.astream(initial_state, stream_mode="updates")` inside an async generator; translate each node update into a stream event and `yield` it as one JSON line + `\n`. Return via `fastapi.responses.StreamingResponse(gen, media_type="application/x-ndjson")`. Emit `extracted` after `extract_node`, `skipped` after `check_node`, one `widget` per `translate_widget` update, then a terminal `done`. Wrap the generator body so any exception yields a terminal `{"type":"error","message":...}` line instead of a broken stream.

**Rationale.** `stream_mode="updates"` yields `{node_name: partial_state}` after each node/branch completes — exactly the granularity needed to forward per-widget results as they land. NDJSON is trivial to parse incrementally on the client and sidesteps SSE's GET-only `EventSource` limitation (we need a multi-MB POST body).

**Alternatives.** (a) SSE via `EventSource` — can't POST a large body. (b) `stream_mode="values"` — emits full state each step; wasteful for large HTML in state. (c) WS RPC bridge — reserved for the execute pipeline; too heavy and off-pattern for the translation family.

**Note.** Keep the two raw page-HTML blobs out of any streamed payload (they're multi-MB); stream only widget-sized fields.

---

## R3. Consuming NDJSON on the MV3 frontend

**Decision.** `PageAdapter.translatePageStream` does `fetch(url, {method:"POST", body, signal})`, then reads `res.body.getReader()` with a `TextDecoder`, buffering across chunks and splitting on `\n`. Each complete line → `JSON.parse` → `onEvent`. A trailing partial line is retained in the buffer until the next chunk. An `AbortSignal` cancels the stream (user leaves the tab / starts a new page).

**Rationale.** `fetch` + `ReadableStream` is supported in MV3 extension pages/service workers and handles request-body + streamed-response in one call. Manual line buffering is required because chunk boundaries don't align to lines.

**Alternatives.** `@microsoft/fetch-event-source` — adds a dependency for SSE semantics we don't need with NDJSON. Rejected.

---

## R4. BeautifulSoup inner-HTML fidelity

**Decision.** Parse each render with `BeautifulSoup(html, "lxml")`, locate `soup.find("div", class_="main")`, then for each widget `div` extract **inner** HTML via `widget.decode_contents()`. Classify by class list membership: `text-content-container` → content, `editable-raw-content` → raw. The widget `id` (e.g. `SITEBUILDER_ALE_MONTERO_1:content1-editable`) is the pairing key and the save `windowId`.

**Rationale.** `decode_contents()` returns the children markup without the wrapper div — the exact string DDC's save endpoints expect. `lxml` matches the specialist's original `extract_main_content` and is lenient on real-world dealer HTML.

**Risk / mitigation.** bs4 may normalize quotes/entities on re-serialization. Mitigated by (a) a round-trip fixture test asserting stability on representative widget HTML, and (b) the downstream structural validator in `translate_labels` which guards tag/href/variable drift. If normalization proves lossy, fall back to slicing the original HTML between the widget's start/end tags by id.

**Alternatives.** `str(widget)` (includes the wrapper div — wrong for save body); regex extraction (fragile on nested markup); FE `DOMParser` (rejected earlier — keeps parsing untestable in Python).

---

## R5. Detecting "already translated" vs DDC Spanish placeholder

**Decision.** Three-way, deterministic-first: `es` empty ⇒ translate; `es.strip()==en.strip()` ⇒ translate (English fallback); else call `judge_translation(en, es, dealer_name)` and skip only when `ok:true`. Ambiguous-widget judge calls run concurrently under a semaphore (default 5).

**Rationale.** DDC injects non-empty Spanish lorem-ipsum that no regex distinguishes from a real translation; `judge_translation` already answers "does `es` faithfully render `en`?". Spending an LLM call only on the ambiguous subset keeps cost proportional to real uncertainty.

**Alternatives.** Pure-regex skip (002/003 style) — rejected: misclassifies placeholder text. A bespoke checker prompt — rejected: duplicates `judge_translation`.

---

## R6. New dependencies

**Decision.** Add `beautifulsoup4` and `lxml` to `pyproject.toml` + `requirements.txt`. Confirmed absent today. No new FE dependency — streaming uses native `fetch`.

**Rationale.** Minimal surface; both are mature, widely used, and already the specialist's chosen parser.

---

## Open items carried to risks (not blocking Phase 1)

- Very large RAW widgets vs. single-call token limits → measure; chunk later (spec §8.1).
- `siteType`/`accountId` beyond `"primary"` (spec §8.7).
- Multi-page store shape / page switcher (spec §8.8).
