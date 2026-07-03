"""Tool implementation for the translator's glossary_lookup function.

Replaces the previous approach of baking the whole glossary into the system
prompt. The translator now requests authoritative MX-Spanish for specific
terms only when uncertain. Net: smaller prompts, scoped lookups.

Exact, case-insensitive match. The model is responsible for chunking phrases
itself — no fuzzy or contains matching, since the glossary is curated and
deterministic behavior matters.
"""

from __future__ import annotations

from functools import lru_cache

from .glossary_loader import GlossaryEntry, get_glossary


@lru_cache(maxsize=1)
def _lower_map() -> dict[str, str]:
    return {e.en.lower(): e.es for e in get_glossary()}


def glossary_search(terms: list[str]) -> dict[str, str | None]:
    """Look up authoritative MX-Spanish for each term.

    Returns a dict keyed by the ORIGINAL term (preserving the caller's
    casing/spacing) with the matched ES string, or None on miss. Empty input
    returns empty dict.
    """
    if not terms:
        return {}
    table = _lower_map()
    return {t: table.get(t.strip().lower()) for t in terms}


__all__ = ["glossary_search", "GlossaryEntry"]
