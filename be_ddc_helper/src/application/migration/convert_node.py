"""Convert node — det_plan (algo shape) → section_plan (ColumnWidget shape).

Two responsibilities:
  1. Translate each `det_plan` entry into the ColumnWidget shape the FE
     consumes (`section_type`/`position`/`intent`/`slots[slot[widget]]`).
  2. Trim each section's slot count to the catalog maximum for its layout.

This node is intentionally LLM-free. The previous design wired an LLM
fallback here for ambiguous `empty-one` sections; it was deleted because
picking a DDC layout is a structural decision and the geometry analyzer is
the source of truth for structure. Letting the LLM second-guess layouts
produced unreliable output in testing — wrong layouts picked, slots merged
incorrectly, HTML rewritten when it shouldn't have been.

If a future node ever needs to mutate `section_plan` based on something the
LLM is genuinely good at (copy, intent, enrichment), that's the enrich node.
"""

from typing import Awaitable, Callable

from src.domain.models import MigrationState

Progress = Callable[[str], Awaitable[None]]


def build_convert_node(
    catalog: list[dict],
    progress: Progress | None = None,
):
    catalog_columns: dict[str, int] = {
        entry["sectionName"]: entry["columns"] for entry in catalog
    }

    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def convert(state: MigrationState) -> dict:
        all_items: list[dict] = []
        for det_section in state["det_plan"]:
            item = await _convert_one_section(
                det_section, catalog_columns, _progress, position=len(all_items)
            )
            all_items.append(item)
        return {"section_plan": all_items}

    return convert


# ── Per-section conversion ───────────────────────────────────────────────────


async def _convert_one_section(
    det_section: dict,
    catalog_columns: dict[str, int],
    _progress: Callable[[str], Awaitable[None]],
    position: int,
) -> dict:
    layout = det_section["section"]
    item_slots = [_translate_slot(slot_widgets) for slot_widgets in det_section["slots"]]
    item_slots = await _trim_to_catalog(item_slots, layout, catalog_columns, _progress)
    return {
        "section_type": layout,
        "position": position,
        "intent": _auto_intent(layout, item_slots),
        "slots": item_slots,
    }


def _translate_slot(slot_widgets: list[dict]) -> list[dict]:
    return [_translate_widget(w) for w in slot_widgets]


def _translate_widget(w: dict) -> dict:
    """Algo shape → ColumnWidget shape for one widget. Dispatches on type."""
    wtype = w.get("type")
    if wtype == "image":
        return {"widget_type": "image", "source_url": w.get("url") or ""}
    if wtype == "links":
        return {"widget_type": "links", "buttons": w.get("buttons") or []}
    if wtype in ("form", "contact_info", "hours"):
        # Marker widgets — execute layer fills in dealer master-record data
        # server-side. No payload here.
        return {"widget_type": wtype}
    return {"widget_type": "content", "html": w.get("html") or ""}


async def _trim_to_catalog(
    item_slots: list[list[dict]],
    layout: str,
    catalog_columns: dict[str, int],
    _progress: Callable[[str], Awaitable[None]],
) -> list[list[dict]]:
    """Trim slot count to the catalog maximum. Emits a progress warning when
    dropping happens so the specialist sees why the section changed shape."""
    expected = catalog_columns.get(layout)
    if expected is None or len(item_slots) <= expected:
        return item_slots

    dropped = len(item_slots) - expected
    await _progress(
        f"⚠ '{layout}' has {len(item_slots)} slots but catalog "
        f"expects {expected} — dropping {dropped} excess slot(s)."
    )
    return item_slots[:expected]


# ── Auto intent ──────────────────────────────────────────────────────────────


def _auto_intent(layout: str, item_slots: list[list[dict]]) -> str:
    """Terse intent string for deterministically-classified sections."""
    counts = _count_widget_types(item_slots)
    parts: list[str] = []
    if counts.get("content"):
        n = counts["content"]
        parts.append(f"{n} content widget{'s' if n > 1 else ''}")
    if counts.get("image"):
        n = counts["image"]
        parts.append(f"{n} image{'s' if n > 1 else ''}")

    summary = " + ".join(parts) if parts else "empty"
    return f"Auto: {layout} — {summary}"


def _count_widget_types(item_slots: list[list[dict]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for slot in item_slots:
        for w in slot:
            wt = w.get("widget_type", "content")
            counts[wt] = counts.get(wt, 0) + 1
    return counts
