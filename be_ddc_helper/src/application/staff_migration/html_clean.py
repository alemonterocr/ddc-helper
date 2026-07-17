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


# Character budget per extraction chunk. A large roster (dozens of staff) can't
# fit in one LLM response — the JSON output truncates. Splitting the page into
# windows bounds each call's output and lets them run in parallel. ~24k chars ≈
# ~6-8k input tokens per chunk, whose staff JSON fits comfortably in 8192 out.
_CHUNK_CHARS = 24000
_CHUNK_OVERLAP = 2000


def chunk_html(html: str, max_chars: int = _CHUNK_CHARS, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split HTML into overlapping windows for batched staff extraction.

    Returns `[html]` unchanged when it already fits. Windows overlap so a staff
    card straddling a boundary appears whole in at least one chunk; the caller
    dedupes the results. Splits are nudged to the next `>` so tags aren't cut
    mid-token (extraction tolerates minor fragmentation regardless).
    """
    if len(html) <= max_chars:
        return [html]

    chunks: list[str] = []
    start = 0
    n = len(html)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            gt = html.find(">", end)
            if gt != -1 and gt - end < 500:
                end = gt + 1
        chunks.append(html[start:end])
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def dedup_staff(members: list[dict]) -> list[dict]:
    """Merge staff dicts from overlapping chunks, keyed by email then name+dept.

    First occurrence wins. Rows with neither an email nor a name are dropped."""
    seen: set[str] = set()
    out: list[dict] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        email = str(m.get("email") or "").strip().lower()
        name = str(m.get("name") or "").strip().lower()
        dept = str(m.get("department") or "").strip().lower()
        key = email or (f"{name}|{dept}" if name else "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out
