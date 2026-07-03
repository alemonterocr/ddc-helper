"""Parse the raw `taskfeed1__Description__c` blob into a row dict.

The blob is plain text from the Salesforce Onboarding Questionnaire Insight
record. Lines are `\\r\\n`-separated. Each line is `Key<tabs>Value` where the
tab run between key and value is 1+ tabs (most are double-tab, some are
single-tab when the key wraps with a colon).

This module is pure: no I/O, no LLM, no HTTP. It only does the deterministic
row-splitting + design-choice JSON probe. Typed-field extraction (dealer name,
URL, etc.) now happens via the LLM in `extractor.py` because the questionnaire
labels drift across boards (same reasoning that drove the classifier to use an
LLM — see `classifier.py:3-8`).

Field-by-field normalisation (Title Case, lowercase email, https:// prefix) is
applied by the extractor AFTER it has the LLM's raw values.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any

# Line splitter: one or more tabs between key and value. Some rows use two tabs,
# some one - be permissive.
_LINE_KV_RE = re.compile(r"^(?P<key>[^\t]+?)\t+(?P<value>.*)$")


@dataclass
class DesignChoiceJson:
    """Design Choice parsed as JSON (the dealer pasted a real config)."""
    value: dict[str, Any]
    kind: str = "json"


@dataclass
class DesignChoiceDescription:
    """Design Choice as free-text - needs human input to produce real JSON."""
    raw: str
    kind: str = "description"
    needs_human_input: bool = True


@dataclass
class DesignChoiceMissing:
    """Design Choice row was empty or absent."""
    kind: str = "missing"


DesignChoice = DesignChoiceJson | DesignChoiceDescription | DesignChoiceMissing


@dataclass
class ParsedQuestionnaire:
    """Output of parse_questionnaire_blob.

    Typed fields are populated by the LLM extractor (see `extractor.py`); the
    parser itself only fills `all_rows`. The orchestrator converts `None` →
    `"-"` at response-build time so the FE never has to handle null/undefined.
    """
    dealership_name: str | None = None
    new_dealership_name: str | None = None  # buysell-only
    dealership_address: str | None = None   # smart-title-cased
    leads_email: str | None = None          # lowercased
    primary_url: str | None = None          # https://-prefixed (current/live site)
    new_primary_url: str | None = None      # buysell-only: buyer's new URL
    design_choice: DesignChoice = field(default_factory=DesignChoiceMissing)

    # Full row dict — input to the LLM classifier + extractor.
    all_rows: dict[str, str] = field(default_factory=dict)


def parse_questionnaire_blob(blob: str) -> ParsedQuestionnaire:
    """Turn the raw Description__c text into a ParsedQuestionnaire.

    Splits on `\\r\\n`, splits each line on its first tab run, builds a dict
    keyed by the (whitespace-stripped) label. Typed fields are left None;
    the LLM extractor fills them.

    Empty input → empty ParsedQuestionnaire, no exceptions.
    """
    return ParsedQuestionnaire(all_rows=_parse_rows(blob))


def _parse_rows(blob: str) -> dict[str, str]:
    """Split the blob into a dict by label.

    Tolerant of `\\r\\n`, `\\n`, and trailing whitespace. Trailing duplicate
    labels overwrite earlier ones (the later one wins - Salesforce sometimes
    appends extra rows on edit).
    """
    if not blob:
        return {}

    out: dict[str, str] = {}
    for raw_line in blob.replace("\r\n", "\n").split("\n"):
        if not raw_line.strip():
            continue
        match = _LINE_KV_RE.match(raw_line)
        if not match:
            # Lines without a tab → ignore (e.g. continuation lines of a multi-line value).
            # Future: if we see real multi-line values in the wild, append to last key.
            continue
        key = match.group("key").strip()
        # Salesforce's UI API returns long-text fields with HTML entities
        # (e.g. `&quot;`, `&amp;`, `&apos;`). Decode once at parse time so
        # downstream consumers (JSON.parse on design choice, LLM context,
        # FE rendering) see the original characters the dealer typed.
        value = html.unescape(match.group("value")).strip()
        out[key] = value
    return out


def _clean_or_none(s: str | None) -> str | None:
    if s is None:
        return None
    stripped = s.strip()
    return stripped if stripped else None


def _normalise_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _parse_design_choice(raw: str | None) -> DesignChoice:
    """Try JSON parse; fall back to description; fall back to missing."""
    cleaned = _clean_or_none(raw)
    if not cleaned:
        return DesignChoiceMissing()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return DesignChoiceJson(value=parsed)
        # Non-dict JSON (string, array, number) - treat as description so a human reviews.
        return DesignChoiceDescription(raw=cleaned)
    except (json.JSONDecodeError, ValueError):
        return DesignChoiceDescription(raw=cleaned)
