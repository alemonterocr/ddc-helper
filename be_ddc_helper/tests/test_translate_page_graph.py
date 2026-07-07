"""Unit tests for the page-translation graph: check logic, fan-out, event order."""

import pytest

from src.application.translate_pages.check_node import build_check_node
from src.application.translate_pages.routing import route_to_widget_branches
from src.application.translate_pages.translate_page_graph import (
    build_translate_page_graph,
)


class FakeLLM:
    """Minimal LLMPort double.

    - judge_translation: a non-empty es is a genuine translation UNLESS it
      contains "PLACEHOLDER" (stand-in for DDC's Spanish filler).
    - translate_label_with_tools: echoes the English so the structural validator
      stays clean and the label graph returns status "ready".
    """

    usage_log: list = []

    def reset_usage(self) -> None:
        pass

    async def judge_translation(self, en_html, es_html, dealer_name):
        return {"ok": "PLACEHOLDER" not in es_html, "reason": ""}

    async def translate_label_with_tools(self, en_html, dealer_name, glossary_lookup, extra_hint=""):
        return {"translation": en_html, "reasoning": "echoed"}


def _content(window_id, en, es):
    return {"window_id": window_id, "widget_type": "content", "en_html": en, "es_html": es}


# ── check node ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_empty_es_needs_translation():
    check = build_check_node(FakeLLM())
    out = await check({"candidates": [_content("a", "<p>Hi</p>", "")], "dealer_name": "D"})
    assert [w["window_id"] for w in out["to_translate"]] == ["a"]
    assert out["skipped"] == []


@pytest.mark.asyncio
async def test_check_es_equals_en_needs_translation():
    check = build_check_node(FakeLLM())
    out = await check({"candidates": [_content("a", "<p>Hi</p>", "<p>Hi</p>")], "dealer_name": "D"})
    assert [w["window_id"] for w in out["to_translate"]] == ["a"]


@pytest.mark.asyncio
async def test_check_genuine_translation_is_skipped():
    check = build_check_node(FakeLLM())
    out = await check({"candidates": [_content("a", "<p>Hi</p>", "<p>Hola</p>")], "dealer_name": "D"})
    assert [w["window_id"] for w in out["skipped"]] == ["a"]
    assert out["to_translate"] == []


@pytest.mark.asyncio
async def test_check_placeholder_es_needs_translation():
    check = build_check_node(FakeLLM())
    out = await check({"candidates": [_content("a", "<p>Hi</p>", "<p>PLACEHOLDER</p>")], "dealer_name": "D"})
    assert [w["window_id"] for w in out["to_translate"]] == ["a"]


# ── routing (pure fan-out) ───────────────────────────────────────────────────


def test_routing_one_send_per_widget():
    state = {"to_translate": [_content("a", "x", ""), _content("b", "y", "")], "dealer_name": "D"}
    sends = route_to_widget_branches(state)
    assert len(sends) == 2
    assert all(s.node == "translate_widget" for s in sends)
    assert sends[0].arg["widget"]["window_id"] == "a"


def test_routing_empty_when_nothing_to_translate():
    assert route_to_widget_branches({"to_translate": [], "dealer_name": "D"}) == []


# ── full graph stream ────────────────────────────────────────────────────────

_EN = """
<div class="main">
  <div class="text-content-container editable content" id="x:c1-editable"><p>Hello</p></div>
  <div class="text-content-container editable content" id="x:c2-editable"><p>World</p></div>
</div>
"""

# c1 already translated (skip); c2 empty on es (translate)
_ES = """
<div class="main">
  <div class="text-content-container editable content" id="x:c1-editable"><p>Hola</p></div>
</div>
"""


@pytest.mark.asyncio
async def test_graph_streams_expected_event_sequence():
    graph = build_translate_page_graph(llm=FakeLLM())
    events = []
    async for chunk in graph.astream(
        {"en_page_html": _EN, "es_page_html": _ES, "dealer_name": "D"},
        stream_mode="updates",
    ):
        for node, update in chunk.items():
            updates = update if isinstance(update, list) else [update]
            events.append((node, updates))

    node_order = [node for node, _ in events]
    assert node_order[0] == "extract_widgets"
    assert "check" in node_order
    assert node_order[-1] == "translate_widget"

    check_update = next(u for n, ups in events if n == "check" for u in ups)
    assert [w["window_id"] for w in check_update["to_translate"]] == ["x:c2-editable"]
    assert [w["window_id"] for w in check_update["skipped"]] == ["x:c1-editable"]

    widget_results = [u for n, ups in events if n == "translate_widget" for u in ups]
    translated = [r for wr in widget_results for r in wr["results"]]
    assert len(translated) == 1
    assert translated[0]["window_id"] == "x:c2-editable"
    assert translated[0]["status"] == "ready"
