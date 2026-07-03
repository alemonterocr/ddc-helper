"""Structural sanity checks for translated label HTML.

The prompt does the heavy lifting; this is the defensive layer so a misbehaving
model can't silently drop tags, mangle hrefs, or eat bracketed variables.

Validation is intentionally loose where ambiguity is fine and strict where it
isn't — text content can change freely (that's the point), but tag count,
href values, and bracketed variables must round-trip exactly.
"""

from __future__ import annotations

import re


_TAG_RE = re.compile(r"<\s*(/?)\s*([a-zA-Z0-9]+)\b", re.IGNORECASE)
_HREF_RE = re.compile(r'href\s*=\s*"([^"]*)"', re.IGNORECASE)
_VAR_RE = re.compile(r"\[[A-Z0-9_]+\]")


def _tag_counts(html: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _slash, name in _TAG_RE.findall(html):
        key = name.lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def validate_translation(en: str, es: str) -> list[str]:
    """Return a list of human-readable warnings; empty list = clean."""
    warnings: list[str] = []

    en_tags = _tag_counts(en)
    es_tags = _tag_counts(es)
    if en_tags != es_tags:
        missing = {k: v - es_tags.get(k, 0) for k, v in en_tags.items() if v != es_tags.get(k, 0)}
        warnings.append(f"Tag count mismatch: {missing}")

    en_hrefs = sorted(_HREF_RE.findall(en))
    es_hrefs = sorted(_HREF_RE.findall(es))
    if en_hrefs != es_hrefs:
        warnings.append(f"href values changed: {en_hrefs} → {es_hrefs}")

    en_vars = sorted(set(_VAR_RE.findall(en)))
    es_vars = sorted(set(_VAR_RE.findall(es)))
    if en_vars != es_vars:
        warnings.append(f"Bracketed variables changed: {en_vars} → {es_vars}")

    if not es.strip():
        warnings.append("Empty translation")

    return warnings
