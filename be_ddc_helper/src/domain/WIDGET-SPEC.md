# DDC Migration — Widget Extension Spec

This document lives next to the deterministic migration algorithm — split as of 2026-07-01 into `src/domain/migration/{_atoms,chrome,tree_cleanup,buttons,chunking,discovery}.py`, with a re-export shim at `src/domain/deterministic_migrate.py`. It captures the
current state of the deterministic migration algorithm and the immediate
roadmap for extending it beyond the two-widget POC (content + image) toward
the full DDC widget catalog. It is written for an LLM picking up this
codebase cold, with no prior conversation context.

---

## 1. Project context

We're migrating dealership pages from arbitrary source CMSs (DealerOn,
DealerInspire, Overfuel, WordPress, etc.) into DDC (Dealer.com), a closed
proprietary CMS with no public API. A Chrome extension captures the source
page DOM into a structured skeleton; a FastAPI backend analyzes the skeleton
to produce a migration plan; an execution layer injects DDC sections and
widgets via JavaScript injected into an authenticated DDC tab over WebSocket.

This document concerns the **analysis layer**. `migrate.py` is the
deterministic backbone of that layer; this spec covers how to extend it.

---

## 2. Current state

### What works

- **Section discovery**: `discover_sections()` recursively walks the source
  DOM, groups siblings into rows by y-overlap (using `getBoundingClientRect`
  data captured by the extractor), and classifies multi-column rows into one
  of the DDC layouts via width ratios. Falls back to Bootstrap `col-*` class
  detection when geometry is absent. Validated on three pages:
  - DDC reference page (Buddy Chevy, Decatur): 4 sections detected correctly
  - Mazda blog (single-column article): 2 sections, h1 separated from body
  - Mazda Food Bank page (the hard case with nested 66/33): 3 sections,
    including the geometry-recovered `empty-66-33` that the previous
    LLM-only approach collapsed entirely

- **Editorial chunking**: `editorial_chunk()` splits each section slot into
  widgets at heading and standalone-image boundaries, with smart split-level
  detection (uses the smallest heading level present in the slot, ignoring
  h1, so an h2-led article doesn't get over-fragmented by h3 subsections).

- **Output**: list of `(layout, slot_nodes)` tuples per page. Each slot
  produces a list of widgets, currently of type `content` or `image`.
  Internal `_slot_nodes` field preserves raw DOM nodes for LLM fallback.

### What's currently supported in the section catalog

```
empty-one             # 1 slot, full width
empty-fifty-fifty     # 2 slots, equal
empty-66-33           # 2 slots, 66/33
empty-33-66           # 2 slots, 33/66
empty-fifths          # 5 slots, equal
```

### What's currently supported in the widget catalog

```
content  # HTML chunk (editable by dealer in DDC)
image    # URL reference (uploaded to DDC media library at execution time)
```

### Known gaps surfaced by validation

- **Image URL resolution**: `img.custom-image-blogs` on Mazda pages still
  resolves to no URL. The extractor's lazy-load attribute fallback chain
  (`src`, `data-src`, `data-lazy-src`, `srcset`, `<picture> source[srcset]`)
  doesn't cover whatever Mazda's CMS uses. Open: identify the attribute by
  inspecting raw HTML on one of those `<img>` tags, add to extractor.
- **Editorial-vs-structural image distinction**: an inline editorial image
  inside a content block (e.g. the Food Bank page's donate photo) currently
  gets emitted as a separate image widget, breaking the prose flow. Should
  be inline. Fix: classifier that uses `w/parent.w > 0.8` AND `no text
within ~40px above/below` to flag as structural; otherwise inline.

These gaps are in the queue but not blocking widget expansion.

---

## 3. Architecture: principles that should not be relitigated

These design decisions were made deliberately, validated against real pages,
and are not up for debate without strong reason:

### 3.1. Three concerns, three layers

The original LLM-based approach failed because one prompt was asked to do all
three of these at once:

1. **Segmentation** — where do section boundaries belong?
2. **Classification** — which DDC layout matches each section?
3. **Extraction** — what content/widget goes in each slot?

Each is now its own pass:

- Segmentation: `group_into_rows()` in migrate.py
- Layout classification: `classify_columns_by_geometry()` (geometric) with
  `classify_columns_by_bootstrap()` as fallback
- Extraction: `editorial_chunk()` per slot

Adding a new widget type extends the **extraction** layer (classification at
the widget granularity). It does NOT touch segmentation or layout
classification.

### 3.2. Deterministic first, LLM as fallback (not primary)

The migrate.py pipeline produces a complete migration plan with zero LLM
tokens. Where the deterministic classifier returns ambiguous output (low
confidence, unrecognized pattern), the analyze endpoint should escalate that
specific slot/widget to the LLM, using `_slot_nodes` to feed the raw DOM
back. The LLM never sees the whole page; it sees the specific subtree the
deterministic algorithm couldn't classify, with a narrow prompt.

This architecture matters because:

- Cost: deterministic is free, LLM is metered per token
- Determinism: same input → same output, debuggable, testable
- Latency: deterministic returns in milliseconds, LLM in seconds
- Auditability: when output is wrong, it's wrong in a predictable place

Adding widget types must preserve this property: classifier first, LLM
fallback for the residual.

### 3.3. Multi-signal scoring, not single-attribute detection

Every classifier in this codebase combines several weak signals into a score
rather than relying on a single strong signal. This is non-negotiable for
cross-platform robustness.

Example: chrome detection uses tag AND class-word match AND restricts class
matching to container tags (with headings exempt). Layout classification
uses geometric width ratios AND Bootstrap class fallback. Editorial chunking
uses heading-level analysis AND structural signals (standalone images, hr).

When adding a widget classifier (see Section 5), do NOT rely on:

- A single class-name match (every CMS uses different classes)
- A single tag match (`<a>` is used for both buttons and inline links)
- A single style property
- A single text pattern

Always stack ≥3 signals. Require ≥3 hits for positive classification. Tune
threshold by experimentation on real pages.

### 3.4. Backward compatibility on extractor data

`migrate.py` handles old skeletons captured before the extractor was updated
(no geometry, no `bgImage`, no `fontSize`). It degrades to class-based and
structural heuristics when geometry is absent. New code added to migrate.py
must preserve this property: if you add a check that requires a new field,
guard with `if node.get('newfield') is not None` or equivalent.

### 3.5. Sections cannot nest (DDC constraint)

The DDC grammar forbids nested sections. `discover_sections()` enforces this
by always returning a flat list, using `.extend()` (not `.append()`) when
combining results from recursive calls. Any new widget logic added must
similarly emit flat structure — a widget cannot contain other widgets in
DDC's grammar except as inline HTML inside a content widget.

---

## 4. The widget extension pattern

Every widget type follows the same lifecycle inside `editorial_chunk`:

1. **Detection**: `is_X_widget(node, context)` — multi-signal classifier
   returns True if `node` should be emitted as widget type X.
2. **Extraction**: `extract_X_widget(node)` — pulls the structured data out
   of the node and returns the widget config dict.
3. **Emission**: in `editorial_chunk`, where currently only `content` and
   `image` paths exist, add a check for each new widget type BEFORE the
   generic content path. Order matters: more specific detectors run first;
   the catch-all content widget runs last.

The output widget shape extends to:

```python
{
  'type': 'content' | 'image' | 'links' | 'raw_html' | 'hours' | 'contact_info' | 'accordion',
  # type-specific fields:
  'html': str,           # content, raw_html
  'preview': str,        # content (for debugging output)
  'url': str,            # image
  'links': [             # links widget
    {'label': str, 'url': str, 'style': str?}
  ],
  'hours': {             # hours widget
    'monday': {'open': '09:00', 'close': '18:00'},
    ...
  },
  'contact': {           # contact_info widget
    'name': str, 'address': str, 'phone': str, 'email': str,
  },
  'items': [             # accordion widget
    {'question': str, 'answer_html': str},
    ...
  ],
}
```

When the deterministic classifier is confident, emit the widget config.
When ambiguous, emit a placeholder with `_needs_llm: True` and the raw node;
the analyze endpoint handles LLM fallback at the boundary.

---

## 5. Links widget — immediate implementation spec

A Links widget represents one or more buttons grouped together (CTAs at the
end of a section, button rows, single action buttons).

### 5.1. Why class-only detection fails

The naive approach — "is the class `btn` or `button` or `cta`?" — fails
because every CMS uses different conventions:

```
DealerOn:        aag-btn aag-btn-main aag-btn-lg aag-btn-block
Mazda CMS:       btn btn-lg btn-danger
DealerInspire:   (different naming, not yet sampled)
Bootstrap raw:   btn btn-primary
Custom:          arbitrary
```

You cannot enumerate the class set. The signal stack must work without it.

### 5.2. Multi-signal detection — `is_button(node, parent_context)`

Stack the following signals. Each contributes 1 point. Threshold for
positive classification: ≥3 points.

**Structural signals (most reliable, cheapest)**

- **S1**: `node.tag == 'a'` OR `node.tag == 'button'` OR `node.get('role') == 'button'`. If False, return False immediately — buttons are anchors, buttons, or role-buttons. No other tag qualifies.
- **S2**: Not nested inside a `<p>` tag (walk up the parent chain when needed; or check during editorial_chunk where parent context is known). Inline text links live in `<p>`; buttons don't.
- **S3**: Siblings are not text nodes. Adjacent content is whitespace, other buttons, or block elements — not flowing text.

**Geometric signals (high reliability when extractor data is present)**

- **G1**: `node.h > node.fontSize * 1.5`. Buttons have visual padding pushing
  height beyond raw text height. Inline links match text height exactly.
- **G2**: `node.w >= 80`. Buttons have minimum widths; inline link widths
  match their text content and can be very narrow.

**Style signals**

- **C1**: `node.bg` is set and non-transparent. Buttons have background
  color treatment; inline links don't (they have color and underline, not bg).
- **C2**: `node.bgImage` is set (gradient buttons, some image-bg buttons).

**Class signals (weakest, confirmation only)**

- **K1**: Class word-set contains any of `{btn, button, cta}`. Word-boundary
  match (split on whitespace and dash, like chrome detection — same pattern,
  different word list).

**Total**: 8 signals available, threshold 3+. The DealerOn example you
should encounter (`aag-btn aag-btn-main aag-btn-lg aag-btn-block`) hits S1,
S2, S3, almost certainly G1, G2, K1 — 6 of 8. A naked inline link `<a
href="...">click here</a>` inside a `<p>` hits S1 only. The threshold of 3
draws a clean boundary.

### 5.3. Button grouping — `group_buttons(buttons_in_subtree)`

A Links widget can hold multiple buttons. After button detection, group
adjacent buttons into single widgets:

- Two or more buttons with the **same parent** AND **similar geometry**
  (heights within 30%, font sizes within 30%) → one Links widget with
  multiple entries.
- An isolated button → its own Links widget with one entry.

Order within the widget follows document order (or x-order for horizontal
button rows).

### 5.4. Extraction — `extract_links(button_nodes)`

For each button, extract:

```python
{
  'label': button.text.strip(),
  'url': button.href or '',
  'style': classify_button_style(button),  # optional: 'primary' | 'secondary' | 'danger' | None
}
```

`classify_button_style` uses class-word matching for style hints (`primary`,
`secondary`, `danger`, `warning`, `success`, `info`) when present. If absent
or ambiguous, omit the field; the execution layer applies DDC's default.

### 5.5. Emission in `editorial_chunk`

In the for-loop where each semantic element is processed, add button detection
BEFORE the standalone-image check (buttons should not be misclassified as
images even though both can be standalone):

```python
# Pseudo-code addition
for el in elements:
    if is_button(el, parent_context):
        # Look ahead/behind to see if siblings are also buttons (grouping)
        button_group = collect_button_group(elements, el)
        flush()  # close any open content chunk
        widgets.append({
            'type': 'links',
            'links': extract_links(button_group),
        })
        continue  # skip the grouped buttons in subsequent iterations
    elif is_standalone_image(el):
        ...
    elif should_split_at(el, split_level) and current:
        ...
    ...
```

Implementation note: `flatten_to_semantic` currently doesn't capture `<a>`
tags as semantic blocks. Either extend `SEMANTIC_BLOCK_TAGS` to include `a`
(but only when standalone — not when inside a `<p>`), or add an explicit
post-flatten pass that scans for buttons. The latter is cleaner because it
avoids polluting the heading/list/paragraph semantic set.

### 5.6. What's needed from outside migrate.py

To implement this fully, two pieces of information are needed from the
broader system:

1. **DDC Links widget config schema**: what fields the execution layer
   expects per button. Minimum is probably `{label, url}` but DDC may
   support more (icon, color, target, size). The execution layer
   (`inject_section` / widget config calls in the Chrome extension) is the
   source of truth here.

2. **Confirmation of extractor attribute capture**: the extractor needs to
   capture `href` (it does, already used in `render_html`) and ideally
   `role`. If `role` is not yet captured, add it — `role="button"` is a
   strong signal for `<div>`s and `<span>`s styled as buttons. Cheap
   extractor change.

### 5.7. Test cases for validation

The deterministic Links classifier should be regression-tested on:

- Mazda Food Bank page: the `a.btn btn-lg btn-danger` button at y=1330 in
  the col-md-8 slot should be detected as a single-button Links widget.
- DealerOn page (need fresh skeleton): the `aag-btn` example should classify.
- DealerInspire page (need fresh skeleton): unknown class names should
  classify via structural + geometric signals alone.
- Mazda blog: inline links inside paragraphs MUST NOT be misclassified as
  buttons. The current expected output (12 widgets, no links) should not
  change after the Links classifier is added.
- DDC reference page (Buddy Chevy / Decatur): existing 4 sections should
  remain unchanged after Links is added (Decatur §4 is a contact form,
  separate concern).

---

## 6. Other widgets — sketches for future iteration

These are NOT to be implemented yet. Listed here so future work has a
starting framework.

### 6.1. RAW HTML widget

Use case: iframes, embedded videos, third-party calculators, scripts —
content that exists in source but shouldn't be editable by non-technical
dealer staff in DDC.

**Detection (almost fully deterministic)**:

- Subtree contains `<iframe>`, `<embed>`, `<object>`, `<video>`, `<canvas>`, `<script>` → RAW HTML.
- Subtree has complex inline styles that wouldn't survive content-editor
  round-trips (CSS variables, gradients, transforms) → RAW HTML.
- Class names indicating third-party widgets (Google Maps embed, payment
  widget, etc.) → RAW HTML.

**Extraction**: pass through the raw outer HTML of the subtree, escape
appropriately for DDC's content storage. Preserve the original markup
verbatim.

LLM role: essentially zero. This is one of the most clearly deterministic
widget types.

### 6.2. Hours widget

Use case: dealer business hours display.

**Detection (deterministic)**:

- Schema.org `OpeningHours` markup (microdata or JSON-LD) → HIGHEST signal
- Class names containing word-boundary `hours`, `schedule`, `business-hours` → strong
- Text content matches `Mon|Tue|Wed|...` + time-range regex → strong
- Structural pattern: small block with repeated day+time rows → medium

**Extraction (deterministic for common formats, LLM fallback for tail)**:

- 80% of dealer hours blocks use one of three patterns: HTML table with day
  and time columns, `<dl><dt>day</dt><dd>time</dd>`, or repeated divs with
  day class + time class. Build parsers for these three.
- Long tail (free-form prose like "Open Monday through Saturday from 9 to
  6"): fall back to LLM with a narrow extraction prompt that returns
  structured day→time JSON.

### 6.3. Contact Info widget

Use case: dealership name, address, phone, email, social links.

**Detection (deterministic)**:

- Schema.org `LocalBusiness` or `AutoDealer` JSON-LD → trivial extraction
- Class names containing `contact`, `address`, `phone-info` → strong
- Co-occurrence of phone regex + email regex + address pattern within a
  small block → strong

**Extraction**: parse schema.org JSON-LD directly when present; otherwise
pattern-match each field with regex. LLM fallback for unstructured prose.

### 6.4. Accordion widget

Use case: FAQs and other collapsible Q&A sections.

**Detection (deterministic)**:

- Repeated heading-content pairs at the same depth, ≥3 pairs in sequence
- Class names containing `faq`, `accordion`, `panel`, `question`
- HTML5 `<details><summary>` native pattern
- `<dl><dt><dd>` semantic pattern

**Extraction**: pair adjacent siblings into `{question, answer_html}`
tuples. Order preserved from document.

LLM role: essentially zero. This is one of the most structural widget
types.

---

## 7. Integration with the backend pipeline

`migrate.py` is the analysis-layer module. The `/analyze` FastAPI endpoint
should:

1. Receive the DOMSkeleton from the extension via WebSocket or HTTP.
2. Call `migrate(skeleton)` — returns the deterministic plan.
3. For each widget in the plan, check `_needs_llm` (TO BE ADDED — currently
   not part of the schema). If True, invoke the LLM with the corresponding
   `_slot_nodes[i]` subtree as context, narrow extraction prompt.
4. Strip internal fields (`_slot_nodes`, `_needs_llm`) before serializing
   the response to the frontend.
5. Send the cleaned plan to the extension for execution.

The "Run Deterministic Algo" button currently in the Chrome extension is
debt and should be removed once the algorithm is fully integrated into
`/analyze`. The button was added during development to A/B test against the
LLM-only path; it shouldn't ship.

Preserve the LLM-only code path behind a feature flag for now
(`USE_DETERMINISTIC_SEGMENTER = True`). Don't delete it. Two reasons:
graceful fallback if the deterministic algorithm hits a class of pages it
can't handle, and A/B logging during the next batch of pages to validate the
deterministic plan against LLM plan on real data.

---

## 8. What NOT to do

These mistakes have already been made and reversed during development.
Future agents working on this code should not repeat them:

- **Don't add depth limits to the DOM walk.** The extractor walks to leaves
  with chrome and hidden-element pruning. A depth cap will silently lose
  content on deep wrapper soups (modern CMSs nest 10+ levels routinely).
- **Don't dump the whole page DOM at an LLM and ask for a one-shot
  migration plan.** That was the original architecture; it produced output
  that was wrong in unpredictable ways. The whole point of `migrate.py` is
  to avoid this.
- **Don't conflate "one visual area" with "one editable widget."** A single
  visual section can contain multiple stacked widgets — that's the
  editorial-chunking principle. Multiple `empty-one` sections instead of one
  `empty-one` with stacked widgets is bad DDC practice.
- **Don't strip classes too aggressively at the chrome layer.** The original
  chrome detector matched `header` as a substring and ate `<h1
class="header">`. Word-boundary matching with heading-tag exemption is
  the correct rule.
- **Don't rely on single-attribute classification.** The "class contains
  btn" approach fails on every CMS that doesn't use that exact word. Stack
  signals.
- **Don't break the deterministic-first contract.** If a new widget
  classifier requires an LLM call to function at all, redesign it — the
  classifier must be capable of working without LLM access. LLM is fallback
  only.

---

## 9. Open questions

- DDC Links widget config schema — exact field names and types
- Whether DDC catalog includes `empty-33-33-33` (3 equal columns) and
  `empty-25-25-25-25` (4 equal columns) — extending the layout classifier
  is one-liner per ratio if so
- Extractor coverage of `role` and `aria-label` attributes — useful signals
  for buttons and ARIA-labeled elements
- Image URL pattern for `img.custom-image-blogs` (Mazda CMS) — find via
  Chrome devtools inspection
- Tolerance tuning for column-ratio matching — current 0.08 may need
  loosening or tightening based on real-page experiments

---

## 10. Validation and testing

Before merging any classifier extension:

1. Run migrate.py on the existing three test skeletons (Decatur, Mazda
   blog, Food Bank) and confirm output is unchanged for unrelated widgets.
   The new classifier should only affect blocks it detects; everything else
   must regression-clean.
2. Run on any new skeletons added for the specific widget being added
   (DealerOn, DealerInspire for buttons; pages with FAQs for accordions;
   etc.).
3. Capture both the deterministic plan and the LLM plan on the same
   skeleton (shadow mode) and compare. Divergences are either bugs in the
   deterministic classifier or hallucinations from the LLM; investigate
   case by case.
4. After 20+ pages, compile an eval set from the disagreement cases. These
   become the regression test suite.

---

## 11. Code locations referenced

- `migrate.py` (this directory) — the deterministic algorithm
- `extractSkeleton.ts` (frontend Chrome extension) — DOM capture, currently
  produces: tag, cls, text, src, href, x, y, w, h, bg, bgImage, fontSize,
  children, with chrome+hidden+`position:fixed` pruning at capture time
- `/analyze` endpoint (FastAPI backend) — entry point, calls migrate() and
  optionally LLM
- Chrome extension widget injection (frontend, JS injected into DDC tab) —
  consumes the final plan, calls DDC's internal JavaScript widget API over
  WebSocket RPC

The `_slot_nodes` field in the migrate output exists specifically to bridge
the deterministic layer and any LLM fallback — it provides raw DOM context
to a narrower LLM prompt without requiring the LLM to re-parse the page.
