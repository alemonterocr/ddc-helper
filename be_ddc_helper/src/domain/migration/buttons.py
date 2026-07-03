"""Button detection, classification, and DTO extraction.

Detection runs on flat-list elements after `flatten_to_semantic`, so the
original sibling context is gone. `is_button_anchor` scores each candidate
against five signals (tag, class words, background color, geometry) and
requires ≥2 to accept.

`extract_button` produces the DTO shape the execute layer's ButtonDTO expects.
"""
from __future__ import annotations

import re

_BUTTON_CLASS_WORDS = {'btn', 'button', 'cta'}
_BUTTON_PRIMARY_WORDS = {'primary', 'main', 'cta', 'success'}
_BUTTON_SECONDARY_WORDS = {'secondary', 'outline', 'default'}


def _node_class_words(node: dict) -> set[str]:
    cls = (node.get('cls') or '').lower()
    return set(re.split(r'[\s_-]+', cls)) if cls else set()


def _has_button_class(node: dict) -> bool:
    return bool(_node_class_words(node) & _BUTTON_CLASS_WORDS)


def is_button_anchor(node: dict) -> bool:
    """Multi-signal button classifier — runs on flat-list elements where the
    original sibling context is gone. Signals available on the node alone:

      S1 (required) — tag is <a> / <button>, OR role="button" on any tag.
                      If False, return False immediately.
      K1 — class words contain 'btn' / 'button' / 'cta'. WEIGHT 2 (strong).
      C1 — `bg` set on the node itself (non-transparent, different from parent).
      G1 — h > fontSize × 1.5 (button has visible padding pushing height up).
      G2 — w ≥ 80.

    Threshold ≥ 2. A class-word match alone is enough (K1=2). A class-less
    button with both geometry signals + bg also crosses (G1+G2+C1=3).
    Inline links score 0–1 and don't pass.
    """
    if not isinstance(node, dict):
        return False
    tag = node.get('tag', '')
    role = (node.get('role') or '').lower()
    if tag not in ('a', 'button') and role != 'button':
        return False

    score = 0
    if _has_button_class(node):
        score += 2
    if node.get('bg'):
        score += 1
    h = node.get('h', 0)
    fs = node.get('fontSize', 0)
    if h > 0 and fs > 0 and h > fs * 1.5:
        score += 1
    if node.get('w', 0) >= 80:
        score += 1

    return score >= 2


def is_button_group_container(node: dict) -> bool:
    """A wrapper like <p class="hidden-xxs"><a class="btn">…</a><a class="btn">…</a></p>
    where every element child is a button anchor and there's no real text content
    between them. Treated by `flatten_to_semantic` as a transparent wrapper so
    the buttons surface as flat-list siblings, ready for grouping.
    """
    if not isinstance(node, dict):
        return False
    if node.get('tag') not in ('p', 'div', 'span'):
        return False
    children = node.get('children', [])
    if not children:
        return False

    found_button = False
    for c in children:
        if not isinstance(c, dict):
            return False
        ctag = c.get('tag', '')
        if ctag == '#text':
            # Allow whitespace-only pseudo-text (shouldn't survive the FE
            # walker's filter, but be defensive); anything with real text
            # disqualifies — that's an inline-link scenario, not a button row.
            if (c.get('text') or '').strip():
                return False
            continue
        if ctag == 'br':
            continue  # transparent separator between buttons
        if ctag not in ('a', 'button'):
            return False
        if not _has_button_class(c):
            return False  # an anchor without button styling — treat as link
        found_button = True

    return found_button


def classify_button_style(node: dict) -> str:
    """Map class word hints to one of DDC's button styles. Defaults to 'primary'
    when ambiguous — the execute layer's ButtonDTO defaults to 'primary' too."""
    words = _node_class_words(node)
    if words & _BUTTON_PRIMARY_WORDS:
        return 'primary'
    if words & _BUTTON_SECONDARY_WORDS:
        return 'secondary'
    return 'primary'


def extract_button(node: dict) -> dict:
    """Build a button DTO (matches execute_router.ButtonDTO shape)."""
    return {
        'text': _extract_label(node),
        'href': node.get('href') or '',
        'style': classify_button_style(node),
        'target': node.get('target') or '_self',
        'link_class': '',
    }


def _extract_label(node: dict) -> str:
    """Depth-first concatenation of all text descendants. Handles nested
    shapes like <a><h4><i></i>Label</h4></a> where the label text is two
    levels deep behind an icon span."""
    if not isinstance(node, dict):
        return ''
    parts: list[str] = []
    own = (node.get('text') or '').strip()
    if own:
        parts.append(own)
    for ch in node.get('children', []):
        s = _extract_label(ch)
        if s:
            parts.append(s)
    return ' '.join(parts).strip()


def collect_button_group_size(elements: list, start_idx: int) -> int:
    """Count consecutive button anchors starting at elements[start_idx].
    Adjacency in the flat list approximates same-parent (flattening preserves
    document order and only opens button-group wrappers transparently)."""
    n = len(elements)
    end = start_idx
    while end < n and is_button_anchor(elements[end]):
        end += 1
    return end - start_idx
