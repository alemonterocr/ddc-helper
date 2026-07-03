---
name: migration-pipeline
type: use-case
status: built
layer: application
---

## Purpose

LangGraph pipeline for the deterministic+LLM hybrid migration. The
deterministic algorithm lives in `domain/migration/{_atoms,chrome,tree_cleanup,
buttons,chunking,discovery}.py` (with a re-export shim at
`domain/deterministic_migrate.py` for backward-compatible imports) and is the
engine; this graph wires it together with two LLM review steps and exposes
the run as a state machine.

Structural decisions stay in the geometry analyzer. The LLM is never asked
to pick a layout — it only decides what to KEEP/DROP (`chrome_review`) and
enriches HTML and intent strings (`enrich`).

`analyze_router.py` is a thin caller: it derives page metadata, builds
initial state, invokes the graph, returns the response.

## Pipeline

```
prune → chrome_review → build → typify → image_split → convert → enrich → END
```

- **prune** — calls `strip_chrome`. Hard-drops `<header>`/`<footer>`/`<nav>`/
  `<aside>` and widget-chrome subtrees (e.g. Wistia `w-chrome` player UI).
  Flags `_chrome_candidate: True` on (a) class-word matches with no content
  anchor and (b) Bootstrap columns ≤4 sitting next to a sibling ≥8
  (geometry-driven; bypasses the content-anchor rescue since sidebars
  commonly hold lead-gen forms).
- **chrome_review** — single batched LLM call via
  `LLMPort.classify_chrome_batch` for all candidates collected from the tree.
  KEEP clears the flag; DROP removes the subtree. On parse/transport
  failure, defaults to all-KEEP (safer to over-include).
- **build** — `discover_sections` + `editorial_chunk`. The deterministic
  core. The Bootstrap classifier snaps near-9/3 layouts to `empty-66-33` /
  `empty-33-66` so KEEP-verdict sidebars become real two-column sections
  rather than collapsing to `empty-one`.
- **typify** — single batched LLM call via `LLMPort.classify_widget_type`
  for content widgets that have structural signals beyond plain text
  (form tag, day/time text, phone/email/address, structured tables,
  tab/accordion shapes, engineered class markup). The LLM returns one of
  `form` / `contact_info` / `hours` / `content` / `drop` per candidate.
  Replaces matched widgets with marker widgets (no payload — execute layer
  reads dealer master-record data from DDC). Bounded 5-class is allowed
  here because the signal anchor in widget HTML is concrete (text patterns,
  semantic tags) — unlike layout classification which the LLM could not do
  reliably. Feature-gated (`typify_enabled`, default on); all-`content`
  fallback on LLM failure.
- **image_split** — single batched LLM call via
  `LLMPort.classify_image_splits` for content widgets that still contain
  embedded `<img>` tags after editorial chunking. Per-image yes/no:
  promote to a standalone image widget or keep inline. Slices the HTML
  deterministically around promoted images, cleans up orphan tag halves,
  drops empty content slices. Feature-gated (`image_split_enabled`, default
  on). On LLM failure, no-ops — preserves prior widget structure.
- **convert** — translates `det_plan` to `section_plan` ColumnWidget shape
  and trims slot counts to the catalog. Intentionally LLM-free: an earlier
  design had an LLM fallback here for ambiguous `empty-one` sections; it was
  deleted because letting the LLM pick layouts contradicted the architecture
  and produced unreliable structural output in testing.
- **enrich** — batched LLM call for HTML beautify + intent copywriting via
  `LLMPort.enrich_content`. Feature-gated (`enrich_enabled`, default on).
  Renumbers positions at the end.

## Architectural principle: LLM-gated uncertainty, bounded by signal anchor

`chrome_review`, `typify`, and `image_split` follow the same pattern: the
deterministic layer flags candidates whose treatment is uncertain, and a
batched LLM call resolves them with a small, bounded verdict set.

- `chrome_review` and `image_split` are **binary** (KEEP/DROP, promote/keep)
- `typify` is **bounded 5-class** (form/contact_info/hours/content/drop)

The principle isn't strictly "binary only" — it's "the LLM can only choose
from a small bounded set, and only when there's a concrete signal in the
input it can anchor its decision on." Chrome KEEP/DROP anchors on actual
HTML content. Image promote/keep anchors on the surrounding markup. Widget
typing anchors on textual patterns (form tag, day/time text, phone regex).

What the LLM is NOT trusted to do — and what `reclassify` was deleted for —
is pick from N abstract options without a concrete signal anchor. Choosing
"which of 5 DDC layouts best fits these geometric ratios" gave the LLM
nothing to read off the HTML; widget typing reads the HTML directly.

Future LLM gates on uncertain deterministic decisions should follow the
same shape: clear deterministic trigger, small bounded output set, concrete
signal anchor in the input, all-safe fallback on failure.

No `verify` node. Not in scope — neither now nor as a planned followup.

## Inputs / Outputs

- Input: `MigrationState` with `dom_skeleton` and identity fields populated.
- Output: `MigrationState` with `pruned_tree`, `det_plan`, `section_plan`.

## Contracts

- Nodes do not import FastAPI directly.
- LLM calls go through `LLMPort`.
- The deterministic algo is the engine; nodes are thin orchestrators that
  call into `domain/migration/*` (via the `deterministic_migrate` shim's
  re-exported `migrate`, `strip_chrome`, `discover_sections`, `editorial_chunk`,
  `render_html`) rather than reimplementing logic.
- The graph factory rebuilds per request and takes runtime deps (llm,
  catalog, progress callback, feature flag). Keeps `MigrationState` free of
  callables and per-request configuration.
