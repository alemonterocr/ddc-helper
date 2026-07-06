# Translate Navigation Labels

**Status:** PLANNED
**Date:** 2026-07-06
**Purpose:** Batch-translate all navigation labels from a dealer's DDC CMS composer — load the nav tree via `CommandExecutor?cmd=LoadNavigation`, detect which labels need translation, and feed them through the existing `/translations/translate` pipeline one by one, reusing the same review-and-save workflow.

---

## 1. Goal

Instead of pasting label aliases manually, let the user click one button to pull the entire navigation tree from DDC, filter down to labels that need translation (empty es_US text or alias-as-label placeholders), and run those through the existing translate→review→save loop.

**Anti-goals:**
- Do NOT auto-save. Every translation gets human review just like the Simple Label flow.
- Do NOT translate labels that already have real Spanish text. The system detects and skips them, with a "force translate" escape hatch.
- Do NOT make DDC calls from the Python backend. The browser holds session cookies; the backend only processes JSON blobs it receives from the FE.
- Do NOT use an LLM for the "needs translation" check — it's a deterministic regex test.

---

## 2. Architecture overview

```
+---------------------------------+         POST              +----------------------------+
|  fe_ddc_helper                  |  /translations/nav-check   |  be_ddc_helper               |
|  (Chrome extension)             | <------------------------> |  (FastAPI)                   |
|                                 |                            |                             |
|  NavTranslateTab (new organism) |  POST /translations/       |  translations_router.py      |
|  └─ LabelRow (× N) [reused]     |     translate [reused]     |  ├─ POST /nav-check  (new)   |
|  └─ LabelRow (× N) [reused]     |                            |  └─ POST /translate [reused] |
|                                 |                            |                             |
|  LabelAdapter                   |         injected script    |                             |
|  ├─ fetchLabel  [reused]        | ========================== |                             |
|  ├─ saveLabel   [reused]        |                            |                             |
|  └─ loadNav     [new]           |    DDC composer tab        |                             |
|                                 |   (CommandExecutor)        |                             |
+---------------------------------+                            +----------------------------+
```

Key principle: **FE loads nav JSON; BE checks what needs translation; FE drives the translate loop.** The only new BE surface is a deterministic filter endpoint. Everything else is reused.

---

## 3. Pipeline

### 3.1 Load nav — `POST LoadNavigation` (FE, injected script)

The FE injects a self-contained script into the active DDC composer tab:

```
POST /composer/views/CommandExecutor?cmd=LoadNavigation
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Body: json={URL-encoded payload}
```

**Payload:**
```json
{
  "javaClass": "com.dealer.cms.apps.composer.commands.nav.LoadNavigation",
  "navId": "...",
  "siteId": "{dealerSlug}",
  "locale": "es_US",
  "accountId": "{dealerSlug}",
  "userId": "{discovered from page state}",
  "siteType": "primary"
}
```

**Response shape** (relevant fields):
```
result.dto.navigationItems.list[]  — top-level nav items (tabs/parents)
  ├─ labelAlias                    — the DDC label alias
  ├─ label                         — display text in es_US locale
  ├─ navigationItems.list[]        — child items (dropdown entries)
  │   ├─ labelAlias
  │   └─ label
  ...
```

The injected script walks this tree recursively, collects all `{ alias, label }` pairs (both parent and child levels), and returns them as a flat array plus the raw nav JSON for provenance.

**Injected script constraints** (same as all `scripts/`):
- Self-contained — zero imports, zero closures over module-level variables
- All helpers defined as named functions inside the function body
- Runs via `chrome.scripting.executeScript` with `credentials: 'include'`

### 3.2 Nav-check — `POST /translations/nav-check` (BE, new)

**File:** `be_ddc_helper/src/adapters/inbound/http/translations_router.py` (new route in existing router)

**Request:**
```
{ nav_json: object, dealer_name: str }
```

**Processing** — deterministic, no LLM, no LangGraph:

1. Walk `nav_json.result.dto.navigationItems.list[]` recursively (2 levels: parent + children)
2. For each item, collect `{ alias: labelAlias, label_es: label }`
3. Classify each:
   - `to_translate` if: `label_es` is empty **OR** `label_es` matches `^[A-Z0-9_]+$` (looks like an alias, not real text)
   - `skipped` otherwise (has Spanish-looking text)
4. Return both lists + total count

**Detection rule rationale:**
- Empty string → nothing was ever translated, needs work
- Uppercase + underscores → DDC defaults to showing the alias as the label when no translation exists (e.g. `FINANCING_FOR_SERVICE___PARTS`, `RESEARCH_NEW_MODELS`). This is the same regex used by `/translations/sanitize` (`_ALIAS_RE`).
- Everything else → likely has real Spanish text, skip it. User can force-include via the FE.

**Response:**
```
{
  to_translate: [{ alias: str, label_es: str }],
  skipped:     [{ alias: str, label_es: str }],
  total:       int
}
```

### 3.3 Translate loop (FE, reuses existing pipeline)

For each alias in `to_translate`:

1. **Fetch EN** — `LabelAdapter.fetchLabel(dealerSlug, alias)` via injected script. Gets `en_US` from the labels API. If not found → status `not_found`, advance.
2. **Translate** — `POST /translations/translate { alias, en_html, dealer_name, provider }` — same LLM pipeline with glossary, structural validator, semantic judge, 1 retry.
3. **Review** — `LabelRow` component (reused as-is). Shows EN preview (collapsible), ES textarea (editable), warnings, reasoning, retranslate/skip/save buttons.
4. **Save** — `LabelAdapter.saveLabel()` via injected script. POSTs both `en_US` and `es_US` back to DDC. Auto-advances to next queued alias.

### 3.4 Skipped list (FE, new)

Shown in a collapsible footer below the translate rows. Each entry:
- Shows `alias` + `label_es` (the existing Spanish text)
- Has a **[Force translate]** link that moves it to `to_translate` and triggers `runTranslation()`

This is the escape hatch for false negatives (e.g. `CERTIFIED_OVERVIEW_1` where `es` = "Certified Overview" — real English text that happens to look like Spanish to the heuristic).

---

## 4. Data model

### 4.1 BE DTOs (`translations_dtos.py` — new)

```python
class NavCheckItem(BaseModel):
    alias: str
    label_es: str

class NavCheckRequest(BaseModel):
    nav_json: object   # the raw LoadNavigation response body
    dealer_name: str

class NavCheckResponse(BaseModel):
    to_translate: list[NavCheckItem]
    skipped: list[NavCheckItem]
    total: int
```

### 4.2 FE types (`types/index.ts` — new)

```ts
interface NavCheckRequest {
  nav_json: object
  dealer_name: string
}

interface NavCheckItem {
  alias: string
  label_es: string
}

interface NavCheckResponse {
  to_translate: NavCheckItem[]
  skipped: NavCheckItem[]
  total: number
}

interface NavLoadResult {
  /** Flat array of { alias, label_es } extracted from the nav tree. */
  items: { alias: string; label_es: string }[]
  /** Raw nav JSON returned to the BE for /nav-check provenance. */
  raw: object
  /** Error message when the injected script failed. */
  error?: string
}
```

### 4.3 No new store types needed

The existing `SpanishLabelRow` and `SpanishMigrationProject.labels` work unchanged. The nav tab populates `project.labels` the same way `SpanishPanelWorkflow` does via `setSpanishLabels(project.id, aliases)`.

---

## 5. Frontend workflow

### 5.1 NavTranslateTab (new organism)

Sits inside `ProjectPage.tsx` alongside the existing `SpanishPanelWorkflow`. The Spanish project type gets tabs:

```
[Simple Labels] [Translate Nav]
```

**Tab 1 — Simple Labels**: the existing `SpanishPanelWorkflow` (paste aliases → sanitize → translate loop). Unchanged.

**Tab 2 — Translate Nav**: the new `NavTranslateTab`.

### 5.2 NavTranslateTab flow

1. **"Load Navigation Labels" button** → injected script fires `LoadNavigation` with `es_US`, returns raw JSON + flat items list
2. **`POST /translations/nav-check`** → receives `to_translate` + `skipped` lists
3. **Counters shown**: "X queued · Y skipped"
4. **Auto-advance loop** — same as `SpanishPanelWorkflow`: translate first alias immediately, each save advances to next
5. **`LabelRow` reused** — same EN/ES card, same save/skip/retranslate buttons
6. **Skipped footer** — collapsible, each row has **[Force translate]**

### 5.3 LabelPort (new method)

```ts
export interface LabelPort {
  // ... existing methods ...

  /** Load the navigation tree from DDC's CommandExecutor.
   *  Injects a self-contained script into the composer tab. */
  loadNav(dealerSlug: string, userId: string): Promise<NavLoadResult>
}
```

### 5.4 LabelAdapter (new method)

```ts
async loadNav(dealerSlug: string, userId: string): Promise<NavLoadResult> {
  // 1. findComposerTabId() — same pattern as fetchLabel / saveLabel
  // 2. chrome.scripting.executeScript with injected loadNav function
  // 3. Return { items, raw, error }
}
```

The injected script:
1. Reads `userId` from page state (or accepts it as an argument)
2. Calls `POST /composer/views/CommandExecutor?cmd=LoadNavigation` with `locale: "es_US"`
3. Walks the tree, collects `{ alias, label }` for all items (parent + child)
4. Returns `{ items, raw }`

### 5.5 ProjectPage changes

The Spanish branch (`isSpanish`) switches from:
```tsx
<SpanishPanelWorkflow project={project as SpanishMigrationProject} />
```

to:
```tsx
<Tabs defaultValue="simple">
  <TabsList>
    <TabsTrigger value="simple">Simple Labels</TabsTrigger>
    <TabsTrigger value="nav">Translate Nav</TabsTrigger>
  </TabsList>
  <TabsContent value="simple">
    <SpanishPanelWorkflow project={project as SpanishMigrationProject} />
  </TabsContent>
  <TabsContent value="nav">
    <NavTranslateTab project={project as SpanishMigrationProject} />
  </TabsContent>
</Tabs>
```

Follows the same `<Tabs>` pattern already used by `GmPrebuildFlowPanel` in `ProjectPage.tsx:162-179`.

---

## 6. Key design decisions

1. **Deterministic filter, not LLM.** The "needs translation" check is a regex — empty string or looks-like-an-alias. Using an LLM here would burn tokens on 59 labels to find 4 untranslated ones. The skipped list with force-translate is the cheaper, more reliable escape hatch.

2. **Single locale call.** We load `es_US` only, not `en_US`. The nav tree structure is identical across locales (confirmed via diff on a real dealer). The EN text is fetched per-alias via the existing `fetchLabel` which is already required for the translate step.

3. **Nav-check is a flat endpoint, not a LangGraph node.** No LLM is involved — no graph is needed. Adding a node would be ceremony for a pure data transform. If future work adds pre-processing steps, we can retroactively wrap it in a graph without changing the router interface.

4. **Reuse LabelRow unchanged.** The review UX is identical whether the alias came from a paste or from a nav load. No component changes needed.

5. **Reuse the translate pipeline unchanged.** `translate_label_node.py`, `validator.py`, glossary, prompts, LLM adapters — zero changes. The nav tab is a new FE path into the same BE pipeline.

6. **Browser is thin executor for DDC.** `LoadNavigation` is an injected script call just like `fetchLabel` / `saveLabel`. The backend never touches DDC directly.

7. **Tab-based organization in the FE.** Uses the same `<Tabs>` pattern as GM Prebuild's "Page Migration" / "Setup Data" split. Keeps Simple Labels and Translate Nav in the same project page without code duplication.

---

## 7. File reference (complete map)

### BE — New
| File | What changes |
|------|-------------|
| `src/adapters/inbound/http/translations_router.py` | Add `POST /translations/nav-check` route |
| `src/adapters/inbound/http/translations_dtos.py` | Add `NavCheckItem`, `NavCheckRequest`, `NavCheckResponse` DTOs |

### BE — Reused (unchanged)
| File | Role |
|------|------|
| `src/application/translate_labels/translate_label_node.py` | Core translate node |
| `src/application/translate_labels/translate_labels_graph.py` | LangGraph wiring |
| `src/application/translate_labels/validator.py` | Structural validator |
| `src/domain/translations/glossary_es.csv` | Glossary |
| `src/domain/translations/glossary_search.py` | Glossary tool |
| `src/adapters/outbound/prompts.py` | Translation + judge prompts |
| `src/adapters/outbound/anthropic/anthropic_llm_adapter.py` | Anthropic tool definitions |
| `src/adapters/outbound/deepseek/deepseek_llm_adapter.py` | DeepSeek tool definitions |
| `src/adapters/outbound/gemini/gemini_llm_adapter.py` | Gemini tool definitions |

### FE — New
| File | What changes |
|------|-------------|
| `src/services/ports/LabelPort.ts` | Add `loadNav(dealerSlug, userId)` method |
| `src/services/adapters/LabelAdapter.ts` | Implement `loadNav` (injected script + CommandExecutor call) |
| `src/types/index.ts` | Add `NavCheckRequest`, `NavCheckItem`, `NavCheckResponse`, `NavLoadResult` types |
| `src/components/organisms/NavTranslateTab/NavTranslateTab.tsx` | New organism: nav load → nav-check → translate loop |
| `src/scripts/loadNav.ts` or inline in `LabelAdapter` | Injected script for `LoadNavigation` command |

### FE — Modified
| File | What changes |
|------|-------------|
| `src/components/pages/ProjectPage/ProjectPage.tsx` | Spanish branch: wrap in `<Tabs>` with "Simple Labels" + "Translate Nav" |

### FE — Reused (unchanged)
| File | Role |
|------|------|
| `src/components/organisms/SpanishPanelWorkflow/SpanishPanelWorkflow.tsx` | Simple Labels tab (unchanged) |
| `src/components/molecules/LabelRow/LabelRow.tsx` | Per-label review card |
| `src/components/molecules/SpanishProjectForm/SpanishProjectForm.tsx` | New project form |

---

## 8. Risks & open questions

### 8.1 How to discover `navId`?

The `LoadNavigation` command requires a `navId` (e.g. `"V9-MAIN-HYUNDAI"`). This value is not derivable from the dealer slug alone — it depends on the site template. Options to resolve:

1. **Call `GetWindowPreferences` or equivalent first** (same pattern as `SetWindowPreferences` in `cmsTools.ts`) to read the saved nav ID from composer preferences. Preferred — deterministic, same-origin.
2. **Read from page JS state** — the composer's ExtJS/React store likely has a `navId` or `navList` property. Parseable via `document` inspection in the injected script. Frail against UI changes.
3. **Brute-force try** — attempt `V9-MAIN-{BRAND}` patterns and check for valid responses. Ugly but self-contained.
4. **User input** — expose a dropdown or text field for the nav ID. Breaks the "one button" UX goal.

**Recommendation:** spike option 1 first (preferences call), fall back to option 2 (page state read). Document the chosen approach here once resolved.

### 8.2 How to discover `userId`?

The `LoadNavigation` payload requires `userId` (e.g. `"almontero"`). Options:

1. **Read from page state** — the composer page's JS context likely has this in a user/session object. Same ExtJS/React store read as navId.
2. **From the URL** — not present in the composer URL.
3. **From a separate API call** — `GET /cc-website/as/{slug}/{slug}-admin/composer/...` likely returns user info.

**Recommendation:** same spike as navId — read from page state.

### 8.3 `userId` in flat map → no context

The nav tree is collected as a flat list. The user won't see which parent item a child belongs to. For 59 labels this is acceptable — the DDC composer already shows the tree. If confusion arises, add a small `parentLabel` context in the `LabelRow` header: "VEHICLE_RESEARCH *under* Shop". This is a v1.1 polish item, not blocking.

### 8.4 Extra `userId` parameter on `loadNav`

The `loadNav(dealerSlug, userId)` method takes an extra parameter compared to `fetchLabel(dealerSlug, alias)`. If `userId` can be discovered inside the injected script (from the page state), this parameter can be removed — `loadNav(dealerSlug)` alone would suffice.

### 8.5 False negatives in the detection heuristic

Labels like `CERTIFIED_OVERVIEW_1` where `es` = "Certified Overview" (English text that looks like Spanish to the regex) will be marked as skipped. Mitigated by the **[Force translate]** link in the skipped list. Acceptable trade-off: the heuristic catches >90% of untranslated labels; the rest are one click away.
