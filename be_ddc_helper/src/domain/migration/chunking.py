"""Editorial chunking + HTML rendering.

Once a slot node is identified, `editorial_chunk` walks its subtree, promotes
buttons/images to their own widgets, and splits stacked content at heading
boundaries.

`render_html` is the outbound HTML serializer used by both chunking and
`chrome_review_node` (which needs to render candidate subtrees for LLM review).
"""
from __future__ import annotations

from html import escape as html_escape

from src.domain.migration.buttons import (
    collect_button_group_size,
    extract_button,
    is_button_anchor,
    is_button_group_container,
)

HEADING_TAGS = {'h1', 'h2', 'h3', 'h4'}
SEMANTIC_BLOCK_TAGS = {
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'ul', 'ol', 'dl', 'blockquote', 'pre',
    'table', 'form', 'hr',
}


def is_heading(node: dict) -> bool:
    return isinstance(node, dict) and node.get('tag') in HEADING_TAGS


def is_standalone_image(node: dict) -> bool:
    if not isinstance(node, dict):
        return False
    # ── <img> tag ─────────────────────────────────────────────────────────────
    if node.get('tag') == 'img':
        return True
    # ── wrapper around a single <img> or <picture> ────────────────────────────
    # `<p>` is included for the WordPress/CMS pattern `<p><img/></p>` which is
    # structurally an image block, not a paragraph.
    if node.get('tag') in ('div', 'figure', 'picture', 'a', 'p'):
        kids = node.get('children', [])
        text = (node.get('text') or '').strip()
        if not text and len(kids) == 1 and isinstance(kids[0], dict):
            if kids[0].get('tag') in ('img', 'picture'):
                return True
    # ── background-image div (role="img" pattern or img-background class) ─────
    # Matches: <div style="background-image:url(...)" role="img"> or
    #          <div class="img-background ..." style="background-image:url(...)">
    # Guard: must have a URL AND no text AND no content-bearing children so we
    # don't misclassify hero sections that have bg images + child text/buttons.
    if node.get('bgImageSrc'):
        text = (node.get('text') or '').strip()
        kids = node.get('children', [])
        has_content_children = any(
            (c.get('text') or '').strip() or c.get('src') or c.get('bgImageSrc')
            for c in kids if isinstance(c, dict)
        )
        if not text and not has_content_children:
            return True
    return False


def get_image_url(node: dict) -> str | None:
    """Extract image URL from a node. Handles <img src>, bg-image divs, and wrappers."""
    if not isinstance(node, dict):
        return None
    # <img> tag
    if node.get('tag') == 'img':
        return node.get('src') or None
    # Background-image div
    if node.get('bgImageSrc'):
        return node.get('bgImageSrc')
    # Recurse into children (covers <figure><img>, <a><img>, etc.)
    for ch in node.get('children', []):
        url = get_image_url(ch)
        if url:
            return url
    return None


def flatten_to_semantic(node: dict, acc: list | None = None) -> list:
    """Walk subtree, collect semantic elements in document order."""
    if acc is None:
        acc = []
    if not isinstance(node, dict):
        return acc
    tag = node.get('tag', '')
    text = (node.get('text') or '').strip()
    children = node.get('children', [])

    # Button anchors emit as a unit BEFORE any other branch. Without this an
    # `<a class="btn"><h4>…</h4></a>` falls through to the recurse path (because
    # it has element children and no own text), the <a> never reaches the
    # detector, and we lose the button entirely. Also handles the
    # `<a class="btn"><img/></a>` case — class signal beats the image one.
    if is_button_anchor(node):
        acc.append(node)
        return acc
    # Standalone-image check — `<p><img/></p>` is emitted as its own image
    # block instead of being absorbed by the SEMANTIC_BLOCK_TAGS branch.
    if is_standalone_image(node):
        acc.append(node)
        return acc
    # Button-group wrappers (e.g. <div id="sideBtns"><a class="btn">…</a>…</div>
    # or <p class="hidden-xxs"><a class="btn">…</a><a class="btn">…</a></p>) —
    # treat as transparent. Recurse so each button surfaces in the flat list
    # and editorial_chunk can group adjacent ones into a single Links widget.
    if is_button_group_container(node):
        for ch in node.get('children', []):
            flatten_to_semantic(ch, acc)
        return acc
    if tag in SEMANTIC_BLOCK_TAGS:
        acc.append(node)
        return acc
    if not children and text:
        acc.append(node)
        return acc
    for ch in children:
        flatten_to_semantic(ch, acc)
    return acc


def render_html(node: dict) -> str:
    if not isinstance(node, dict):
        return ''
    tag = node.get('tag', 'div')
    # Pseudo-text node emitted by the FE walker for mixed inline content
    # like <p>Hello <strong>x</strong> tail</p>. Renders as bare escaped
    # text with no wrapping tag.
    if tag == '#text':
        return html_escape(node.get('text') or '')
    if tag == 'img':
        src = html_escape(node.get('src') or '')
        alt = html_escape(node.get('text') or '')
        alt_attr = f' alt="{alt}"' if alt else ''
        return f'<img src="{src}"{alt_attr}/>'
    if tag in ('br', 'hr'):
        return f'<{tag}/>'
    # Build attribute string — href for <a>, class when present
    attrs = ''
    if tag == 'a':
        href = node.get('href') or ''
        if href:
            attrs += f' href="{html_escape(href)}"'
    cls = node.get('cls') or ''
    if cls:
        attrs += f' class="{html_escape(cls)}"'
    text = node.get('text') or ''
    inner = html_escape(text)
    for ch in node.get('children', []):
        inner += render_html(ch)
    return f'<{tag}{attrs}>{inner}</{tag}>'


def first_text(node: dict, max_len: int = 70) -> str:
    if not isinstance(node, dict):
        return ''
    t = (node.get('text') or '').strip()
    if t:
        return t[:max_len]
    for ch in node.get('children', []):
        s = first_text(ch, max_len)
        if s:
            return s
    return ''


def find_split_level(elements: list) -> int | None:
    levels = set()
    for el in elements:
        tag = el.get('tag', '')
        if tag in HEADING_TAGS:
            levels.add(int(tag[1]))
    levels.discard(1)
    if not levels:
        return None
    return min(levels)


def should_split_at(el: dict, split_level: int | None) -> bool:
    if split_level is None:
        return False
    tag = el.get('tag', '')
    if tag not in HEADING_TAGS:
        return False
    return int(tag[1]) <= split_level


def editorial_chunk(slot_node: dict) -> list[dict]:
    if not isinstance(slot_node, dict):
        return []
    elements = flatten_to_semantic(slot_node)

    if not elements:
        text = (slot_node.get('text') or '').strip()
        if text:
            return [{'type': 'content', 'html': render_html(slot_node), 'preview': text[:70]}]
        return []

    split_level = find_split_level(elements)
    widgets: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        preview = ''
        for n in current:
            preview = first_text(n)
            if preview:
                break
        html = '\n'.join(render_html(c) for c in current)
        widgets.append({'type': 'content', 'html': html, 'preview': preview, 'node_count': len(current)})
        current = []

    i = 0
    while i < len(elements):
        el = elements[i]
        # Button detection runs FIRST. An <a class="btn"><img/></a> would
        # otherwise be misclassified as a standalone image; checking buttons
        # first lets the class word win.
        if is_button_anchor(el):
            group_size = collect_button_group_size(elements, i)
            group = elements[i:i + group_size]
            flush()
            widgets.append({
                'type': 'links',
                'buttons': [extract_button(b) for b in group],
            })
            i += group_size
            continue
        if is_standalone_image(el):
            flush()
            widgets.append({'type': 'image', 'url': get_image_url(el)})
        elif should_split_at(el, split_level) and current:
            flush()
            current.append(el)
        elif el.get('tag') == 'hr':
            flush()
        else:
            current.append(el)
        i += 1

    flush()
    return widgets
