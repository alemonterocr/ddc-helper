from typing import Callable, Protocol

from src.domain.models import DOMSkeleton, SectionPlan, TokenUsage


class LLMPort(Protocol):
    # ── Token accounting ────────────────────────────────────────────────────
    usage_log: list[TokenUsage]

    def reset_usage(self) -> None:
        """Clear the usage log for this adapter — called at the start of each
        billable request (e.g. /analyze) so per-request totals are accurate."""
        ...


    async def analyze(
        self,
        skeleton: DOMSkeleton,
        catalog: list[dict],
        rules: str,
    ) -> SectionPlan: ...

    async def clean_html(self, raw_html: str, base_url: str) -> SectionPlan: ...

    async def enrich_content(self, sections: list[dict]) -> list[dict]:
        """Enrich a batch of sections in one shot.

        Input per section: {id, section_type, slot_summary, snippets: list[str]}
        Output per section: {id, intent: str, snippets: list[str]}

        Uses a lighter model than the main analyze() call — fast, cheap,
        appropriate for HTML cleanup and copywriting tasks.
        """
        ...

    async def classify_chrome_batch(self, snippets: list[str]) -> list[str]:
        """Batched KEEP/DROP for many chrome candidates in one LLM call.

        Returns a list of "KEEP" or "DROP" verdicts, same length and order as
        `snippets`. On any parse/transport failure, callers should default to
        all-KEEP (safer to over-include than to drop real content).
        """
        ...

    async def classify_widget_type(self, items: list[dict]) -> list[dict]:
        """Batched N-class widget classification for content widgets flagged
        as having structural signals beyond plain text.

        Input: list of {id: str, html: str}.
        Output: list of {id: str, type: str} in the same order, where type
        is one of: "form", "contact_info", "hours", "content", "drop".

        On any parse/transport failure, callers should default to all-"content"
        (preserves the existing widget structure — safe fallback)."""
        ...

    async def classify_image_splits(self, items: list[dict]) -> list[list[bool]]:
        """Batched per-image promote/keep verdicts for content widgets that
        contain embedded <img> tags.

        Input: list of {id: str, html: str} — each html is a content widget's
        HTML that contains one or more <img> tags.
        Output: list of list[bool], one outer entry per input item (same order
        and length), each inner list having one boolean per <img> in that
        item's html (document order). True = promote to standalone image
        widget; False = keep inline in content.

        On any parse/transport failure or missing entries, callers should
        default to all-False (no widget changes — preserves current behavior).
        """
        ...

    async def extract_staff(self, html: str, base_url: str) -> list[dict]:
        """Parse a staff-page HTML snippet into a list of staff member dicts.

        Input:
          - html: raw HTML of the source staff page (typically `skeleton.raw_html`).
          - base_url: absolute base URL of the source site for resolving relative
            photo URLs (e.g. `/static/jane-doe.jpg`).

        Output: list of dicts matching `StaffMember`:
          {
            "department":         str,
            "name":               str,
            "title":              str | None,
            "phone":              str | None,
            "email":              str | None,
            "bio":                str | None,
            "has_photo":          bool,
            "original_photo_url": str | None,
          }

        On any parse/transport failure, callers should default to an empty list
        with a warning. The executor handles "no photo" rows by skipping the
        upload step for that member.
        """
        ...

    async def parse_nav(self, html: str, base_url: str) -> list[dict]:
        """Parse a navigation-menu HTML snippet into a list of {title, url, category} dicts.

        Input:
          - html: navigation-menu HTML, typically the contents of a <nav> element.
          - base_url: absolute base URL of the source site. Used to resolve relative
            href values into absolute URLs.

        Output: list of dicts in document order, deduplicated (last occurrence wins):
          {
            "title":    str,                          # cleaned anchor text
            "url":      str,                          # absolute URL
            "category": "general" | "model_specific"  # see prompt
          }

        Trigger buttons with no href are skipped. On any parse/transport failure,
        callers should default to an empty list with a warning.
        """
        ...

    async def classify_intake(self, rows: dict[str, str]) -> str:
        """Classify a Salesforce onboarding questionnaire as Prebuild vs. BuySell.

        Input: the full parsed row dict from the Salesforce questionnaire blob
        (key -> value, all rows the parser found). Caller should pass the full
        `ParsedQuestionnaire.all_rows` so the LLM has context beyond the 5
        normalised fields.

        Output: raw response text. The caller (`classifier.classify_intake_with_llm`)
        parses it into a `ClassificationVerdict`. Adapters must NOT pre-parse —
        return whatever the model emitted. On any transport/auth failure, the
        caller defaults to `prebuild + confidence:0`, so adapters may raise
        freely here.

        Uses the light-tier model (same as enrich/parse_nav).
        """
        ...

    async def translate_label(
        self,
        en_html: str,
        dealer_name: str,
        glossary_table: str,
    ) -> str:
        """Translate one DDC label from English to es_US.

        Input:
          - en_html: the label's English value (may be plain text or HTML).
          - dealer_name: the dealership's display name, used so the model
            never translates the dealer's own brand/model/proper-noun text.
          - glossary_table: pre-rendered EN→ES glossary block to be embedded
            in the system prompt. Caller is responsible for picking the
            right glossary file and pre-formatting.

        Output: the translated es_US string. HTML tags, attributes, href
        values, encoded entities (&nbsp;, \\u002f, etc.), and bracketed
        variables ([PRICE], [MODEL], ...) must be preserved verbatim — the
        prompt enforces this; the caller validates structurally.

        Uses the light-tier model (same tier as enrich/parse_nav).
        """
        ...

    async def extract_intake_fields(
        self,
        rows: dict[str, str],
        classification: str,
    ) -> dict:
        """Extract typed fields from a Salesforce questionnaire row dict.

        Input:
          - rows: full key→value dict from `parse_questionnaire_blob` (the LLM
            needs to see all labels because they drift across boards).
          - classification: "prebuild" | "buysell". Tells the model whether to
            look for seller-side or buyer-side URL/name fields.

        Returns a dict with keys (each value is a string or None):
          - dealership_name           (always: the current/live dealership name)
          - new_dealership_name       (buysell only)
          - dealership_address
          - leads_email
          - primary_url               (always: the current/live site URL)
          - new_primary_url           (buysell only: the buyer's new URL)
          - design_choice             (raw text; app layer post-processes)

        On any parse/transport failure, callers should default to all-None
        and surface a soft warning."""
        ...

    async def translate_label_with_tools(
        self,
        en_html: str,
        dealer_name: str,
        glossary_lookup: Callable[[list[str]], dict[str, str | None]],
        extra_hint: str = "",
    ) -> dict:
        """Multi-turn translation with structured final output.

        The adapter runs an agentic loop with two tools exposed:
          - `glossary_lookup` (auto-callable) for term lookup
          - `submit_translation` (forced final) for the structured answer

        The model may call `glossary_lookup` any number of times to verify
        terminology, then MUST call `submit_translation` with two fields:
          - reasoning: model's brief thinking about translation choices
          - translation: the final es_US string

        Args:
          en_html: the label's English value (plain text or HTML).
          dealer_name: dealership display name for context.
          glossary_lookup: callable mapping terms → MX-Spanish (or None).
          extra_hint: appended to the user message on retries.

        Returns: {"translation": str, "reasoning": str}. The `translation`
        must preserve HTML tags, hrefs, encoded entities, and bracketed
        variables exactly. `reasoning` is short (1-3 sentences) and surfaced
        to the user as a collapsible review field.

        Safety: implementations cap the tool loop at ≤5 iterations. On cap
        hit or parse failure, return {"translation": <best effort>,
        "reasoning": ""}."""
        ...

    async def translate_text_segments(
        self,
        segments: list[str],
        dealer_name: str,
    ) -> list[str]:
        """Translate a batch of plain-text fragments EN→es_US.

        Used by the page-widget translator: markup is extracted client-side and
        only the visible text strings are sent here, so there is nothing to
        preserve structurally and no truncation risk from re-emitting HTML.

        Robustness: the model is addressed by id (not position), so adapters
        match results back by id and fill any id the model drops with the
        original English — the returned list always has one entry per input, in
        order, even when the model omits or reorders items. Empty input → empty
        list. On a hard transport/parse failure (nothing usable) the adapter
        returns an empty list so the caller can mark the widget failed rather
        than saving an empty translation."""
        ...

    async def judge_translation(
        self,
        en_html: str,
        es_html: str,
        dealer_name: str,
    ) -> dict:
        """Single LLM call. Returns {ok: bool, reason: str}.

        Reads en_html and es_html side-by-side, evaluates fluency and meaning
        preservation as a fluent MX-Spanish speaker would. `reason` is a short
        human-readable explanation (empty when ok=True is fine).

        Implementations use the provider's preferred structured-output path
        (tool_choice for Anthropic, response_schema for Gemini, JSON mode for
        DeepSeek). On any parse/transport failure, return {"ok": True,
        "reason": ""} — failing closed would block the entire pipeline; we'd
        rather pass through and let the user catch it visually."""
        ...

    async def validate(self) -> bool: ...
