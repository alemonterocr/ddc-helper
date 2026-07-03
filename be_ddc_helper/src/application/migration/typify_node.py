"""Typify node — LLM-driven widget-type classification.

For each content widget produced by `build_node` that has structural signals
beyond plain text (forms, day/time patterns, phone/email/address, structured
tables, tab/accordion shapes, engineered class markup), ask the LLM what kind
of widget it actually is:

  - form         → replace with {type: 'form'} marker
  - contact_info → replace with {type: 'contact_info'} marker
  - hours        → replace with {type: 'hours'} marker
  - content      → leave unchanged (LLM says "actually just text")
  - drop         → remove the widget

Marker widgets carry no payload — DDC fills in real form fields, dealer
master-record contact data, and configured hours server-side. The execute
layer already accepts widget_type='form'/'contact_info'/'hours'.

Architectural note: this is the one place in the graph where we accept
bounded N-class LLM classification rather than strict binary. The signal
anchor in widget HTML (the <form> tag, day-name + time text, phone regex)
is concrete enough that the LLM can match it to a fixed five-class
taxonomy reliably. Layout classification (the reclassify case that was
deleted) was N-class without that signal anchor and produced unreliable
output.

Trigger philosophy is intentionally aggressive: anything that "doesn't look
like plain blog markup" reaches the LLM, which then votes content/drop on
the false positives. This trades a few extra cheap-tier LLM tokens for
flexibility across CMS templates we haven't seen yet.
"""

import re
from typing import Awaitable, Callable

from src.domain.models import MigrationState
from src.ports.outbound import LLMPort

Progress = Callable[[str], Awaitable[None]]

# One tuple per content-widget candidate: (section_idx, slot_idx, widget_idx, html).
Candidate = tuple[int, int, int, str]


# ── Trigger regexes ──────────────────────────────────────────────────────────

# Phone: tolerates (704) 555-1234, 704-555-1234, 704.555.1234, 704 555 1234,
# 7045551234. The (?:\(\d{3}\)|\d{3}) handles the optional paren-wrapped area
# code; the literal "\(?\)?" approach was rejected because it allowed an open
# paren without a close, matching ambient text noise like "(see page 42)5551234".
_PHONE_RE = re.compile(
    r"(?:\(\d{3}\)|\d{3})\s*[-.\s]?\s*\d{3}\s*[-.\s]?\s*\d{4}\b"
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_STREET_RE = re.compile(
    r"\d+\s+\w+(\s+\w+)*\s+(st|ave|rd|blvd|dr|way|pkwy|hwy|street|avenue|road|drive|boulevard)\b",
    re.IGNORECASE,
)
_ZIP_RE = re.compile(r"\b\d{5}(-\d{4})?\b")
_US_STATE_RE = re.compile(
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    r"MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|"
    r"WA|WV|WI|WY|DC)\b"
)
_DAY_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"mon|tue|wed|thu|fri|sat|sun)\b",
    re.IGNORECASE,
)
_TIME_RE = re.compile(
    r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)\b|\b\d{1,2}:\d{2}\b",
    re.IGNORECASE,
)
_CLASS_WORDS_RE = re.compile(
    r'class="[^"]*\b('
    r'hours|contact|address|dealer-info|dealership-info|schedule|'
    r'location|find-us|visit-us|directions|phone|email|mailing|'
    r'office-hours|lobby-hours|service-hours|parts-hours|sales-hours|'
    r'dealer-card|contact-card|contact-block|info-block|info-card'
    r')\b',
    re.IGNORECASE,
)
_TAB_CLASS_RE = re.compile(
    r'class="[^"]*\b(tab|tabs|accordion|pane|tab-content|tab-pane)\b',
    re.IGNORECASE,
)
_TAB_ROLE_RE = re.compile(r'role="(tablist|tab|tabpanel)"', re.IGNORECASE)
_JSON_LD_RE = re.compile(
    r"localbusiness|openinghours|openinghoursspecification|postaladdress",
    re.IGNORECASE,
)
_CLASSED_ELEMENT_RE = re.compile(r'<\w+\s[^>]*class="[^"]+"')


# ── Node factory ─────────────────────────────────────────────────────────────


def build_typify_node(
    llm: LLMPort | None,
    progress: Progress | None = None,
    enabled: bool = True,
):
    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def typify(state: MigrationState) -> dict:
        det_plan = state["det_plan"]
        if not enabled or llm is None:
            return {"det_plan": det_plan}

        candidates = _collect_candidates(det_plan)
        if not candidates:
            return {"det_plan": det_plan}

        await _progress("AI is deciding widget types")
        verdicts = await _classify(llm, candidates)
        if verdicts is None:
            await _progress("⚠ Widget typing failed — keeping widgets unchanged")
            return {"det_plan": det_plan}

        _apply_verdicts(det_plan, candidates, verdicts)
        return {"det_plan": det_plan}

    return typify


# ── Pass 1: candidate collection ─────────────────────────────────────────────


def _collect_candidates(det_plan: list[dict]) -> list[Candidate]:
    """Content widgets whose HTML has structural signals worth an LLM opinion."""
    candidates: list[Candidate] = []
    for s_idx, section in enumerate(det_plan):
        for sl_idx, slot in enumerate(section.get("slots", [])):
            for w_idx, widget in enumerate(slot):
                if widget.get("type") != "content":
                    continue
                html = widget.get("html") or ""
                if _has_structured_signal(html):
                    candidates.append((s_idx, sl_idx, w_idx, html))
    return candidates


# ── LLM invocation ───────────────────────────────────────────────────────────


async def _classify(
    llm: LLMPort, candidates: list[Candidate]
) -> dict[str, str] | None:
    """Run the batched LLM call. Return {candidate_id: verdict} or None on failure."""
    items = [{"id": str(i), "html": html} for i, (_, _, _, html) in enumerate(candidates)]
    try:
        raw = await llm.classify_widget_type(items)
    except Exception:
        return None
    return {
        str(v.get("id", "")): str(v.get("type", "content")).lower() for v in raw
    }


# ── Pass 2: verdict application ──────────────────────────────────────────────


def _apply_verdicts(
    det_plan: list[dict],
    candidates: list[Candidate],
    verdicts: dict[str, str],
) -> None:
    """Mutate det_plan in place: replace with marker, drop, or leave unchanged.

    Widgets in the same slot are processed in reverse order so
    deletions/replacements don't shift earlier indices.
    """
    by_slot = _group_verdicts_by_slot(candidates, verdicts)
    for (s_idx, sl_idx), entries in by_slot.items():
        entries.sort(key=lambda e: e[0], reverse=True)
        slot = det_plan[s_idx]["slots"][sl_idx]
        for w_idx, verdict in entries:
            _apply_one(slot, w_idx, verdict)


def _group_verdicts_by_slot(
    candidates: list[Candidate], verdicts: dict[str, str]
) -> dict[tuple[int, int], list[tuple[int, str]]]:
    """{(section_idx, slot_idx): [(widget_idx, verdict), ...]}"""
    by_slot: dict[tuple[int, int], list[tuple[int, str]]] = {}
    for i, (s_idx, sl_idx, w_idx, _) in enumerate(candidates):
        verdict = verdicts.get(str(i), "content")
        by_slot.setdefault((s_idx, sl_idx), []).append((w_idx, verdict))
    return by_slot


def _apply_one(slot: list[dict], w_idx: int, verdict: str) -> None:
    if verdict in ("form", "contact_info", "hours"):
        slot[w_idx] = {"type": verdict}
    elif verdict == "drop":
        del slot[w_idx]
    # verdict == "content" (or anything unknown) → leave the widget as-is


# ── Candidate flagging: split by signal bucket ───────────────────────────────


def _has_structured_signal(html: str) -> bool:
    """Aggressive flag — true for anything that's not plain blog/article markup.

    Any one of four buckets returning True triggers the LLM.
    Plain paragraphs and headings with no class attributes return False.
    """
    if not html:
        return False
    return (
        _has_strong_widget_signal(html)
        or _has_concrete_data_pattern(html)
        or _has_class_word_signal(html)
        or _has_structural_shape(html)
    )


def _has_strong_widget_signal(html: str) -> bool:
    """<form>, <address>, or JSON-LD business schema."""
    h = html.lower()
    if "<form" in h or "<address" in h:
        return True
    return bool(_JSON_LD_RE.search(html))


def _has_concrete_data_pattern(html: str) -> bool:
    """Phone, email, street, zip+state pair, or day+time pair."""
    if _PHONE_RE.search(html) or _EMAIL_RE.search(html) or _STREET_RE.search(html):
        return True
    if _ZIP_RE.search(html) and _US_STATE_RE.search(html):
        return True
    if _DAY_RE.search(html) and _TIME_RE.search(html):
        return True
    return False


def _has_class_word_signal(html: str) -> bool:
    """Class names like hours, contact, dealer-card that signal a widget shape."""
    return bool(_CLASS_WORDS_RE.search(html))


def _has_structural_shape(html: str) -> bool:
    """Tables, definition lists, tabs/accordions, or ≥2 classed children."""
    h = html.lower()
    if "<table" in h or "<dl" in h:
        return True
    if _TAB_CLASS_RE.search(html) or _TAB_ROLE_RE.search(html):
        return True
    return _has_multiple_classed_children(html)


def _has_multiple_classed_children(html: str) -> bool:
    """≥2 element children with class attributes — engineered markup, not
    plain blog prose."""
    return len(_CLASSED_ELEMENT_RE.findall(html)) >= 2
