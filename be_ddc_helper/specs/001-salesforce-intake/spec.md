# Salesforce Intake SDD

**Status:** PARTIALLY IMPLEMENTED - Phase 0 spike done (2026-06-09).
**Date:** 2026-06-09 (rev 3)
**Replaces:** Manual data entry on the GM Prebuild / GM BuySell flows.

**Rev 3 changes vs. rev 2 - MAJOR architectural simplification:**
- **Phase 0 spike succeeded.** Salesforce's public UI API (`/services/data/v66.0/ui-api/...`) returns all 4 reads with just session-cookie auth, from a single Lightning tab.
- ❌ **DELETED:** aura endpoint replay, `fwuid`/`appContextId`/`aura.token` lifting, csrf/Visualforce-signing-token scraping, apexremote calls, two-tab orchestration (board tab + apex VF tab).
- ✅ **NEW §5.1:** 4 parallel-friendly UI API GETs from a single tab.
- ⏱️ **Phase 1 shrinks** from "browser primitives suite" to a single thin `sfUiApiFetch` helper.
- 🧪 Spike files (`scripts/sfIntakeSpike.ts`, `services/salesforceSpike.ts`, `SfIntakeSpikeModal.tsx`, flask button) stay until Phase 3 ships and are deleted then.

**Rev 2 changes (still in effect):**
- Prebuild/BuySell classification by LLM (§5.3).
- Form is a breadcrumb stepper with editable result fields (§4.1, §7).
- BuySell + Prebuild share `GMSetupBlock`; Prebuild adds the existing pages flow (§8).
- Smart Title Case for addresses.
- Assume specialist is logged in.
- Rate-limiting strategy (§11).

---

## 1. Goal

Replace the current GM Prebuild / BuySell forms (which ask the user for `dealerId`, `baseUrl`, `navHtml` - and conceptually require the user to manually look up name, address, leads email, design JSON, PPR) with **a single Salesforce Board URL input**. The system then derives every required field by replaying the same 4 Salesforce calls the user does by hand today.

**Anti-goal:** do NOT make Salesforce calls from the Python backend. SF/Aura endpoints are tied to a session cookie + CSRF token + Visualforce signing key issued to a logged-in browser; calls from a server IP without that context risk being blocked or breaking silently on token rotation. Instead, the backend orchestrates and the **browser is the thin executor** - exact same pattern already used for DDC CMS calls (see `be_ddc_helper` WS-RPC bridge + `WSClientAdapter` in `fe_ddc_helper`).

---

## 2. Why this design (vs. the current form)

Today's pain (described by user):

1. User receives a SF board link.
2. Manually clicks **Insights** → opens the **DDC Client Onboarding Questionnaire** insight.
3. Reads each questionnaire row and copies values out: dealership name, address (and applies sentence case), leads email, primary URL, design choice.
4. Determines buy/sell vs. new from a flag inside the questionnaire.
5. Navigates to a separate Precursive Project page to read **PPR** and **dealer ID** (extracted from `DDC-{dealerId}`).
6. Pastes everything into our form.

The reverse-engineering (see `C:\Users\Ale-CodeRoad\Desktop\Brain\Salesforce Automation Research\*`) shows all of this is reachable via 4 chained POSTs from a logged-in tab. The work becomes mechanical → automatable. Last gap = the **design choice**: sometimes it's a clean JSON pasted by the dealer, sometimes it's prose. Prose → human-in-the-loop fallback (see §6).

---

## 3. Architecture overview

```
+--------------------+        WS RPC         +-------------------------+
|  ddc-migration-    |  tool_call / result   |  fe_ddc_helper   |
|  agent (FastAPI)   | <-------------------> |  (Chrome extension)     |
|                    |                       |                         |
|  /salesforce/      |                       |  SalesforceAdapter:     |
|  intake orchestr.  |                       |   - openSfTab(boardUrl) |
|  state machine     |                       |   - sfFetch(req)        |
|  parser            |                       |   - closeSfTab()        |
+--------------------+                       +-------------------------+
        |                                              |
        | derives dealer bundle                        | issues fetch() from
        v                                              | MAIN-world script
+--------------------+                                 v
|  Dealer Bundle DTO |               +-----------------------------------+
|  (returned to FE)  |               |  casfx.lightning.force.com        |
+--------------------+               |  casfx--taskfeed1.vf.force.com    |
                                     +-----------------------------------+
```

Key principle: **Python decides what call to make next; Chrome makes it.** The browser holds the session, the CSRF token, and the Visualforce remoting signature - none of which need to leak to the backend.

---

## 4. Replacements in the existing form

### 4.1 Form becomes a breadcrumb stepper

`GMProjectForm.tsx` is replaced by a 3-step wizard component (rename → `GMIntakeWizard`). The Prebuild / BuySell toggle is removed - classification is decided by the LLM in step 2 (see §5.3).

**Step 1 - Salesforce link**

| Field | Validation |
|-------|------------|
| `salesforceBoardUrl` | matches `^https://casfx\.lightning\.force\.com/lightning/r/taskfeed1__Board__c/[a-zA-Z0-9]+/view$` |

Submit → kicks off `POST /salesforce/intake` and advances to step 2.

**Step 2 - Loading / live progress**

Streams backend phase status: opening tab → calls 1+3 (parallel) → calls 2+4 → parse → classify. Use the same status pill UX as the migration flow. Cancellation supported (same `AbortController` pattern as analyze/execute, see [[project-architecture]] § Cancellation).

**Step 3 - Editable result**

Top of card: a `<h2>` reading either **"GM Prebuild - {dealershipName}"** or **"GM BuySell - {newDealershipName ?? dealershipName}"** based on LLM verdict (§5.3). A subtle pill next to it shows classification confidence + an "override" affordance for the rare case the user disagrees.

Two **field groups** (cards), each with one "Verify in Salesforce ↗" link rather than per-field links:

| Card | Link target | Editable fields |
|------|-------------|-----------------|
| **Questionnaire** | `https://casfx.lightning.force.com/lightning/r/taskfeed1__Board_Insight__c/{questionnaireInsightId}/view` | dealershipName, newDealershipName *(BuySell only)*, dealershipAddress, leadsEmail, primaryUrl, designChoice |
| **Precursive Project** | `https://casfx.lightning.force.com/lightning/r/preempt__PrecursiveProject__c/{precursiveProjectId}/view` | ppr, dealerId |

Every field is **pre-filled and editable**. Fields the backend couldn't resolve come back as `"-"` (literal dash); user can type over. Validation runs on the form, not on the intake response - backend always returns something.

Footer buttons: `Back` · `Reset` · `Create project`. On `Create project`:
- If `isBuySell` → navigate to `GMBuySellFlowPanel` (see §8.1).
- Else → navigate to `GMPrebuildFlowPanel` (see §8.2).

### 4.2 Backend change

`be_ddc_helper/src/adapters/inbound/http/` gains a new router:
- `salesforce_router.py` → `POST /salesforce/intake { boardUrl }` → returns `DealerBundleDTO` (see §7).

Same WS-RPC bridge pattern as `execute_router` → `MigrationExecutor`. New orchestrator:
- `application/salesforce/intake_orchestrator.py` - `SalesforceIntake` class, 4 step methods.
- `application/salesforce/questionnaire_parser.py` - pure parsing.
- `application/salesforce/bundle_dtos.py` - DTOs (DealerBundle, QuestionnaireRow, etc.).

---

## 5. Pipeline (4 GETs + 1 parse + 1 LLM classify)

### 5.1 Calls - single Lightning tab, public UI API

All 4 reads are plain `GET` against Salesforce's public UI API. The browser fetches with `credentials: 'include'` from the Lightning origin; the session cookie (`sid`) is auto-attached. No `fwuid`, no `aura.token`, no csrf, no Visualforce signing key, no apexremote, no second tab.

`BASE = https://casfx.lightning.force.com` · `API = /services/data/v66.0/ui-api`

| Step | UI API endpoint | Input | Extract |
|------|-----------------|-------|---------|
| 1 | `GET {BASE}{API}/related-list-records/{boardId}/taskfeed1__Board_Insights__r?fields=taskfeed1__Board_Insight__c.Id,taskfeed1__Board_Insight__c.Name&pageSize=10` | `boardId` | Pick the record whose `Name == "DDC Client Onboarding Questionnaire"` (fallback: first record) → `Id.value` → `questionnaireInsightId` |
| 2 | `GET {BASE}{API}/records/{questionnaireInsightId}?fields=taskfeed1__Board_Insight__c.taskfeed1__Description__c,taskfeed1__Board_Insight__c.Name` | `questionnaireInsightId` | `taskfeed1__Description__c.value` → raw questionnaire blob |
| 3 | `GET {BASE}{API}/records/{boardId}?fields=taskfeed1__Board__c.psx__Project__c,taskfeed1__Board__c.Name,taskfeed1__Board__c.taskfeed1__Type__c` | `boardId` | `psx__Project__c.value` → `precursiveProjectId` |
| 4 | `GET {BASE}{API}/records/{precursiveProjectId}?fields=preempt__PrecursiveProject__c.Project_ID__c,preempt__PrecursiveProject__c.Product_Fulfillment_Account__r.Name,preempt__PrecursiveProject__c.Name` | `precursiveProjectId` | `Project_ID__c.value` → `ppr` ; nested `Product_Fulfillment_Account__r.value.fields.Name.value` → strip `DDC-` prefix → `dealerId` |

Dependency graph (= concurrency plan):

```
boardId ──┬──> step1 ──> step2
          └──> step3 ──> step4
```

Steps 1 & 3 fire in parallel from `boardId`. As each resolves, its dependent (2 or 4) fires immediately. End-to-end is ~2 round trips, not 4. Validated by the Phase 0 spike on the McElveen Buick GMC board (all 4 returned 200 + extracted values match the research docs).

### 5.1.1 Why this works (vs. what we feared)

The aura endpoints in the research curls are Lightning's *internal* RPC channel - they require the `fwuid` + `aura.token` because Lightning treats them as authenticated framework actions. The UI API at `/services/data/vXX.X/ui-api/...` is the **same data, public surface**, auth'd by the user's session cookie alone. Same origin → cookie flows automatically with `credentials: 'include'`.

In particular: the apexremote call in the research was used to read `psx__Project__c` from the Board record. But `psx__Project__c` is just a field on the Board record - readable directly via `GET .../records/{boardId}?fields=taskfeed1__Board__c.psx__Project__c`. The apexremote path was the only one the user happened to capture; the UI API path is simpler and was confirmed by the spike.

### 5.2 Parser (step 5 - Python)

`questionnaire_parser.py` works on the `taskfeed1__Description__c` blob:

- Lines are `\r\n`-separated.
- Each line is `Key\t\tValue` (double tab). Some lines have `\t` then value; treat any run of tabs as the delimiter.
- Build a `dict[str, str]` keyed by the (canonicalized) question label.

Field-by-field normalizers (deterministic, no LLM):

| Bundle field | Source row label | Normalizer |
|--------------|------------------|------------|
| `dealershipName` | `Dealership Name:` | trim |
| `dealershipAddress` | `Dealership Address:` | trim → **Title Case** (each word capitalized, "Sentence Case" in user's terminology - clarify in §9.4); preserve commas |
| `leadsEmail` | `Leads Email:` | trim, lowercase |
| `primaryUrl` | `Primary URL/Domain:` | trim, ensure `https://` prefix |
| `designChoice` | `Design Choice:` | `json.loads` → if success → `parsed`; if fail → flag `needsHumanDesign=True`, keep raw text |
| `newDealershipName` | LLM-extracted (see §5.3) | only set when LLM classifies as BuySell |

`isBuySell` is **not** parsed deterministically - that classification is delegated to the LLM (§5.3). Backend then merges parser output with LLM verdict and steps 1+3+4 data → `DealerBundleDTO`.

### 5.3 LLM classifier (Prebuild vs. BuySell)

Why LLM here when everything else is deterministic? Field labels in the questionnaire drift across boards ("old name" / "previous name" / "former dealership", etc.), and the official `Is this a Buy/Sell` row is sometimes blank or contradicted by the body of the description. A regex-and-rules classifier would need constant maintenance; an LLM with a one-paragraph prompt handles drift naturally and is a single cheap call.

**Inputs:** the full parsed questionnaire dict (already extracted in §5.2).

**Prompt (sketch):**

> A DDC client onboarding questionnaire is either for a **Prebuild** (a brand-new website for an existing dealership) or a **BuySell** (a dealership that was just bought by a different owner, replacing an existing site). BuySells almost always include fields naming the *previous/old/former* dealership and/or owner alongside the *new* dealership name. Prebuilds don't have those fields. Classify this questionnaire and, if BuySell, also return the new dealership name.

**Output (JSON-mode):**

```json
{
  "classification": "prebuild" | "buysell",
  "confidence": 0.0-1.0,
  "reasoning": "one short sentence",
  "newDealershipName": "..." | null   // only when classification = buysell
}
```

**Model choice:** light tier per provider - same models already used for HTML beautification (DeepSeek `deepseek-chat`, Anthropic `claude-haiku-4-5`, Gemini `gemini-2.0-flash`). Single call, ~500 input tokens, ~80 output. Cost is negligible.

**Failure mode:** if LLM call fails or returns non-JSON, default to `classification: "prebuild"`, `confidence: 0`, `newDealershipName: null`, and surface a banner on step 3 prompting the user to confirm/override. Never block the intake.

**Override:** FE shows the LLM verdict with an inline switch so the user can flip Prebuild↔BuySell. The wizard title and the routed flow panel both reflect the final (user-confirmed) value.

Backend then merges parser output with LLM verdict and steps 1+3+4 data → `DealerBundleDTO`.

---

## 6. Human-in-the-loop: design JSON

When `designChoice` row is not valid JSON, the FE flow:

1. Shows the raw description text in a modal.
2. Provides a `<textarea>` for the user to paste a valid JSON design.
3. Validates with `JSON.parse` + a (yet to be defined) shape check.
4. Resumes the create-project action.

No translator agent is wired in this pass. Future: a separate skill/agent can ingest the prose description and propose a JSON; out of scope for v1.

---

## 7. Data model

Every string field in the `bundle.*` block is **always a string** - when the backend can't resolve it, the value is the literal `"-"`. The FE never has to handle `null/undefined` for these; it just shows the dash and lets the user type over. Structured fields (`designChoice`, `classification`) keep their object shape.

```ts
// FE - mirrored in Pydantic on BE
interface DealerBundle {
  // From step 4 (PPR card on FE)
  ppr: string;                    // "PPR-340445" | "-"
  dealerId: string;               // "mcelveenbgmc" | "-"

  // From questionnaire parse - step 2 (Questionnaire card on FE)
  dealershipName: string;         // "" never; "-" if missing
  newDealershipName: string;      // "-" when prebuild
  dealershipAddress: string;      // Title-cased
  leadsEmail: string;
  primaryUrl: string;
  designChoice:
    | { kind: 'json'; value: unknown }
    | { kind: 'description'; raw: string; needsHumanInput: true }
    | { kind: 'missing' };

  // LLM classification (§5.3)
  classification: {
    value: 'prebuild' | 'buysell';
    confidence: number;            // 0..1, 0 when LLM failed
    reasoning: string;             // "" on failure
    source: 'llm' | 'user-override';
  };

  // Provenance - used for the two "Verify in Salesforce ↗" links + debugging
  source: {
    boardId: string;
    questionnaireInsightId: string;
    precursiveProjectId: string;
    fetchedAt: string;             // ISO timestamp
  };
}
```

Derived (computed in FE, not stored):
- `isBuySell = classification.value === 'buysell'`
- `displayName = isBuySell ? newDealershipName : dealershipName`
- Questionnaire link = `…/lightning/r/taskfeed1__Board_Insight__c/{source.questionnaireInsightId}/view`
- Project link = `…/lightning/r/preempt__PrecursiveProject__c/{source.precursiveProjectId}/view`

---

## 8. Flow panels after Create project

The "Create project" button in step 3 of the wizard branches the user into one of two organisms. Both share the **GM Setup Block** - a small read-only header that displays the bundle data (name, dealer ID, PPR, address, leads email, primary URL, design) with the two "Verify in Salesforce ↗" links. This is the part the two flows share; everything below it diverges.

```
GMSetupBlock  ← shared organism (BuySell + Prebuild)
  ├── header: classification + displayName + status
  ├── two info cards (Questionnaire / Precursive Project) with verify links
  └── quick-access buttons:
        - CMS:           https://{dealerId}.cms.dealer.com
        - Dealer Center: https://apps.dealercenter.coxautoinc.com/landing/dealer/{dealerId}/dashboard
```

### 8.1 `GMBuySellFlowPanel`

Two-column layout:

```
┌───────────────────────────────────────────────────────────┐
│  GM BuySell - {newDealershipName}                         │
├──────────────────────────────────┬────────────────────────┤
│  LEFT (flex-1)                   │  RIGHT (w-72)          │
│                                  │                        │
│  <GMSetupBlock />                │  [Execute BuySell      │
│                                  │   Automation]          │
│                                  │   ↑ disabled, "Coming  │
│                                  │     soon" tooltip      │
└──────────────────────────────────┴────────────────────────┘
```

The BuySell automation itself is **out of scope for this SDD** - placeholder button only.

### 8.2 `GMPrebuildFlowPanel`

Reuses the existing `MigrationFlowPanel` page-migration flow (nav HTML → page list → migrate). New layout:

```
┌───────────────────────────────────────────────────────────┐
│  GM Prebuild - {dealershipName}                           │
├───────────────────────────────────────────────────────────┤
│  <GMSetupBlock />                                         │
├───────────────────────────────────────────────────────────┤
│  <PageMigrationFlow />   ← current MigrationFlowPanel,    │
│                            unchanged behavior             │
└───────────────────────────────────────────────────────────┘
```

The page-migration flow continues to need `navHtml` until §9.1 is resolved - that field is collected inside `PageMigrationFlow`, not in the intake wizard.

**Rationale:** Prebuild and BuySell share the *initial setup* (dealer identity + access links). BuySell ends there; Prebuild continues with page work. Sharing `GMSetupBlock` keeps the BuySell dashboard from feeling like a stub of Prebuild - they're both built from the same primitive.

---

## 9. Phases

Each phase is shippable and verifiable independently.

### Phase 0 - UI API spike - ✅ DONE (2026-06-09)

Validated UI API works for all 4 reads against McElveen board. Temp files (delete with Phase 3):
- `fe_ddc_helper/src/scripts/sfIntakeSpike.ts`
- `fe_ddc_helper/src/services/salesforceSpike.ts`
- `fe_ddc_helper/src/components/molecules/SfIntakeSpikeModal/SfIntakeSpikeModal.tsx`
- flask 🧪 button in `ProjectListPage` header

### Phase 1 - Promote spike into proper FE service (small)

Now that we know the approach works, the FE side collapses to ~1 file:

- `services/salesforce/sfUiApiFetch.ts`: thin helper that takes a Lightning origin + a UI API path, fetches with `credentials: 'include'`, returns parsed JSON or throws a typed error (`SfAuthError` for 401/403, `SfNotFoundError` for 404, `SfError` otherwise).
- WS-RPC tool registered: `sf.uiApiGet(path)` - backend dispatches a GET, browser executes, returns JSON. Single tool, not four.
- The 4 endpoints from §5.1 become 4 backend-defined paths, NOT 4 separate browser primitives. Browser stays generic.
- Adapter `SalesforceAdapter` opens/finds the Board tab once at intake start, holds the tab id, dispatches each `sf.uiApiGet` against it. Closes nothing - leaves the tab open per §11.

### Phase 2 - Backend orchestrator + parser + LLM classifier

- New `adapters/inbound/http/salesforce_router.py` (thin) → `POST /salesforce/intake`.
- `application/salesforce/intake_orchestrator.py` - `SalesforceIntake` class, steps 1+3 in parallel, then 2+4, then parse, then classify.
- `application/salesforce/questionnaire_parser.py` - pure dict parser + normalizers; full unit-test coverage using the McElveen blob captured in research.
- `application/salesforce/classifier.py` - calls the LLM via existing `LLMFactory`. Uses light-tier model. Falls back to `prebuild + confidence=0` on any error.
- `application/salesforce/bundle_dtos.py` - DTOs.
- All `"-"` defaulting happens in the orchestrator at response-build time, NOT in the parser. Parser returns optional strings; orchestrator coalesces.

### Phase 3 - FE intake wizard

- New organism `GMIntakeWizard` (3-step stepper) replaces `GMProjectForm` usage. Delete `GMProjectForm` once nothing imports it.
- New molecules: `IntakeStepLink`, `IntakeStepLoading`, `IntakeStepReview`.
- New molecule `BundleFieldCard` - generic card with header + verify-link + editable fields list. Reused for Questionnaire card and Project card.
- Streamed progress in step 2 reuses the WS message bus already used by analyze/execute.
- Cancellation wired through (`AbortController` pattern from S3.2).

### Phase 4 - Flow panels + GMSetupBlock

- New molecule `GMSetupBlock` (the shared header).
- New organism `GMBuySellFlowPanel` with the right-column placeholder button.
- New organism `GMPrebuildFlowPanel` wrapping `GMSetupBlock` + the existing migration flow content.
- Routing in `ProjectPage` updates to dispatch on `classification.value`.

### Phase 5 - End-to-end verify

- Prebuild: run against the McElveen Buick GMC board (the one in the research docs).
- BuySell: run against an actual BuySell board (user provides URL).
- Validate Title Case rules vs. user expectation (§10.4).
- Validate LLM classifier on at least 5 boards of each kind (track confidence distribution).

### Phase 6 - Follow-ups (out of scope for v1)

- Design JSON translator agent (LLM that converts prose → JSON).
- Intake cache (skip the 4 calls if same `boardId` was intaken in last N minutes).
- BuySell automation behind the "Execute BuySell Automation" button.
- Multi-rooftop questionnaires (the "Other DDC Websites" question hints these exist).

---

## 10. Open questions

### 10.1 Where does `navHtml` come from now? - DEFERRED

The current GM form requires nav HTML pasted from the source dealer site, used downstream to enumerate pages to migrate. The questionnaire does NOT contain this. **Decision: keep manual paste inside `GMPrebuildFlowPanel` for v1.** The intake wizard does not collect nav HTML. v2 may auto-fetch via the existing skeleton extractor pointed at `primaryUrl`.

### 10.2 ~~`aura.context` / `fwuid` / `appContextId` stability~~ - CLOSED

Rev 3: no longer relevant. UI API doesn't use any of these. Token rotation is now a non-issue.

### 10.3 LLM classifier prompt drift

The classifier prompt in §5.3 is a sketch. Tuning required during Phase 5 - track confidence on real boards, adjust wording until 0.85+ confidence is the norm for clean inputs. Edge: questionnaires where the dealership is BOTH a BuySell AND a relocation - out of scope, classify as BuySell.

### 10.4 "Sentence Case" → smart Title Case - CONFIRMED

Rule: capitalize each word's first letter, lowercase the rest, EXCEPT preserve all-caps tokens ≤3 chars (state codes like `SC`, `NC`, `USA`). Implementation: a tiny `smart_title_case(s)` helper in the parser module. Override set starts as `{"USA", "DDC", "GM", "GMC"}` and is extensible.

### 10.5 LLM provider availability

The classifier requires an LLM provider already configured (same `LLMFactory` as the migration flow). If the user hits intake before configuring a key, the orchestrator falls back to `classification: prebuild, confidence: 0` and the FE banner reads "LLM not configured - please confirm classification manually". Same model preference order: DeepSeek → Anthropic → Gemini.

### 10.6 Closed: SF login state

ASSUMED - implementation specialists are always logged in. Adapter still detects a login redirect on the opened tab and surfaces a clean "log in to Salesforce and retry" error, but this is the unhappy-path UX, not the design center.

---

## 11. Rate-limiting strategy

User asked specifically about this. Mitigations, in order of effectiveness:

1. **On-demand only.** Intake fires only when the user clicks `Continue` on step 1. No polling, no background fetches, no retries on hover.
2. **One in-flight per session.** The wizard disables the submit button while an intake is in progress. Backend rejects a second concurrent `POST /salesforce/intake` from the same WS session with 409.
3. **Tab reuse, not tab spam.** `sfTab.openTab` finds an existing `casfx.lightning.force.com` tab and reuses it; only opens a new one if none exists. Same applies to the VF iframe - wait for the existing one, don't force a reload.
4. **Cooldown.** If a board was intaken in the last 60s and the user re-submits the same URL, return the cached `DealerBundle` from a per-session in-memory dict instead of replaying the 4 calls. Cache key = `boardId`. Bypass via a `?fresh=1` flag for debug.
5. **Backoff on `state: "ERROR"`.** If aura returns `ERROR` or apexremote returns non-200, surface to FE immediately AND wait 30s before allowing another intake from the same session. Prevents thrashing on a flagged session.
6. **No parallel beyond what's necessary.** §5.1 says steps 1+3 can be parallel - keep it at 2 concurrent, never more. Steps 2 and 4 are strictly sequential after their dependency.

This is enough for the expected throughput (a specialist intakes a handful of boards a day). If SF starts pushing back even at this rate, we add jitter and per-user daily caps.

---

## 12. Risks

| Risk | Mitigation |
|------|------------|
| UI API field name changes (managed-package upgrade) | Field names in §5.1 wrapped in a `FIELDS` constant in the backend orchestrator → one-file fix; integration test in Phase 5 catches it on the McElveen board |
| ~~VF iframe not loaded~~ | N/A in rev 3 (apex path deleted) |
| User's SF tab is not logged in | Detect login redirect; FE surfaces a "log in to SF and retry" CTA |
| Questionnaire row labels change | Parser is keyed by exact strings - wrap in a `LABELS` constant so future schema drift is a one-file fix |
| Design JSON shape varies across OEMs | v1: just validate JSON parses; v2: schema validation |

---

## 13. What gets deleted

Nothing yet - this is planning only. Once Phase 3 ships:

- `GMProjectForm` molecule (and its zod schema) - replaced by `GMIntakeWizard`.
- Prebuild/BuySell toggle UI - variant is auto-classified now.
- `dealerId` / `baseUrl` form fields disappear from the intake step (still present in the page-migration flow inside `GMPrebuildFlowPanel` until §10.1 is resolved, but populated from the bundle rather than user-typed).

---

## 14. References

- Research notes: `C:\Users\Ale-CodeRoad\Desktop\Brain\Salesforce Automation Research\*.md`
  - `Client Questionnaire ID Discovery.md` - step 1
  - `Client Questionnaire - Extract Actual Questionaire.md` - step 2 + raw blob shape
  - `Get PPR Guide.md` - step 3
  - `Getting our PPR code and dealer ID.md` - step 4 + extraction
- Existing precedent: `BACKEND_REFACTOR_SDD.md` (execute pipeline refactor) - same SDD format + phase gating.
- Existing precedent: WS-RPC bridge - `application/migration/execute_orchestrator.py` (browser-as-executor pattern).
