"""Smart title case for dealer addresses.

Capitalises the first letter of each word, lowercases the rest — EXCEPT for
tokens that should stay ALL CAPS: an extensible override set (USA, DDC, GM,
GMC, OEM, DNS, URL) and US state abbreviations when they appear next to a
ZIP code. Matching is case-insensitive on the override set, so lowercase
input like `"usa"` normalises to `"USA"`. State-code fixup runs as a
second pass gated on a ZIP context, so ambiguous 2-letter words like `"in"`,
`"or"`, `"hi"` in prose don't get accidentally uppercased.

>>> smart_title_case("117 FARMINGTON ROAD, SUMMERVILLE, SC 29486")
'117 Farmington Road, Summerville, SC 29486'
>>> smart_title_case("Charleston, sc 29486")
'Charleston, SC 29486'
>>> smart_title_case("gm dealer in usa")
'GM Dealer In USA'
>>> smart_title_case("")
''
"""

from __future__ import annotations

import re

# Override set — tokens that should be ALL CAPS regardless of input casing or
# length. Match is case-insensitive: `"usa"` and `"USA"` both normalise to `"USA"`.
_PRESERVE = {"USA", "DDC", "GM", "GMC", "OEM", "DNS", "URL"}

# US state abbreviations plus DC. Recognised only in ZIP-adjacent context by
# the second pass (see `_STATE_ZIP_RE`), because several codes collide with
# common English words (IN, OR, HI, OH, ME, MS).
_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# Per-token splitter: runs of word chars or apostrophes; everything else
# (spaces, commas, dashes, slashes, digits) is preserved verbatim.
_TOKEN_RE = re.compile(r"([A-Za-z][A-Za-z']*)")

# Two-letter word directly before a 5-digit ZIP (with optional -NNNN suffix).
# Second pass replaces the state token with its uppercase form when it's a
# valid state code — disambiguates `"in usa"` (prose, unchanged) from
# `"in 46220"` (Indianapolis, upcased).
_STATE_ZIP_RE = re.compile(r"\b([A-Za-z]{2})(\s+\d{5}(?:-\d{4})?\b)")


def smart_title_case(s: str) -> str:
    """Capitalise the first letter of each word; preserve overrides everywhere;
    fix state codes only in ZIP-adjacent context.

    Pass 1: per-token title-case.
    - Token upper form is in `_PRESERVE` → return upper form (any position).
    - Token is already all-caps and ≤3 chars → preserve as-is (unlisted short
      acronyms like a hand-typed `"LLC"`).
    - Otherwise: first letter upper, rest lower.

    Pass 2: state-code fixup.
    - Match `[A-Za-z]{2}\\s+ZIP` — if the two-letter word is a state code,
      uppercase it.
    """
    if not s:
        return s
    return _fix_state_codes(_title_case_tokens(s))


def _title_case_tokens(s: str) -> str:
    def _transform(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.upper() in _PRESERVE:
            return token.upper()
        if token.isupper() and len(token) <= 3:
            return token
        return token[0].upper() + token[1:].lower()

    return _TOKEN_RE.sub(_transform, s)


def _fix_state_codes(s: str) -> str:
    def _upcase_if_state(match: re.Match[str]) -> str:
        candidate, tail = match.group(1), match.group(2)
        if candidate.upper() in _STATE_CODES:
            return candidate.upper() + tail
        return match.group(0)

    return _STATE_ZIP_RE.sub(_upcase_if_state, s)
