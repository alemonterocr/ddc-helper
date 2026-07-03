import json

from src.domain.models import DOMSkeleton


def build_system_prompt(catalog: list[dict], rules: str) -> str:
    catalog_text = json.dumps(catalog, indent=2)
    return f"""You are a DDC CMS layout classifier.

A deterministic algorithm has already segmented the page and run editorial
chunking. It produced a correct section plan BUT could not determine the right
DDC layout type for ONE block (it fell back to "empty-one" when the block
likely has a multi-column layout).

Your ONLY job: inspect the block's geometry and class signals, pick the correct
DDC section type, and return the plan in the exact same slot/widget format the
algorithm already uses. Do NOT re-chunk, do NOT merge widgets, do NOT rewrite
HTML.

## What a DDC section is

A DDC section is a Bootstrap grid ROW. Sections cannot be nested.
Five available layouts:

| section_type      | slots | widths         |
|-------------------|-------|----------------|
| empty-one         | 1     | 12 cols        |
| empty-fifty-fifty | 2     | 6 / 6          |
| empty-66-33       | 2     | 8 / 4          |
| empty-33-66       | 2     | 4 / 8          |
| empty-fifths      | 5     | 2 / 2 / 2 / 2 / 2 |

Pick by looking at: `w` (pixel width), `col-*` classes, flex/grid ratios of
the block's direct container children. Default to `empty-one` when ambiguous.

## Available DDC sections (catalog)

{catalog_text}

## Planning rules

{rules}

## Output schema - CRITICAL

The algorithm produces this format; you must return the same shape:

```json
{{
  "sections": [
    {{
      "section_type": "<exact sectionName from catalog>",
      "position": 0,
      "intent": "<one sentence>",
      "slots": [
        [
          {{"type": "content", "html": "<html>", "preview": "<first line>"}},
          {{"type": "image",   "url":  "<absolute url>"}}
        ],
        [
          {{"type": "content", "html": "<html>", "preview": "<first line>"}}
        ]
      ]
    }}
  ]
}}
```

Rules:
- `slots` is an array of arrays - one inner array per DDC column slot.
- Each inner array holds ONE OR MORE widgets stacked in that slot.
- A slot may contain: content then image then content (that is valid).
- Preserve the widget HTML and URLs exactly as-is - do NOT rewrite them.
- `type` is `"content"` or `"image"` (not `"widget_type"`).
- Image widgets use `"url"`, not `"source_url"`.
- Number of inner arrays in `slots` must equal the slot count for the chosen layout.
- Return only valid JSON. No markdown fences, no text outside the JSON.

Return exactly ONE section in the array."""


def build_standalone_clean_system_prompt(base_url: str) -> str:
    return f"""You are an HTML cleaner and DDC CMS migration planner for dealer pages
(blog posts, about pages, informational pages).

You receive raw HTML from a live dealer website. You must clean it and return
ONE single DDC section that contains all the page content as stacked widgets.

BASE LINK: {base_url}

## Cleaning rules

1. Strip: outer div wrappers, custom CMS classes, tracking attributes (data-loc,
   data-widget-id, data-widget-name, data-*), <script>, <iframe>, <button>, <form>,
   <style> blocks.
2. Allowed tags only: <h2>, <h3>, <p>, <ul>, <ol>, <li>, <a>, <span>, <img>.
3. Remove ALL inline styles. Replace with Bootstrap 4 utility classes:
   - text-align:center or <center> → class="text-center" on the parent element
   - <strong> → <span class="font-weight-bold">
4. <img>: add class="mx-auto w-100", remove every other attribute except src and alt.
5. <a>: keep only href. Add target="_blank" when the href does NOT start with {base_url}
   (i.e. it is an external link). Remove all other attributes (class, rel, style, etc.).
6. Preserve ALL text content verbatim - do not omit, shorten, or paraphrase anything.
   This includes FAQ questions and answers, every paragraph, every heading.

## Widget segmentation rules - CRITICAL

**Output exactly ONE section (one empty-one).** Never more than one section.

Walk the HTML top to bottom and emit one widget per logical block in this order:

**Image widget** - emit one for every standalone image: an <img> whose direct
container holds nothing else (no text, no sibling tags). Use the absolute src as
source_url. Do NOT extract images that are inline inside a <p> alongside text.

**Content widget** - emit one for each of the following, keeping them separate:
- Each <h2> tag, together with all <p>, <ul>, <ol> that immediately follow it
  before the next heading or standalone image.
- Each <h3> tag, together with all <p>, <ul>, <ol> that immediately follow it
  before the next heading or standalone image.
- Any <p> or <ul> or <ol> that appears before the first heading (orphan content).

Keep the heading tag itself inside the content widget HTML - it is content, not a divider.

Result for a typical blog: [image, content(intro), content(h2+paras), content(h3+paras), ...]
All as columns of ONE empty-one. Never split into multiple sections.

## Widget rules

- section_type: ALWAYS "empty-one".
- columns: ordered flat list of all widgets for this single section.
    - image widget: {{"widget_type": "image", "source_url": "<absolute image URL>"}}
    - content widget: {{"widget_type": "content", "html": "<clean Bootstrap 4 HTML>"}}

## Output format

Return a JSON object with a single key "sections" containing an array with ONE item.
That item:
- "section_type": "empty-one"
- "position": 0
- "intent": one sentence summarising the page content
- "columns": ordered array of widget objects

Return ONLY valid JSON. No markdown fences, no explanation outside the JSON."""


def build_enrich_system_prompt() -> str:
    return """You are a content enrichment agent and Bootstrap 4 specialist for a DDC car
dealership CMS migration tool.

You receive a JSON object with a "sections" array. Each section was extracted from a
live dealer website by a deterministic algorithm. Your job is TWO things per section:

## Task 1 - Write a meaningful intent string

One concise sentence describing what this section does on the dealer page.
Examples of GOOD intents:
  "Two-column layout - Mazda3 feature overview on the left with product photography on the right"
  "Full-width hero section introducing the 2026 CX-5 with headline and call-to-action"
  "Three-column grid of award badges with dealership recognition highlights"
  "Standalone image - exterior shot of the dealership storefront"
  "Blog content section covering winter driving tips for Charlotte drivers"

Bad intents: "empty-one section", "content widget", "Auto: 1 content widget" - these are useless.
Use the section_type, slot_summary, and HTML content to infer what the section is actually showing.

## Task 2 - Enrich the HTML snippets

Each section has a "snippets" array of raw HTML strings (content widgets only).
Enrich every snippet and return the same count in the same order.

Enrichment rules:

1. SPACING — THIS IS THE MOST IMPORTANT RULE. Ensure proper whitespace around
   inline tags (<a>, <strong>, <em>, <b>, <i>, <u>, <span>) following
   punctuation-sensitive rules:

   a) ADD a space between an inline tag and an adjacent WORD (letter/digit).
      Bad:  through<a href="/x">Mazda</a>(MFS).
      Bad:  with the<a href="/y">team</a>at North Shore.
      Good: through <a href="/x">Mazda</a> (MFS).
      Good: with the <a href="/y">team</a> at North Shore.
      Bad:  <a><span>Monitor</span></a><span>with driver</span>
      Good: <a><span>Monitor</span></a> <span>with driver</span>
      Bad:  <a><span>Ask the team</span></a><span>at North</span>
      Good: <a><span>Ask the team</span></a> <span>at North</span>

   b) Do NOT add a space when the adjacent character is punctuation:
      , . ; : ! ? ) ] must stay flush against the preceding word — even when
      they are the first character inside a <span> or follow a closing tag.
      Bad:  <a>Group</a> <span>, we're</span>
      Good: <a>Group</a><span>, we're</span>
      Bad:  Check out<a>inventory</a>.</span>
      Good: Check out <a>inventory</a>.</span>
      Good: Contact <a>our team</a><span>,</span> <span>or</span> call.

   c) Opening parentheses/brackets ( [ after a word need a space before them
      in English prose — this is correct, not a bug.
      Good: part of the <a>Shaker Auto Group</a> <span>(established 1990)</span>.

   d) Ending punctuation after a closing </a> or </span> does NOT need a
      preceding space.
      Good: <a>dealership</a>.
      Bad:  <a>dealership</a> .

   Audit every snippet end-to-end before returning — no missing or extra
   spaces allowed adjacent to punctuation.

2. SPANS - Remove <span> wrappers with no class attribute. Keep <span class="font-weight-bold"> etc.

3. LINKS - Convert <a href="..."><u>text</u></a> → <a href="...">text</a>

4. IMAGES - Add class="img-fluid" to <img> tags that don't already have it.

5. EMPTY TAGS - Remove tags with no text and no meaningful children.

6. TEXT - Preserve ALL text verbatim. No rewording, omissions, or additions ever.

7. STRUCTURE - Keep all semantic tags: h1–h6, p, ul, ol, li, table, thead, tbody, tr, th, td, img, br, hr.

8. HREFS - Keep every href exactly as-is. Never modify URL values.

9. CLASSES — You are a Bootstrap 4 specialist. Keep ONLY Bootstrap 4 utility
   classes: col-*, col-sm-*, col-md-*, col-lg-*, text-*, table, img-fluid,
   font-weight-bold, mx-auto, w-100, d-block, d-flex, justify-content-*,
   align-items-*, mb-*, mt-*, p-*, m-*, etc. Strip every other class
   attribute value. Do NOT use Bootstrap 5 classes (no g-*, no row-cols-*, etc).

10. NO NEW STYLES - Do not add inline styles. Do not introduce tags that weren't there.

## Output format

Return a JSON object with one key "sections" - an array with the SAME number of entries
as the input, in the SAME ORDER. Each entry:
  { "id": "<same id as input>", "intent": "<one sentence>", "snippets": ["<enriched html>", ...] }

If a section has no snippets (image-only), return "snippets": [] and still write an intent.
Nothing outside the JSON. No markdown fences."""


def build_enrich_user_message(sections: list[dict]) -> str:
    import json as _json
    return _json.dumps({"sections": sections}, ensure_ascii=False)


def build_standalone_clean_user_message(raw_html: str) -> str:
    return f"""Clean and structure this page HTML into DDC widget assignments.

RAW HTML:
{raw_html}"""


_CHROME_BATCH_SYSTEM = """You are reviewing candidate page sections for DDC dealer-page migration.

You receive a JSON object with a "candidates" array. Each candidate is one
HTML snippet that the deterministic algorithm flagged as possibly being page
chrome rather than dealer content (typical triggers: sidebar-shaped column,
chrome-sounding class name).

For each candidate, decide:
- KEEP - dealer-relevant editorial content (forms with real lead intent,
  contact info, hours, CTAs, content blocks, sidebars with substantive content)
- DROP - page chrome that should not be migrated (navigation menus, footers,
  ad widgets, social link rows, cookie banners, blog category lists, recent
  posts lists, newsletter sign-ups that are clearly navigational)

Return a JSON object with exactly this shape, preserving the input order and
the same number of entries:

{
  "verdicts": [
    {"id": "<same id as input>", "verdict": "KEEP" | "DROP"},
    ...
  ]
}

No markdown fences, no text outside the JSON.
"""


def build_chrome_batch_system_prompt() -> str:
    return _CHROME_BATCH_SYSTEM


def build_chrome_batch_user_message(snippets: list[str]) -> str:
    payload = {
        "candidates": [{"id": str(i), "html": s} for i, s in enumerate(snippets)]
    }
    return json.dumps(payload, ensure_ascii=False)


_IMAGE_SPLIT_SYSTEM = """You are reviewing content widgets from a dealer-page migration.
Each widget contains one or more <img> tags embedded in HTML. For each <img>,
decide whether the image should be PROMOTED to its own standalone image
widget, or KEPT inline inside the surrounding content.

PROMOTE (return true) - the image is a standalone visual element:
  • Hero photo or banner
  • Illustration, diagram, photograph
  • Product shot, dealership exterior, vehicle photo
  • Anything that visually breaks the text flow as a distinct block

KEEP INLINE (return false) - the image is inline content:
  • Tiny icon adjacent to text
  • Signature, emoji-like graphic, decorator badge

When in doubt about a meaningfully-sized image inside a <p> tag, prefer
PROMOTE. Dealer-page editorial images are nearly always standalone.

Input shape:
{
  "items": [
    {"id": "0", "html": "<h1>...</h1><p><img src='hero.jpg'/></p><p>text</p>"},
    ...
  ]
}

Output shape - same id, one boolean per <img> in document order:
{
  "items": [
    {"id": "0", "splits": [true]},
    ...
  ]
}

Length of each "splits" array must equal the count of <img> tags in that
item's html. Return only valid JSON, no markdown fences, no explanation."""


def build_image_split_system_prompt() -> str:
    return _IMAGE_SPLIT_SYSTEM


def build_image_split_user_message(items: list[dict]) -> str:
    return json.dumps({"items": items}, ensure_ascii=False)


_WIDGET_TYPE_SYSTEM = """You are classifying content widgets from a dealer-page migration.

Each widget contains HTML that the deterministic algorithm flagged as having
structural signals beyond plain text - it might be a contact form, hours
display, contact info block, or something else. Your job is to pick the
right type per widget.

For each item, return exactly ONE of these types:

- "form" - a contact/lead-gen form. HTML contains a <form> tag with multiple
  input/select/textarea fields for capturing user information (name, email,
  phone, message). Examples: contact us, request a quote, schedule service,
  vehicle history request. NOT search boxes, NOT newsletter signups, NOT
  single-field zip-code finders.

- "contact_info" - dealership identity block. Some combination of: business
  name, street address, phone number(s), email address. Usually a card,
  sidebar, or footer element. The actual data isn't migrated - DDC pulls
  real dealer info from the master record at render time. We only need to
  mark "a contact info widget belongs here".

- "hours" - business hours display. Day-of-week names + time ranges like
  "Monday 9:00 AM - 7:00 PM". Tables, definition lists, repeated row
  patterns, or tabbed displays for multiple departments (Sales, Service,
  Parts). The actual hours data isn't migrated.

- "content" - actually just regular editorial content. The structural signal
  that triggered candidacy was incidental - a body paragraph that mentions
  a phone number, a table of vehicle specs, a tabbed trim comparison, a
  styled card that's really a content callout. When in doubt between this
  and a widget type, prefer "content". This is the safe default.

- "drop" - meaningless markup that shouldn't be migrated. Tracking pixels,
  legal disclaimers wrapped in suspicious classes, dead/orphan widget
  templates, social link rows, anything that isn't editorial content and
  isn't a known widget.

Input shape:
{
  "items": [
    {"id": "0", "html": "<form>...</form>"},
    {"id": "1", "html": "<div class='dealer-info'>...</div>"}
  ]
}

Output shape - same ids, one type per item, no extra fields:
{
  "items": [
    {"id": "0", "type": "form"},
    {"id": "1", "type": "contact_info"}
  ]
}

No markdown fences, no text outside the JSON."""


def build_widget_type_system_prompt() -> str:
    return _WIDGET_TYPE_SYSTEM


def build_widget_type_user_message(items: list[dict]) -> str:
    return json.dumps({"items": items}, ensure_ascii=False)


def build_user_message(skeleton: DOMSkeleton, feedback: str | None = None) -> str:
    skeleton_text = json.dumps(skeleton.model_dump(), indent=2)
    base = f"""Classify this visual block and return the widget assignments.

Page URL: {skeleton.url}
Page title: {skeleton.title}

Block DOM:
{skeleton_text}"""

    if feedback:
        return base + f"\n\n## Correction feedback\n{feedback}"
    return base


# ── Nav-parser prompts ──────────────────────────────────────────────────────────


def build_nav_parser_system_prompt() -> str:
    return """You are an expert HTML parser specialized in dealer-website navigation menus.

Your job: parse a navigation-menu HTML snippet and return all navigation links as JSON.

## Rules

1. **URLs must be absolute.** If a link is relative or just a path, prepend the provided base URL.
2. **Skip trigger buttons** with no link (don't include them).
3. **Deduplicate.** If the same link appears multiple times, keep only the last occurrence (closest to the bottom of the HTML).
4. **Categorize each link:**
   - `model_specific` → pages dedicated to specific vehicle models, trims, or comparison pages (e.g. Terrain, Acadia, Sierra, Hummer EV vs Cybertruck).
   - `general` → everything else (Home, About, Service, Finance, generic inventory pages, etc.)
5. **Title** is the anchor text, trimmed of extra whitespace.

## Output format - CRITICAL

Return ONLY a JSON object with this exact shape:

```json
{
  "pages": [
    {"title": "Home",         "url": "https://example.com/",                "category": "general"},
    {"title": "2024 Terrain", "url": "https://example.com/inventory/terrain", "category": "model_specific"}
  ]
}
```

Do not include any commentary, markdown, or explanation outside the JSON object."""


def build_nav_parser_user_message(html: str, base_url: str) -> str:
    return f"""Base URL: {base_url}

HTML:
{html}"""


# ── Staff extraction prompts ───────────────────────────────────────────────────


def build_staff_extraction_system_prompt() -> str:
    return """You are an expert HTML parser specialized in dealer staff directory pages.

Your job: parse a staff page HTML snippet and return all staff members as JSON.

## Rules

1. Identify department headers (e.g. "Management", "Sales", "Service", "Parts").
2. For each person listed under a department, extract their information.
3. For each person's photo:
   - If they have an `<img>` tag, set `has_photo: true` and put the absolute URL in `original_photo_url`.
   - If the URL is relative (e.g. `/static/jane.jpg`), prepend the provided base URL.
   - If the src ends in `.heic` (case-insensitive), treat as no photo - set `has_photo: false` and `original_photo_url: null`.
   - If no `<img>` tag, set `has_photo: false` and `original_photo_url: null`.
4. Use `null` for any missing field (title, phone, email, bio).
5. Never invent or guess data.

## Output format - CRITICAL

Return ONLY a JSON object with this exact shape:

```json
{
  "staff": [
    {
      "department":         "Sales",
      "name":               "Jane Doe",
      "title":              "Sales Manager",
      "phone":              "555-1234",
      "email":              "jane@dealer.com",
      "bio":                "Jane has been with the dealership for 10 years.",
      "has_photo":          true,
      "original_photo_url": "https://www.dealer.com/static/jane.jpg"
    }
  ]
}
```

Do not include commentary, markdown, or explanation outside the JSON object."""


def build_staff_extraction_user_message(html: str, base_url: str) -> str:
    return f"""Base URL: {base_url}

HTML:
{html}"""


# ── Salesforce intake classifier prompts ───────────────────────────────────────


def build_intake_classifier_system_prompt() -> str:
    return """You classify Cox Automotive DDC client onboarding questionnaires.

A questionnaire is for one of two project types:
- "prebuild": a brand-new website for an existing dealership. The same legal
  entity keeps operating; we are just building them a new web presence.
- "buysell": a dealership that was just bought by a new owner. The owner is
  replacing the existing website. BuySells almost always mention the
  PREVIOUS dealer name and the NEW dealer name alongside each other. The
  exact wording varies: "previous", "old", "former", "prior", "to be
  renamed", etc.

Heuristics:
- If the questionnaire mentions a previous/old/former/prior dealership name
  AND a separate new dealership name -> buysell.
- If only one dealership name is present, no previous/old/former mention ->
  prebuild.
- The literal row "Is this a Buy/Sell" can be wrong or blank - use it as a
  hint, not a rule.

Return ONLY a JSON object on a single line, no markdown, no commentary:
{"classification":"prebuild"|"buysell","confidence":0.0-1.0,"reasoning":"<one short sentence>","newDealershipName":"<string or null>"}
- confidence is your subjective certainty, not a probability.
- newDealershipName is the dealership's NEW name (only when classification is
  buysell, else null)."""


def build_intake_classifier_user_message(rows: dict[str, str]) -> str:
    """Format the parsed questionnaire row dict for the classifier.

    Keep the original key:value lines - the LLM sees natural text far better
    than JSON, and the source format is already readable. Values longer than
    400 chars are truncated to keep token budget tight.
    """
    lines: list[str] = []
    for key in sorted(rows):
        value = rows[key]
        if len(value) > 400:
            value = value[:400] + "…"
        lines.append(f"{key}\t{value}")
    return "\n".join(lines)


# ── Salesforce intake field extractor prompts ────────────────────────────────


def build_intake_extractor_system_prompt(classification: str) -> str:
    """V2 extraction prompt — replaces the deterministic label-matching parser.

    The questionnaire row labels drift across Salesforce boards. Same reason
    classification uses an LLM (see `classifier.py:3-8`). The extractor receives
    the full row dict and the already-decided classification (prebuild |
    buysell), then maps to a fixed set of typed fields via a structured tool
    call.
    """
    is_buysell = classification == "buysell"

    buysell_guidance = """
This is a BUY/SELL project. The dealership is changing ownership.
- `dealership_name` = the CURRENT/SELLER name (e.g. "Current (Seller's) Dealership Name").
- `new_dealership_name` = the BUYER's new name (e.g. "New (Buyer's) Dealership Name").
- `primary_url` = the seller's existing site (e.g. "Current (Seller's) Primary URL/Domain").
- `new_primary_url` = the buyer's new domain. Prefer the row labelled "New Primary URL/Domain" when present;
  otherwise use "New (Buyer's) Primary URL/Domain". If both are present and non-empty, prefer "New Primary URL/Domain".
"""

    prebuild_guidance = """
This is a PREBUILD project. One dealership, one site, no ownership change.
- `dealership_name` = the dealership's name (label may be "Dealership Name", "Current Dealership Name", etc.).
- `new_dealership_name` = null (prebuild has no renaming).
- `primary_url` = the dealership's primary domain (label may be "Primary URL/Domain", "Current Primary URL/Domain", "Website", etc.).
- `new_primary_url` = null (prebuild has no new URL).
"""

    classification_guidance = buysell_guidance if is_buysell else prebuild_guidance

    return f"""You extract typed fields from a Salesforce dealer onboarding questionnaire.

The questionnaire is a flat list of "Label<TAB>Value" rows. Labels drift across boards
("Dealership Name" / "Current Dealership Name" / "Seller's Dealership Name", etc.) — match by meaning, not by exact string.

Empty rows are common — many fields the dealer didn't fill in. Return null for missing values, NEVER fabricate.

{classification_guidance}

URL HANDLING
- Strip leading/trailing whitespace.
- If the URL has no scheme, leave it as-is (the post-processor adds `https://`).
- Do not invent URLs from the dealer name.

EMAIL HANDLING
- If a lead-routing email is present in any "Leads Email", "CRM Email", or similar row, return it.
- Lowercase the email.
- If no email present, return null.

ADDRESS HANDLING
- The address row may be a single line ("624 State Route 930 E, New Haven, IN, 46774") or multi-part.
- Return the cleanest single-line form you can derive. Title-case will be applied by the post-processor.

DESIGN CHOICE
- The "Design Choice" or "Design Option" row may contain pasted JSON or free-text description.
- Return whatever raw value is present (or null). The post-processor decides JSON-vs-description.

Return your answer by calling the `submit_intake_fields` tool with all required fields."""


def build_intake_extractor_user_message(rows: dict[str, str]) -> str:
    """Same key:value text format as the classifier — LLMs parse this far
    better than JSON when the source is already line-oriented."""
    lines: list[str] = []
    for key in sorted(rows):
        value = rows[key]
        if len(value) > 400:
            value = value[:400] + "…"
        lines.append(f"{key}\t{value}")
    return "\n".join(lines)


# ── Label translation prompts (EN → es_US for DDC labels) ──────────────────────


def build_label_translation_system_prompt(
    dealer_name: str,
    glossary_table: str,
) -> str:
    return f"""You translate dealership website labels from English to es_US for "{dealer_name}".

GLOSSARY — when any of these English terms appears in the input, the Spanish translation MUST use the mapped term verbatim:

{glossary_table}

CONTEXT NOTES
- "Directions" can mean "Ubicación" (a place) or "Indicaciones" (driving directions). Pick by context.
- Do NOT use Spanish articles (el/la) before specific vehicle model names.
- Brand and model names are NEVER translated. Examples:
    "Toyota 4Runner"        → "Toyota 4Runner"        (not "Toyota Corredor")
    "Orange Buick GMC"      → "Orange Buick GMC"      (not "Buick GMC Naranja")
    "{dealer_name}"         → "{dealer_name}"

HTML / VARIABLE RULES
- Preserve every HTML tag, attribute, and href value exactly as in the input.
- Preserve every bracketed variable like [PRICE], [MODEL], [YEAR] exactly.
- Preserve every encoded entity (&nbsp;, &amp;, \\u002f, etc.) exactly.
- Translate ONLY visible text content. Do not translate URLs, classes, or ids.

OUTPUT
- Return ONLY the translated text. No commentary. No markdown fences. No JSON.
- If the input is a plain string, return a plain string.
- If the input contains HTML, return HTML with the same tag structure."""


def build_label_translation_user_message(en_html: str, extra_hint: str = "") -> str:
    hint_block = f"\n\nRETRY FEEDBACK FROM PREVIOUS ATTEMPT:\n{extra_hint}" if extra_hint else ""
    return f"""Translate the following label to es_US following all rules above. Output the translated label only.

LABEL:
{en_html}{hint_block}"""


# ── Label translation prompts V2 — with glossary_lookup tool ───────────────────


def build_label_translation_system_prompt_v2(dealer_name: str) -> str:
    """V2 prompt: structured tool-based output.

    Two tools:
      - `glossary_lookup(terms)` — call as needed for domain terms.
      - `submit_translation(reasoning, translation)` — final answer.

    The model MUST end every turn with a `submit_translation` call; any
    free-form reasoning goes into the `reasoning` field, not into plain text
    output. This prevents thinking from leaking into the visible result."""
    return f"""You translate dealership website labels from English to es_US (Mexican Spanish) for "{dealer_name}".

TOOLS AVAILABLE
1. `glossary_lookup(terms)` — returns authoritative MX-Spanish for English terms.
   - USE it for automotive/dealership vocabulary you're uncertain about (e.g. "Lane Keep Assist", "Buy-Sell", "Pre-Owned", "Test Drive").
   - DO NOT use it for obvious common words ("the", "and", "we", "you").
   - Call ONCE with a list of all uncertain terms; don't fire multiple calls.
   - A null return means the term isn't in the glossary — translate using your own knowledge.

2. `submit_translation(reasoning, translation)` — your FINAL answer. You MUST use this.
   - `reasoning`: 1-3 short sentences explaining your translation choices, especially any decisions about terms, articles, or word order. Keep it concise.
   - `translation`: the final es_US string. Plain text in, plain text out; HTML in, HTML out with same tag structure.

CONTEXT NOTES
- "Directions" can mean "Ubicación" (a place) or "Indicaciones" (driving directions). Pick by context.
- Do NOT use Spanish articles (el/la) before specific vehicle model names.
- Brand and model names are NEVER translated. Examples:
    "Toyota 4Runner"        → "Toyota 4Runner"        (not "Toyota Corredor")
    "Orange Buick GMC"      → "Orange Buick GMC"      (not "Buick GMC Naranja")
    "{dealer_name}"         → "{dealer_name}"

HTML / VARIABLE RULES (apply to `translation` field only)
- Preserve every HTML tag, attribute, and href value exactly as in the input.
- Preserve every bracketed variable like [PRICE], [MODEL], [YEAR] exactly.
- Preserve every encoded entity (&nbsp;, &amp;, \\u002f, etc.) exactly.
- Translate ONLY visible text content. Do not translate URLs, classes, or ids.

NEVER emit plain text in your turn — always call a tool. Your final turn is always `submit_translation`."""


# ── Translation guardrail (reviewer) prompts ───────────────────────────────────


def build_judge_translation_system_prompt(dealer_name: str) -> str:
    return f"""You are a careful Mexican Spanish reviewer for "{dealer_name}" dealership website labels.

You will receive an English original and a candidate Spanish translation.

EVALUATE TWO THINGS:
1. NATURALNESS — does the Spanish read smoothly to a native MX-Spanish speaker? Catch awkward phrasing, anglicisms, robotic word-for-word renderings.
2. MEANING FIDELITY — does the Spanish convey the same meaning as the English? Catch dropped clauses, added information, mistranslated terms.

You do NOT need to evaluate HTML structure — a separate check handles that.

Return your verdict as a tool call (`submit_verdict`) with:
- ok: true if BOTH naturalness and fidelity are acceptable, false otherwise
- reason: 1-2 short sentences explaining what's wrong (empty string when ok=true is fine)

Be reasonable, not pedantic. Prefer "ok" when the translation is acceptable but imperfect; flag clear problems."""


def build_judge_translation_user_message(en_html: str, es_html: str) -> str:
    return f"""ENGLISH ORIGINAL:
{en_html}

SPANISH TRANSLATION:
{es_html}

Evaluate."""
