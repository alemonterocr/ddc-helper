"""Truly-shared helpers used by ≥2 sibling modules in this package.

Kept intentionally small: only helpers that would otherwise force a circular
import land here. Everything module-local (chrome tags, button class words,
heading tags, semantic block tags) stays with its owner.
"""
from __future__ import annotations

import re

# Bootstrap col-width parser. Used by both chrome (`is_minor_col_chrome`) and
# discovery (`classify_columns_by_bootstrap`, `is_likely_column`), so it lives
# here to keep the import graph one-way.
COL_RE = re.compile(r'\bcol(?:-[a-z]+)?-(\d+)\b')


def get_bootstrap_col_width(node: dict) -> int | None:
    if not isinstance(node, dict):
        return None
    cls = node.get('cls') or ''
    m = COL_RE.findall(cls)
    return int(m[0]) if m else None
