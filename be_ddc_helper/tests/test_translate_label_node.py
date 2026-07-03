"""Node-level tests for the translate_label flow.

Uses a fake LLMPort that scripts the translation outputs and judge verdicts
per call. Verifies the 1-retry budget, structural+semantic gating, and the
final status logic.
"""

import pytest

from src.application.translate_labels.translate_label_node import build_translate_label_node


class FakeLLM:
    """Scripts `translate_label_with_tools` and `judge_translation` outputs.

    Both lists are consumed in order. If the test exhausts the list, that's a
    bug — the node called the LLM more than the test expected.

    `translations` entries may be plain strings (legacy shorthand — wrapped
    into the new dict shape automatically) or dicts like
    {"translation": ..., "reasoning": ...}.
    """
    def __init__(self, translations: list, verdicts: list[dict]):
        self._translations = list(translations)
        self._verdicts = list(verdicts)
        self.translate_calls: list[dict] = []
        self.judge_calls: list[dict] = []

    async def translate_label_with_tools(self, en_html, dealer_name, glossary_lookup, extra_hint=""):
        self.translate_calls.append({"en": en_html, "hint": extra_hint})
        item = self._translations.pop(0)
        if isinstance(item, dict):
            return item
        return {"translation": item, "reasoning": ""}

    async def judge_translation(self, en_html, es_html, dealer_name):
        self.judge_calls.append({"en": en_html, "es": es_html})
        return self._verdicts.pop(0)


def _state(en="<p>Hello world</p>", dealer="Test Dealer"):
    return {"alias": "TEST", "en_html": en, "dealer_name": dealer}


@pytest.mark.anyio
async def test_happy_path_passes_first_try():
    llm = FakeLLM(
        translations=["<p>Hola mundo</p>"],
        verdicts=[{"ok": True, "reason": ""}],
    )
    node = build_translate_label_node(llm)
    out = await node(_state())

    assert out["status"] == "ready"
    assert out["es_html"] == "<p>Hola mundo</p>"
    assert out["warnings"] == []
    assert out["raw"] is None
    assert len(llm.translate_calls) == 1
    assert len(llm.judge_calls) == 1
    assert llm.translate_calls[0]["hint"] == ""


@pytest.mark.anyio
async def test_guardrail_fail_then_retry_passes():
    llm = FakeLLM(
        translations=["<p>bad translation</p>", "<p>Hola mundo</p>"],
        verdicts=[
            {"ok": False, "reason": "Awkward phrasing"},
            {"ok": True, "reason": ""},
        ],
    )
    node = build_translate_label_node(llm)
    out = await node(_state())

    assert out["status"] == "ready"
    assert out["es_html"] == "<p>Hola mundo</p>"
    assert "Awkward phrasing" in llm.translate_calls[1]["hint"]
    assert len(llm.translate_calls) == 2


@pytest.mark.anyio
async def test_structural_fail_skips_judge_then_retry_passes():
    # First attempt drops the <p> tag → structural fail. Retry restores it.
    llm = FakeLLM(
        translations=["Hola mundo", "<p>Hola mundo</p>"],
        verdicts=[{"ok": True, "reason": ""}],   # only consumed on retry
    )
    node = build_translate_label_node(llm)
    out = await node(_state())

    assert out["status"] == "ready"
    # Judge was NOT called on attempt 1 (structural fail short-circuits)
    assert len(llm.judge_calls) == 1
    # Retry hint mentions structural
    assert "Structural" in llm.translate_calls[1]["hint"]


@pytest.mark.anyio
async def test_both_fail_twice_returns_error():
    llm = FakeLLM(
        translations=["<p>bad one</p>", "<p>bad two</p>"],
        verdicts=[
            {"ok": False, "reason": "wrong meaning"},
            {"ok": False, "reason": "still wrong"},
        ],
    )
    node = build_translate_label_node(llm)
    out = await node(_state())

    assert out["status"] == "error"
    assert out["es_html"] == "<p>bad two</p>"
    assert out["raw"] == "<p>bad two</p>"
    assert any("Reviewer" in w for w in out["warnings"])


@pytest.mark.anyio
async def test_reasoning_surfaces_to_state():
    llm = FakeLLM(
        translations=[{"translation": "<p>Hola mundo</p>", "reasoning": "I chose 'mundo' for 'world'."}],
        verdicts=[{"ok": True, "reason": ""}],
    )
    node = build_translate_label_node(llm)
    out = await node(_state())

    assert out["status"] == "ready"
    assert out["reasoning"] == "I chose 'mundo' for 'world'."


@pytest.mark.anyio
async def test_empty_input_short_circuits():
    llm = FakeLLM(translations=[], verdicts=[])
    node = build_translate_label_node(llm)
    out = await node({"en_html": "   ", "dealer_name": "X"})

    assert out["status"] == "error"
    assert out["warnings"] == ["Empty input"]
    assert llm.translate_calls == []


# ── anyio plugin wiring ──────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"
