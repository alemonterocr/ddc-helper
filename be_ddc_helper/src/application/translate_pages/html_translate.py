"""Translate a widget's HTML by translating only its text nodes.

The markup — tags, attributes, inline styles, hrefs — never touches the LLM.
We parse the fragment, pull out the visible text strings, translate just those
(batched), and drop the translations back into the same nodes. This makes
translation robust to widget size (only text is sent, never the megabytes of
boilerplate style attributes), structurally exact by construction, and immune
to the output-truncation failure that an "emit the whole HTML" approach hits.

Robustness to LLM nondeterminism lives in the adapter: `translate_text_segments`
matches results back to inputs by id and fills any the model drops with the
original English, so it always returns one entry per input. This module treats a
wrong-length batch as a soft failure — it keeps the English for that batch rather
than crashing or (worse) misaligning every fragment after a dropped item.

Pure except for the injected `translate_batch` callable, so it is unit-testable
with a fake translator.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from bs4 import BeautifulSoup, Comment, NavigableString

TranslateBatch = Callable[[list[str]], Awaitable[list[str]]]

# Text inside these elements is code/markup, never user-visible copy.
_SKIP_PARENTS = {"script", "style"}
# Bound each LLM call so a widget with hundreds of segments still translates in
# small batches. Smaller batches also drop-less: fewer items per call to lose.
_BATCH_SIZE = 20


def _translatable_nodes(soup: BeautifulSoup) -> list[NavigableString]:
    nodes: list[NavigableString] = []
    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        parent = node.parent
        if parent is not None and parent.name in _SKIP_PARENTS:
            continue
        if not node.strip():
            continue
        nodes.append(node)
    return nodes


def _reattach_whitespace(original: str, translated: str) -> str:
    """Keep the node's original leading/trailing whitespace (significant for
    inline layout); only the trimmed text is translated."""
    leading = original[: len(original) - len(original.lstrip())]
    trailing = original[len(original.rstrip()):]
    return f"{leading}{translated.strip()}{trailing}"


async def _translate_in_batches(
    segments: list[str], translate_batch: TranslateBatch
) -> tuple[list[str], int]:
    """Return (translations, untranslated_count).

    `translations` is always the same length as `segments`. A batch that comes
    back the wrong length (LLM dropped/added items, or the call failed) is kept
    in English rather than misaligned — never raise, never shift positions.
    """
    out: list[str] = []
    untranslated = 0
    for start in range(0, len(segments), _BATCH_SIZE):
        chunk = segments[start:start + _BATCH_SIZE]
        try:
            translated = await translate_batch(chunk)
        except Exception:
            translated = []
        if len(translated) == len(chunk):
            out.extend(translated)
        else:
            out.extend(chunk)  # keep English for this batch, stay aligned
            untranslated += len(chunk)
    return out, untranslated


async def translate_widget_html(
    html: str, translate_batch: TranslateBatch
) -> tuple[str, int, int]:
    """Return (translated_html, segment_count, untranslated_count).

    Never raises on a translator hiccup: untranslated fragments stay in English
    and are reported via `untranslated_count` so the caller can warn or fail.
    """
    soup = BeautifulSoup(html, "html.parser")
    nodes = _translatable_nodes(soup)
    if not nodes:
        return html, 0, 0

    raws = [str(node) for node in nodes]
    stripped = [raw.strip() for raw in raws]
    translations, untranslated = await _translate_in_batches(stripped, translate_batch)

    for node, raw, translated in zip(nodes, raws, translations):
        node.replace_with(NavigableString(_reattach_whitespace(raw, translated)))

    return str(soup), len(nodes), untranslated
