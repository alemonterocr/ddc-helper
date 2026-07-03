---
name: injected-scripts
type: script
status: built
---

## Purpose
Self-contained functions injected into browser tabs via
`chrome.scripting.executeScript`. These are the only code that runs inside
a foreign tab's context.

## Contracts
- **ZERO imports** — these files must be fully self-contained
- **ZERO closures** over external module-level variables (Vite minification
  rewrites them and the injected `.toString()` body loses the binding)
- Every function is exported for TypeScript type safety, but the serialised
  body is what gets injected — module structure isn't preserved
- No module-level `const`s referenced from inside an injected function
  (same minification trap as closures)

## Dependencies
None (by definition)

## Scripts

| Script file | Run target | Purpose |
|---|---|---|
| `extractSkeleton.ts` | Live dealership site tab (isolated world) | Walk the DOM and emit a structured JSON skeleton consumed by the BE pipeline |
| `cmsTools.ts` | DDC CMS tab (isolated world, JSESSIONID auth) | Section/widget operations against `/cms-configurator/*` endpoints |
| `mediaLibTools.ts` | DDC Media Library tab (MAIN world, JWTAuth cookie) | Upload images, manage folders. MAIN world required — DDC validates `Sec-Fetch-Site` and JWTAuth, both of which only work from the page's own JS context |

## `extractSkeleton` pruning

Pruning at capture time is intentionally narrow — the FE only drops what's
**definitely not content** so the BE can make all class-based decisions
with full visibility (see `be_ddc_helper/src/domain/deterministic_migrate.py`).

The walker drops in this order:

1. **`SKIP_TAGS`** — `script`, `style`, `svg`, `noscript`, `link`, `meta`,
   `head`, `iframe`. Entire subtree dropped.
2. **`CHROME_TAGS`** — `header`, `footer`, `nav`, `aside`. Entire subtree
   dropped (semantic chrome is unambiguous).
3. **Hidden / fixed-position** — `display:none`,
   `visibility:hidden`, `position:fixed`, or zero-area bounding rect.
   Caught at the element level; doesn't recurse.

Everything else flows through. Class-name pruning (`sidebar`, `chat-*`,
`social-*`, etc.) used to live here and was moved to the BE during the
hexagonal cleanup — the BE has full visibility into the candidate
subtrees and can ask the LLM to KEEP/DROP via `chrome_review`.

## `extractSkeleton` walker — mixed-content handling

Elements with element children get walked via `childNodes` (not `children`)
so interleaved text nodes are captured as `#text` pseudo-children:

```html
<p>Hello <strong>world</strong> tail</p>
```

becomes:

```ts
{ tag: 'p', text: '', children: [
  { tag: '#text', text: 'Hello ' },
  { tag: 'strong', text: 'world', children: [] },
  { tag: '#text', text: ' tail' },
]}
```

Pure-text leaves (no element children) skip the pseudo-child machinery and
keep their text on the parent as before. Whitespace-only text nodes (HTML
indentation) are dropped; runs of internal whitespace are collapsed but
significant leading/trailing single spaces are preserved.

## Captured node fields

Per real element node:

| Field | Source |
|---|---|
| `tag`, `cls` | `el.tagName.toLowerCase()`, `el.getAttribute('class')` |
| `text` | `el.textContent` (only when no element children) |
| `style` | Layout-relevant inline styles only (`display`, `width`, `flex`, `grid` family) |
| `bg` | `getComputedStyle(el).backgroundColor` — emitted only when different from the parent's |
| `src`, `href`, `target` | On `<img>` and `<a>` respectively |
| `role` | On any element with the attribute set |
| `x`, `y`, `w`, `h` | `getBoundingClientRect()` + scroll offset, rounded to int |
| `bgImage`, `bgImageSrc` | When the element has a non-`none` `background-image` |
| `fontSize` | Computed font-size in px |
| `children` | Element children + `#text` pseudo-children, document order |

`#text` pseudo-children carry only `tag: '#text'`, `cls: ''`, `text`, and
an empty `children` array — all geometry/style fields are absent.
