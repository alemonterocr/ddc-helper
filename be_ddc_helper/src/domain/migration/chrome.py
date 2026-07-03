"""Chrome (page furniture) detection and pruning.

Two flavors of chrome:
- Definite chrome (semantic tags, w-chrome widget UI): hard-dropped by
  `strip_chrome`, no rescue.
- Candidate chrome (class-word matches on container tags, minor sidebar-shaped
  columns): kept in the tree with `_chrome_candidate: True` so the analyze
  router can ask the LLM whether to KEEP or DROP them.

`has_content_anchor` rescues candidate-shape nodes whose subtree carries
high-value signals (forms, phone numbers, hours tables) — dealer identity
that shouldn't be dropped even from a chrome-classed sidebar.
"""
from __future__ import annotations

import re

from src.domain.migration._atoms import get_bootstrap_col_width

CHROME_CLASS_WORDS = {
    'navbar', 'sidebar', 'breadcrumb',
    'cookie', 'chat-now', 'chat-widget', 'social-icons', 'subscribe',
    # Blog-post chrome additions: post-navigation prev/next links,
    # post-tagging/category metadata blocks, and third-party attribution
    # widgets. All meaningless on a migrated DDC page.
    'navigation', 'postmetadata', 'bookmarkify',
}
CHROME_TAGS = {'header', 'footer', 'nav', 'aside'}
# <p> is included so a <p class="postmetadata"> can be flagged. Other
# paragraph chrome (footnotes, attribution lines) follows the same shape.
CONTAINER_TAGS_FOR_CHROME_CHECK = {'div', 'section', 'aside', 'ul', 'a', 'p'}

# Embedded-widget UI hard-drops (video player chrome and the like). These
# match as substrings of the full class string — `w-chrome notranslate`
# matches `w-chrome`. Always pruned, no LLM review. The actual MEDIA payload
# (video swatch, image thumbnail) sits in a sibling subtree and survives.
WIDGET_CHROME_CLASS_PATTERNS = ('w-chrome',)


def is_widget_chrome(node: dict) -> bool:
    if not isinstance(node, dict):
        return False
    cls = (node.get('cls') or '').lower()
    return any(p in cls for p in WIDGET_CHROME_CLASS_PATTERNS)


def has_content_anchor(node: dict) -> bool:
    """Return True if the subtree contains high-value content signals.

    Mirrors the subtreeHasContentAnchor rescue logic in extractSkeleton.ts.
    Used to override class-based chrome classification when a node has a
    chrome-sounding class (e.g. 'sideBar') but actually holds page content.
    """
    if not isinstance(node, dict):
        return False
    tag = node.get('tag', '')
    # Form elements — lead-gen forms are never chrome
    if tag in ('form', 'input', 'textarea', 'select'):
        return True
    # Phone number in text content — dealer contact info
    text = node.get('text') or ''
    if re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text):
        return True
    # Hours table — day-of-week labels inside a table
    if tag == 'table' and re.search(
        r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', text, re.I
    ):
        return True
    return any(has_content_anchor(c) for c in node.get('children', []))


def is_definite_chrome(node: dict) -> bool:
    """Semantic chrome tags — always pruned unconditionally, no rescue possible."""
    return isinstance(node, dict) and node.get('tag') in CHROME_TAGS


def is_chrome_candidate(node: dict) -> bool:
    """Chrome by class name but no content anchor — ambiguous, flagged for LLM review.

    These nodes are kept in the tree with _chrome_candidate: True so the
    analyze router can ask the LLM whether to KEEP or DROP them.
    """
    if not isinstance(node, dict):
        return False
    if node.get('tag') not in CONTAINER_TAGS_FOR_CHROME_CHECK:
        return False
    class_ = (node.get('cls') or '').lower()
    class_words = set(re.split(r'[\s-]+', class_))
    if not (class_words & CHROME_CLASS_WORDS):
        return False
    # Content anchor present → rescued, not a candidate
    return not has_content_anchor(node)


def is_chrome(node: dict) -> bool:
    """Backward-compatible: True for definite or candidate chrome."""
    return is_definite_chrome(node) or is_chrome_candidate(node)


def is_minor_col_chrome(node: dict, siblings: list) -> bool:
    """Geometry-driven chrome candidate: a Bootstrap col ≤4 sitting next to
    a sibling col ≥8.

    Catches the sidebar-shaped column whose class carries no chrome word at
    all (the col-md-3 dealer-blog case). Applies content-anchor rescue so
    dealer identity signals (phone numbers, hours tables) in sidebars
    survive. Sidebars without such signals are flagged for LLM review.
    """
    if not isinstance(node, dict):
        return False
    if node.get('tag') not in CONTAINER_TAGS_FOR_CHROME_CHECK:
        return False
    width = get_bootstrap_col_width(node)
    if width is None or width > 4:
        return False
    for s in siblings:
        if s is node or not isinstance(s, dict):
            continue
        s_width = get_bootstrap_col_width(s)
        if s_width is not None and s_width >= 8:
            return not has_content_anchor(node)
    return False


def strip_chrome(node: dict) -> dict:
    if not isinstance(node, dict):
        return node
    out = dict(node)
    siblings = node.get('children', [])
    new_children = []
    for c in siblings:
        if is_definite_chrome(c) or is_widget_chrome(c):
            continue  # hard prune — no rescue
        processed = strip_chrome(c)
        if is_chrome_candidate(c) or is_minor_col_chrome(c, siblings):
            processed = dict(processed)
            processed['_chrome_candidate'] = True
        new_children.append(processed)
    out['children'] = new_children
    return out
