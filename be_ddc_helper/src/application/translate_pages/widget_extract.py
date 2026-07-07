"""Extract editable widgets from a DDC page render, paired across locales.

Lives in the application layer, not `domain/` — BeautifulSoup is an external
import, which the constitution forbids inside `domain/`.

DDC marks editable regions with two class signatures inside `div.main`:
  - `text-content-container` → a plain content widget
  - `editable-raw-content`   → a RAW HTML widget
Each carries an `id` like `SITEBUILDER_ALE_MONTERO_1:content1-editable`, which is
both the pairing key across locales and the save `windowId`.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

_CONTENT_CLASS = "text-content-container"
_RAW_CLASS = "editable-raw-content"


def _find_main(html: str) -> Tag | None:
    """The `div.main` holds the representative sections + widgets."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("div", class_="main")
    return main if isinstance(main, Tag) else None


def _widget_type(node: Tag) -> str | None:
    classes = node.get("class") or []
    if _CONTENT_CLASS in classes:
        return "content"
    if _RAW_CLASS in classes:
        return "raw"
    return None


def _collect_widgets(html: str) -> dict[str, dict]:
    """Map window_id → {window_id, widget_type, inner_html} for one render."""
    main = _find_main(html)
    if main is None:
        return {}

    found: dict[str, dict] = {}
    for node in main.find_all("div", id=True):
        widget_type = _widget_type(node)
        if widget_type is None:
            continue
        window_id = str(node.get("id") or "").strip()
        if not window_id or window_id in found:
            continue
        found[window_id] = {
            "window_id": window_id,
            "widget_type": widget_type,
            "inner_html": node.decode_contents(),
        }
    return found


def extract_widgets(en_html: str, es_html: str) -> list[dict]:
    """Return paired widgets across both locales, keyed by window_id.

    Each entry: {window_id, widget_type, en_html, es_html}. The English side is
    authoritative for ordering and widget type; `es_html` is "" when the widget
    is absent from the es render.
    """
    en_widgets = _collect_widgets(en_html)
    es_widgets = _collect_widgets(es_html)

    paired: list[dict] = []
    for window_id, en in en_widgets.items():
        es = es_widgets.get(window_id)
        paired.append(
            {
                "window_id": window_id,
                "widget_type": en["widget_type"],
                "en_html": en["inner_html"],
                "es_html": es["inner_html"] if es else "",
            }
        )
    return paired
