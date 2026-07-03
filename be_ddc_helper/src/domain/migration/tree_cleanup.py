"""Tree normalization helpers used before section discovery.

`unwrap_singletons` collapses redundant wrapper divs. `filter_meaningful`
drops spacer elements, empty leaves, and `#text` pseudo-children so
`group_into_rows` never sees geometry-less nodes.
"""
from __future__ import annotations

WRAPPER_TAGS = {'div', 'main', 'section', 'article'}
CONTAINER_LIKE_TAGS = {'div', 'section', 'article', 'main', 'aside'}


def unwrap_singletons(node: dict) -> dict:
    if not isinstance(node, dict):
        return node
    while (
        node.get('tag') in WRAPPER_TAGS
        and len(node.get('children', [])) == 1
        and not (node.get('text') or '').strip()
        and not node.get('src')
    ):
        only_child = node['children'][0]
        if not isinstance(only_child, dict):
            break
        node = only_child
    return node


def is_container_like(node: dict) -> bool:
    """Could this element hold a sub-section? True for wrapper divs/sections."""
    return isinstance(node, dict) and node.get('tag') in CONTAINER_LIKE_TAGS


def filter_meaningful(children: list) -> list:
    """Drop spacer elements (w<=2 or h<=2), empty leaves, and `#text` pseudo-
    children.

    The `#text` filter is structural: those pseudo-children are inline content
    of their parent emitted by the FE walker for mixed-inline shapes like
    `<p>Hello <strong>world</strong> tail</p>`. They carry no geometry, so
    they'd crash `group_into_rows` on `c['y']`. The text isn't lost — the
    parent (which ends up as a slot_node) still has them in its `children`
    array, and `editorial_chunk`'s `flatten_to_semantic` walks the full
    subtree later.
    """
    out = []
    for c in children:
        if not isinstance(c, dict):
            continue
        # #text pseudo-children: inline content, no geometry, don't participate
        # in section-level row/column discovery.
        if c.get('tag') == '#text':
            continue
        w, h = c.get('w', 0), c.get('h', 0)
        has_geom = w > 0 or h > 0
        if has_geom and (w <= 2 or h <= 2):
            continue
        if (not c.get('text') and not c.get('src')
                and not c.get('children')):
            continue
        out.append(c)
    return out
