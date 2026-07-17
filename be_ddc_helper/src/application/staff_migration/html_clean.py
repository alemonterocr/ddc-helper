"""Strip non-content noise from a raw staff page before sending it to the LLM.

A captured staff page is mostly things the parser never needs — `<script>`,
`<style>`, inline SVG icons, `<link>`/`<meta>` head junk, and huge inline
`style="…"` attributes. Sending all of it inflates input tokens (and latency
and cost) without helping extraction. This removes the noise while preserving
the visible content and structure (tags, text, class names, image/link hrefs)
the staff prompt relies on.

Lives in the application layer, not `domain/` — BeautifulSoup is an external
import the constitution forbids in `domain/`. Fail-safe: any parse error
returns the original HTML unchanged, so a weird page degrades to today's
behavior rather than losing content.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment

# Elements that never carry staff content — dropped whole.
_DROP_TAGS = ("script", "style", "noscript", "svg", "link", "meta", "iframe")
# Attributes that are pure visual weight (the big inline style blobs) — dropped.
_DROP_ATTRS = ("style",)
_BLANK_LINES = re.compile(r"\n\s*\n+")


def strip_noise(html: str) -> str:
    """Return `html` with scripts/styles/svg/head-junk and inline style
    attributes removed. Returns the input unchanged on empty input or any
    parse failure."""
    if not html or not html.strip():
        return html
    try:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(_DROP_TAGS):
            tag.decompose()

        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        for element in soup.find_all(True):
            for attr in _DROP_ATTRS:
                if attr in element.attrs:
                    del element[attr]

        cleaned = str(soup)
        return _BLANK_LINES.sub("\n", cleaned)
    except Exception:
        return html
