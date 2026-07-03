"""
Simplified VIPS-inspired page segmentation.

Groups the top-level children of the page root into visual blocks using two passes:
  1. Background color — consecutive nodes sharing the same computed bg stay together.
  2. Structural HTML — if pass 1 yields one group, split at <section>/<article>/<hr>.

Before segmenting, single-child wrapper chains are unwrapped so the algorithm sees
the actual content nodes (e.g. body > main > section > [real blocks] → [real blocks]).

The result is a list of DOMNode subtrees, one per visual block.
The LLM never decides section boundaries — it only classifies and extracts content
for each pre-labelled block.
"""
from __future__ import annotations

from src.domain.models.dom_skeleton import DOMNode

# Tags that are structural page chrome — stripped before segmentation at any depth
_CHROME_TAGS = frozenset({'header', 'footer', 'nav', 'aside'})

# Tags that are always their own block
_HARD_BREAK_CONTAINERS = frozenset({'section', 'article'})

# Maximum levels to unwrap single-child containers
_MAX_UNWRAP_DEPTH = 6


def segment_page(root: DOMNode) -> list[DOMNode]:
    """Return an ordered list of visual segments from the page root.

    Each segment is a self-contained DOMNode subtree suitable for a single
    LLM classification call.
    """
    # Strip page chrome recursively before segmenting
    root = _strip_chrome(root)

    # Unwrap single-child wrapper chains so the segmenter sees the real content
    # nodes rather than a single opaque container.
    # e.g.  body > main > section > [hero, about, contact]
    #   →   [hero, about, contact]
    root = _unwrap_single_children(root)

    children = root.children
    if not children:
        return [root]

    # Pass 1: group by background color
    groups = _split_by_bg(children)

    # Pass 2: if still one group, try structural HTML boundaries
    if len(groups) == 1:
        groups = _split_by_structure(children)

    return [_wrap(g) for g in groups]


# ── Internal helpers ─────────────────────────────────────────────────────────

def _unwrap_single_children(node: DOMNode, depth: int = 0) -> DOMNode:
    """Walk down single-child chains until we reach a node with 0 or 2+ children.

    Stops at _MAX_UNWRAP_DEPTH to avoid descending into actual leaf content.
    """
    if depth >= _MAX_UNWRAP_DEPTH:
        return node
    if len(node.children) == 1 and node.children[0].children:
        return _unwrap_single_children(node.children[0], depth + 1)
    return node


def _strip_chrome(node: DOMNode) -> DOMNode:
    """Recursively remove header/footer/nav/aside nodes at any depth."""
    clean_children = [
        _strip_chrome(c)
        for c in node.children
        if c.tag not in _CHROME_TAGS
    ]
    if clean_children == node.children:
        return node  # nothing changed, avoid unnecessary copy
    return DOMNode(
        tag=node.tag,
        cls=node.cls,
        style=node.style,
        bg=node.bg,
        text=node.text,
        src=node.src,
        children=clean_children,
    )

def _split_by_bg(nodes: list[DOMNode]) -> list[list[DOMNode]]:
    """Group consecutive nodes that share the same effective background."""
    if not nodes:
        return []

    groups: list[list[DOMNode]] = []
    current: list[DOMNode] = []
    current_bg = nodes[0].bg or ""

    for node in nodes:
        node_bg = node.bg or current_bg   # inherit parent bg when not set
        if node_bg != current_bg and current:
            groups.append(current)
            current = []
            current_bg = node_bg
        current.append(node)

    if current:
        groups.append(current)

    return groups


def _split_by_structure(nodes: list[DOMNode]) -> list[list[DOMNode]]:
    """Split at <hr>, <section>, and <article> boundaries."""
    groups: list[list[DOMNode]] = []
    current: list[DOMNode] = []

    for node in nodes:
        if node.tag == 'hr':
            if current:
                groups.append(current)
                current = []
        elif node.tag in _HARD_BREAK_CONTAINERS:
            if current:
                groups.append(current)
                current = []
            groups.append([node])
        else:
            current.append(node)

    if current:
        groups.append(current)

    return groups if groups else [nodes]


def _wrap(nodes: list[DOMNode]) -> DOMNode:
    """Wrap a group of sibling nodes into a synthetic container node."""
    if len(nodes) == 1:
        return nodes[0]
    return DOMNode(
        tag="div",
        cls="",
        bg=nodes[0].bg or "",
        children=nodes,
    )
