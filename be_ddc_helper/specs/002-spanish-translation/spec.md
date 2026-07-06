# Spanish Label Translation

**Status:** BUILT
**Date:** 2026-07-06
**Purpose:** LLM-powered EN→es_US (Mexican Spanish) translation of DDC CMS website labels, with glossary-based terminology, structural + semantic validation, and human-in-the-loop save.

---

## 1. Goal

Translate DDC CMS label aliases from `en_US` to `es_US` at scale. The specialist pastes a blob of label aliases, and the system translates each one individually — fetching the English value from DDC, running it through an LLM with a domain glossary, validating the output both structurally and semantically, and letting the user review, edit, and save each translation back to DDC.

**Anti-goal:** do NOT batch-translate and auto-save. The user reviews every translation before it hits DDC. Do NOT make DDC calls from the Python backend — the browser holds the session cookies.

---

## 2. Architecture overview

```
+---------------------------+       HTTP POST        +---------------------------+
|  fe_ddc_helper            |  /translations/sanitize |  be_ddc_helper             |
|  (Chrome extension)       |  /translations/translate|  (FastAPI + LangGraph)     |
|                           | <---------------------> |                           |
|  SpanishPanelWorkflow     |                        |  translations_router.py    |
|  └─ LabelRow (× N)        |                        |  └─ translate_labels_graph |
|  LabelAdapter             |                        |     └─ translate_label_node|
|  └─ sanitize / translate  |                        |        ├─ LLM (glossary)   |
|  └─ fetchLabel / saveLabel|                        |        ├─ validator.py     |
|                           |                        |        └─ LLM judge        |
+---------------------------+                        +---------------------------+
         |                                                    |
         | chrome.scripting.executeScript                     | LLMPort (Anthropic /
         | (session cookies auto-attached)                    |  Gemini / DeepSeek)
         v                                                    v
+---------------------------+                      +-----------------------+
|  DDC CMS composer tab     |                      |  LLM Provider         |
|  (labels API)             |                      |  (glossary_lookup +   |
+---------------------------+                      |   submit_translation) |
                                                   +-----------------------+
```

Key principle: **Python translates; Chrome fetches and saves.** The browser holds DDC session cookies. The backend never calls DDC directly.

---

## 3. Pipeline (per label)

### 3.1 Sanitize — `POST /translations/sanitize`

```
Raw paste blob → split on whitespace/commas/semicolons → uppercase → deduplicate
                 → validate each token matches ^[A-Z0-9_]+$
                 → return { aliases, dropped }
```

No LLM involved. Pure regex. See `translations_router.py:30-60`.

### 3.2 Translate — `POST /translations/translate`

Single-node LangGraph graph (`translate_label → END`). Intentional — kept as a graph so future nodes (e.g. `load_existing_es`, `dictionary_postprocess`) can extend without restructuring.

**Request:** `{ alias, en_html, dealer_name, provider }`
**Response:** `{ alias, es_html, status ("ready"|"error"), warnings, raw, reasoning }`

#### Step 1: Translator with glossary tool

The LLM receives a system prompt (`build_label_translation_system_prompt_v2`) with two tools:

1. **`glossary_lookup(terms)`** — case-insensitive exact match against `glossary_es.csv`. Returns `{ term: es_value | null }`. The model calls this once with all uncertain automotive/dealership terms. Returns null for terms not in the glossary.
2. **`submit_translation(reasoning, translation)`** — mandatory final call. `reasoning` is 1-3 sentences explaining choices; `translation` is the final es_US string. No plain-text output allowed — the tool gate prevents thinking from leaking into the visible result.

Context rules baked into the prompt:
- Brand/model names NEVER translated (e.g. "Toyota 4Runner" stays "Toyota 4Runner")
- "Directions" disambiguated contextually: "Ubicación" (place) vs "Indicaciones" (driving)
- No Spanish articles before vehicle model names
- Preserve all HTML tags, attributes, href values, bracketed variables, and encoded entities

#### Step 2: Structural validator (`validator.py`)

Deterministic regex checks. No LLM. Validates:
- **Tag count** — every opening/closing tag matches across EN and ES
- **href values** — sorted set comparison; must be identical
- **Bracketed variables** — `[PRICE]`, `[MODEL]`, `[YEAR]` etc. must match exactly
- **Empty check** — translation must not be empty

Returns `list[str]` of human-readable warnings. Empty list = clean.

#### Step 3: Semantic guardrail (`_judge()`)

LLM-as-judge evaluates two dimensions:
1. **Naturalness** — reads smoothly to a native MX-Spanish speaker? Catches awkward phrasing, anglicisms, robotic renderings.
2. **Meaning fidelity** — conveys the same meaning? Catches dropped clauses, added info, mistranslated terms.

The judge does NOT evaluate HTML structure (step 2 handles that). Fails open — if the judge LLM call throws, the translation passes through rather than blocking the pipeline.

#### Step 4: Corrective retry

If structural check OR semantic check fails:
- Build a combined hint string from both sets of feedback
- Re-run the translator with `extra_hint` appended to the user message
- Re-run structural + semantic checks on the retry
- Return the retry result with warning context

**Retry budget: exactly 1.** The trade-off — now inherited from the original design — is to let the user hand-edit on persistent failure rather than spin through endless LLM attempts.

#### Response states

| `status` | Meaning |
|----------|---------|
| `ready` | Translation passed structural + semantic checks |
| `error` | Any check failed after retry; `raw` field holds the unvalidated output for hand-editing |

---

## 4. Glossary system

### 4.1 `glossary_es.csv`

69 automotive/dealership terms. Three-column CSV:

```
English,Spanish,MexicanSpanish
All Inventory,Todos los Vehículos,Todos los Vehículos
Lease,Arrendamiento,
...
```

**Loading rules** (`glossary_loader.py`):
- Prefer `MexicanSpanish` column when non-empty; fall back to `Spanish`
- Drop rows where the resolved ES is empty or `"<<"` (placeholder)
- Skip ambiguous terms listed in `_AMBIGUOUS_EN` (currently only `"directions"` — handled inline in the prompt)
- Cached via `@lru_cache`

### 4.2 `glossary_search(terms)`

Pure function — no I/O. Lowercases and does exact match. Returns `{ original_term: es_translation | None }`. The LLM calls this via the `glossary_lookup` tool.

### 4.3 Why tool-based instead of inline prompt

The original V1 prompt baked the full glossary into the system prompt (67 lines of `EN → ES` mappings). V2 replaced this with a `glossary_lookup` tool. Benefits:
- Smaller system prompt (fewer tokens)
- Model only looks up terms it's uncertain about
- Scoped lookups — no risk of the model hallucinating glossary entries it saw in prompt context

---

## 5. Validation details

### 5.1 Structural validator (`validator.py`)

| Check | Regex | Failure mode |
|-------|-------|-------------|
| Tag count | `<\s*(/?)\s*([a-zA-Z0-9]+)\b` | Tags missing or added relative to source |
| href values | `href\s*=\s*"([^"]*)"` | Sorted set comparison; any difference = warning |
| Bracketed variables | `\[[A-Z0-9_]+\]` | Variables dropped or added |
| Empty | `es.strip()` | Empty translation |

Intentionally loose where ambiguity is fine (text content changes freely) and strict where it isn't (structural markup must round-trip exactly).

### 5.2 Semantic judge

System prompt: `build_judge_translation_system_prompt` in `prompts.py:717-732`.

Evaluates naturalness + fidelity. Not pedantic — prefers "ok" when acceptable but imperfect. Fails open: if the judge call throws, the pipeline treats it as passing.

---

## 6. Frontend workflow

### 6.1 Types (`fe_ddc_helper/src/store/types.ts:67-136`)

```ts
type LabelRowStatus =
  | "queued"       // sanitized, waiting to start
  | "fetching"     // GET-label from DDC in flight
  | "translating"  // /translations/translate in flight
  | "ready"        // translation clean, awaiting user save
  | "error"        // fetch failed, or translation failed validation
  | "saved"        // POST-label to DDC succeeded
  | "skipped"      // user opted to skip
  | "not_found";   // DDC returned no en_US for the alias

interface SpanishLabelRow {
  alias: string;
  status: LabelRowStatus;
  enHtml: string | null;   // null until fetched
  esHtml: string;          // model output, possibly user-edited
  warnings: string[];
  raw: string | null;      // unvalidated model output (only on error)
  error: string | null;
  reasoning: string;       // translator's 1-3 sentence explanation
}

interface SpanishMigrationProject extends BaseProject {
  type: "spanish";
  dealerName: string;      // required so brand names stay untranslated
  labels: SpanishLabelRow[];
}
```

### 6.2 User steps

1. **Create project** — `SpanishProjectForm.tsx`: enter Dealer ID (slug) + Dealer Name
2. **Paste aliases** — paste blob of DDC label aliases into textarea
3. **Sanitize** — `POST /translations/sanitize` → clean alias array + dropped list
4. **Sequential translate loop** — for each alias:
   a. **Fetch EN** from DDC CMS (via `chrome.scripting.executeScript` into composer tab)
   b. **If not found** → status `not_found`, advance to next
   c. **Translate** via `POST /translations/translate`
   d. **Review** — card shows EN (collapsible), ES (editable textarea), warnings, reasoning (collapsible)
   e. **User action**: **Save** (POST back to DDC → status `saved`, auto-advance), **Skip** (status `skipped`, auto-advance), or **Retranslate** (re-run steps 4c-4e)
5. **Auto-advance** — saving or skipping a row triggers translation of the next `queued` row

### 6.3 Key components

| Component | Role |
|-----------|------|
| `SpanishPanelWorkflow.tsx` | Organism: paste input, counters, row list, orchestration |
| `LabelRow.tsx` | Molecule: one label card with EN preview, ES textarea, actions |
| `SpanishProjectForm.tsx` | Molecule: dealer ID + name form for new projects |
| `LabelAdapter.ts` | Adapter: BE calls via fetch, DDC calls via injected scripts |
| `LabelPort.ts` | Port interface: `sanitizeAliases`, `translateLabel`, `fetchLabel`, `saveLabel` |

### 6.4 DDC fetch/save (extension-side)

DDC calls must originate from the user's Chrome session. The adapter finds the composer tab by URL pattern (`*.website.dealercenter.coxautoinc.com/*`), then injects self-contained functions via `chrome.scripting.executeScript`:

- **`fetchLabel`** — `GET /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/labels/{slug}?alias={alias}` → `{ en, es }`
- **`saveLabel`** — `POST .../api/labels/{slug}/{alias}` with body `{ labelToSave: { en_US, es_US } }`

Injected functions have zero imports (per the project's `scripts/` rule).

---

## 7. LLM provider support

Three providers supported through `LLMPort` / `LLMFactory`:

| Provider | Adapter file |
|----------|-------------|
| Anthropic | `adapters/outbound/anthropic/anthropic_llm_adapter.py` |
| DeepSeek | `adapters/outbound/deepseek/deepseek_llm_adapter.py` |
| Gemini | `adapters/outbound/gemini/gemini_llm_adapter.py` |

Each adapter defines `translate_label_with_tools()` (with glossary_lookup + submit_translation tool definitions) and `judge_translation()` (with submit_verdict tool). Same prompt strings, different tool schemas per provider.

---

## 8. Key design decisions

1. **No batching.** Each label is translated and reviewed individually. The cost of one `/translate` call is small, and the user needs per-row review control.
2. **1 retry budget.** A trade-off: let the user hand-edit on persistent failure rather than spin through endless LLM attempts. Structural + semantic feedback from the failed attempt is shown as warnings.
3. **Browser is thin executor for DDC.** All DDC API calls (fetch label, save label) originate from the Chrome extension's user session. The backend never calls DDC directly.
4. **Glossary as tool, not inline prompt.** V2 replaced baking 69 glossary entries into the system prompt with a `glossary_lookup` tool call. Smaller prompts, scoped lookups, no hallucination risk from seeing the full glossary.
5. **LLM guardrail fails open.** If the judge LLM call throws, the translation passes through rather than blocking the pipeline. A misbehaving judge shouldn't halt progress.
6. **Dealer name in prompt.** Required so the LLM knows which brand name to leave untranslated (e.g. "Orange Buick GMC" → "Orange Buick GMC", not "Buick GMC Naranja").

---

## 9. File reference (complete map)

### BE — Domain
| File | Role |
|------|------|
| `src/domain/translations/glossary_es.csv` | 69-term EN→ES/MX glossary |
| `src/domain/translations/glossary_loader.py` | CSV loader with caching, prefers MexicanSpanish |
| `src/domain/translations/glossary_search.py` | `glossary_search(terms)` — exact-match lookup |

### BE — Application
| File | Role |
|------|------|
| `src/application/translate_labels/translate_labels_graph.py` | LangGraph wiring (1-node linear graph) |
| `src/application/translate_labels/translate_label_node.py` | Core node: translate → validate → judge → retry |
| `src/application/translate_labels/validator.py` | Structural validator (tag/href/variable checks) |

### BE — Adapters
| File | Role |
|------|------|
| `src/adapters/inbound/http/translations_router.py` | `POST /translations/sanitize` + `/translate` |
| `src/adapters/inbound/http/translations_dtos.py` | Pydantic request/response DTOs |
| `src/adapters/outbound/prompts.py` (lines 630-742) | System prompts: translator V1/V2 + judge |
| `src/adapters/outbound/anthropic/anthropic_llm_adapter.py` | Anthropic tool definitions + translate method |
| `src/adapters/outbound/deepseek/deepseek_llm_adapter.py` | DeepSeek equivalents |
| `src/adapters/outbound/gemini/gemini_llm_adapter.py` | Gemini equivalents |

### BE — Tests
| File | Role |
|------|------|
| `tests/test_translate_label_node.py` | Node unit tests (happy path, retry, guardrail) |
| `tests/test_glossary_search.py` | Glossary search unit tests |

### FE — Types
| File | Role |
|------|------|
| `src/store/types.ts` (lines 67-136) | `LabelRowStatus`, `SpanishLabelRow`, `SpanishMigrationProject` |
| `src/types/index.ts` (lines 348-405) | `TranslateLabelRequest/Response`, `DDCLabelFetchResult`, `DDCLabelSaveResult` |

### FE — Services
| File | Role |
|------|------|
| `src/services/ports/LabelPort.ts` | Port interface |
| `src/services/adapters/LabelAdapter.ts` | BE calls + DDC injected scripts |

### FE — Components
| File | Role |
|------|------|
| `src/components/organisms/SpanishPanelWorkflow/SpanishPanelWorkflow.tsx` | Main workflow: paste → sanitize → translate loop |
| `src/components/molecules/LabelRow/LabelRow.tsx` | Per-label card: EN/ES display, save/skip/retranslate |
| `src/components/molecules/SpanishProjectForm/SpanishProjectForm.tsx` | New-project creation form |

### FE — Store
| File | Role |
|------|------|
| `src/store/useMigrationStore.ts` | Zustand store: `spanishProjects` array + actions |

---

## 10. Risks & open questions

| Risk | Mitigation |
|------|------------|
| LLM produces structurally broken HTML | Structural validator catches tags/hrefs/variables; 1 retry with feedback |
| LLM translates brand/model names | Prompt explicitly forbids it; dealer name injected as context |
| DDC composer tab not found or not logged in | `LabelAdapter` surfaces clean error; user sees "DDC fetch failed" per row |
| Glossary grows stale (new automotive terms emerge) | CSV is the single source of truth; adding a row = one-file edit |
| Judge rejects acceptable translations | Fails open; pedantic-averse prompt; user can still manually save `error`-status rows |
| Provider not configured | `/translate` returns `status: "error"` with provider message; FE surfaces it |
