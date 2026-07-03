"""Enrich node — batched LLM call for HTML beautify + intent copywriting.

Input: state["section_plan"] in ColumnWidget shape from convert_node.
Output: state["section_plan"] (enriched HTML + LLM-written intents, positions
renumbered).

When `enabled=False` or `llm is None`, the section_plan passes through with
auto intents and positions renumbered — no LLM call. On any beautifier
failure the original HTML and auto intents are preserved.

Logic lifted from `analyze_router.py` (Step 4 — HTML beautifier).
"""

from typing import Awaitable, Callable

from src.domain.models import MigrationState
from src.ports.outbound import LLMPort

Progress = Callable[[str], Awaitable[None]]

# Section index, slot index, widget index — where each snippet lives.
Loc = tuple[int, int, int]


# ── Node factory ─────────────────────────────────────────────────────────────


def build_enrich_node(
    llm: LLMPort | None,
    progress: Progress | None = None,
    enabled: bool = True,
):
    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def enrich(state: MigrationState) -> dict:
        all_items = list(state.get("section_plan") or [])

        if enabled and llm is not None and all_items:
            enrich_input, slot_locs = _build_enrich_input(all_items)
            if enrich_input:
                await _progress("AI is cleaning content & writing intents")
                await _try_enrich(llm, all_items, enrich_input, slot_locs, _progress)

        _renumber_positions(all_items)
        await _progress(f"✓ Plan ready — {len(all_items)} section(s)")
        return {"section_plan": all_items}

    return enrich


# ── Build the LLM input ──────────────────────────────────────────────────────


def _build_enrich_input(
    all_items: list[dict],
) -> tuple[list[dict], dict[str, list[Loc]]]:
    """Produce the LLM request list plus a map from section id → snippet
    locations so we can write LLM-cleaned HTML back to the right slot."""
    enrich_input: list[dict] = []
    slot_locs: dict[str, list[Loc]] = {}

    for i, item in enumerate(all_items):
        sec_id = str(i)
        locs, snippets, slot_summary = _summarize_section(i, item)
        slot_locs[sec_id] = locs
        enrich_input.append({
            "id": sec_id,
            "section_type": item["section_type"],
            "slot_summary": slot_summary,
            "snippets": snippets,
        })
    return enrich_input, slot_locs


def _summarize_section(
    sec_idx: int, item: dict
) -> tuple[list[Loc], list[str], str]:
    """Walk one section's slots — collect content snippets + build the
    human-readable per-section slot summary for the LLM prompt."""
    locs: list[Loc] = []
    snippets: list[str] = []
    slot_parts: list[str] = []

    for s_idx, slot in enumerate(item.get("slots", [])):
        widget_labels: list[str] = []
        for w_idx, widget in enumerate(slot or []):
            label = _label_widget(widget)
            if label is None:
                continue
            widget_labels.append(label)
            if label == "content":
                locs.append((sec_idx, s_idx, w_idx))
                snippets.append(widget["html"])
        slot_parts.append(
            f"slot {s_idx + 1}: {', '.join(widget_labels) or 'empty'}"
        )

    return locs, snippets, " | ".join(slot_parts)


def _label_widget(widget: dict) -> str | None:
    """One-token label for the LLM's slot_summary line. None means skip."""
    wt = widget.get("widget_type", "")
    if wt == "content" and widget.get("html"):
        return "content"
    if wt == "image":
        url = widget.get("source_url", "")
        fname = url.rsplit("/", 1)[-1].split("?")[0] if url else "image"
        return f"image({fname})"
    return None


# ── Run the LLM + apply results ──────────────────────────────────────────────


async def _try_enrich(
    llm: LLMPort,
    all_items: list[dict],
    enrich_input: list[dict],
    slot_locs: dict[str, list[Loc]],
    _progress: Callable[[str], Awaitable[None]],
) -> None:
    try:
        results = await llm.enrich_content(enrich_input)
    except Exception:
        await _progress(
            "⚠ Enrichment failed — keeping original HTML and auto intents"
        )
        return
    _apply_enrich_results(all_items, slot_locs, results)


def _apply_enrich_results(
    all_items: list[dict],
    slot_locs: dict[str, list[Loc]],
    results: list[dict],
) -> None:
    for result in results:
        sec_id = str(result.get("id", ""))
        item_idx = _parse_item_idx(sec_id, len(all_items))
        if item_idx is None:
            continue
        _apply_one_result(all_items, slot_locs.get(sec_id, []), item_idx, result)


def _parse_item_idx(sec_id: str, count: int) -> int | None:
    if not sec_id or not sec_id.isdigit():
        return None
    idx = int(sec_id)
    return idx if 0 <= idx < count else None


def _apply_one_result(
    all_items: list[dict],
    locs: list[Loc],
    item_idx: int,
    result: dict,
) -> None:
    new_intent = result.get("intent", "").strip()
    if new_intent:
        all_items[item_idx]["intent"] = new_intent

    for (i, s_idx, w_idx), html in zip(locs, result.get("snippets") or []):
        if html:
            all_items[i]["slots"][s_idx][w_idx]["html"] = html


# ── Final pass ───────────────────────────────────────────────────────────────


def _renumber_positions(all_items: list[dict]) -> None:
    for idx, item in enumerate(all_items):
        item["position"] = idx
