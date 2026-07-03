from src.domain.errors import LLMOutputParseError
from src.domain.models import ColumnWidget, SectionPlan, SectionPlanItem


def parse_section_plan(tool_input: dict) -> SectionPlan:
    raw_sections = tool_input.get("sections")
    if not isinstance(raw_sections, list):
        raise LLMOutputParseError("Expected 'sections' list in tool response")

    items = [_parse_item(raw, index) for index, raw in enumerate(raw_sections)]
    return SectionPlan(items=items)


def _parse_item(raw: dict, index: int) -> SectionPlanItem:
    try:
        # ── New format: slots[][]  (matches deterministic algo + updated prompt) ──
        if "slots" in raw:
            slots = [
                [_parse_widget(w) for w in slot]
                for slot in raw["slots"]
            ]
        # ── Legacy format: columns[]  (one widget per slot, old prompt) ──────────
        else:
            slots = [
                [_parse_widget_legacy(c)]
                for c in raw.get("columns", [])
            ]

        return SectionPlanItem(
            section_type=raw["section_type"],
            position=raw["position"],
            intent=raw["intent"],
            slots=slots,
        )
    except (KeyError, TypeError) as error:
        raise LLMOutputParseError(f"Invalid section at index {index}: {error}") from error


def _parse_widget(w: dict) -> ColumnWidget:
    """Parse a widget in the new format: {type, html?, url?, preview?}"""
    wtype = w.get("type", "content")
    return ColumnWidget(
        widget_type="image" if wtype == "image" else "content",
        html=w.get("html"),
        source_url=w.get("url"),
    )


def _parse_widget_legacy(c: dict) -> ColumnWidget:
    """Parse a widget in the legacy format: {widget_type, html?, source_url?}"""
    return ColumnWidget(
        widget_type=c["widget_type"],
        html=c.get("html"),
        source_url=c.get("source_url"),
    )
