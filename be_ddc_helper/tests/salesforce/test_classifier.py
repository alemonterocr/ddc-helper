"""Tests for the classifier - uses a fake LLM call to keep tests pure."""

import json
from typing import Awaitable, Callable

import pytest

from src.application.salesforce.classifier import classify_intake


def fake_llm(response_text: str) -> Callable[[str, str], Awaitable[str]]:
    async def _call(_system: str, _user: str) -> str:
        return response_text
    return _call


def fake_llm_raising() -> Callable[[str, str], Awaitable[str]]:
    async def _call(_system: str, _user: str) -> str:
        raise RuntimeError("provider down")
    return _call


@pytest.mark.asyncio
async def test_clean_prebuild_response():
    raw = json.dumps({
        "classification": "prebuild",
        "confidence": 0.92,
        "reasoning": "Single dealership, no previous/new naming.",
        "newDealershipName": None,
    })
    v = await classify_intake({}, fake_llm(raw))
    assert v.value == "prebuild"
    assert v.confidence == pytest.approx(0.92)
    assert v.new_dealership_name is None


@pytest.mark.asyncio
async def test_clean_buysell_response():
    raw = json.dumps({
        "classification": "buysell",
        "confidence": 0.88,
        "reasoning": "Mentions previous and new dealership.",
        "newDealershipName": "Bay Area Chevrolet",
    })
    v = await classify_intake({}, fake_llm(raw))
    assert v.value == "buysell"
    assert v.new_dealership_name == "Bay Area Chevrolet"


@pytest.mark.asyncio
async def test_markdown_fenced_response():
    raw = "```json\n" + json.dumps({"classification": "buysell", "confidence": 0.7, "newDealershipName": "X"}) + "\n```"
    v = await classify_intake({}, fake_llm(raw))
    assert v.value == "buysell"
    assert v.new_dealership_name == "X"


@pytest.mark.asyncio
async def test_response_with_preamble():
    raw = "Here is the classification: " + json.dumps({"classification": "prebuild", "confidence": 0.5})
    v = await classify_intake({}, fake_llm(raw))
    assert v.value == "prebuild"


@pytest.mark.asyncio
async def test_garbage_response_defaults_to_prebuild_zero_confidence():
    v = await classify_intake({}, fake_llm("not json at all"))
    assert v.value == "prebuild"
    assert v.confidence == 0.0


@pytest.mark.asyncio
async def test_llm_exception_defaults_to_prebuild_zero_confidence():
    v = await classify_intake({}, fake_llm_raising())
    assert v.value == "prebuild"
    assert v.confidence == 0.0


@pytest.mark.asyncio
async def test_invalid_classification_value_defaults():
    raw = json.dumps({"classification": "newDealer", "confidence": 0.9})
    v = await classify_intake({}, fake_llm(raw))
    assert v.value == "prebuild"
    assert v.confidence == 0.0


@pytest.mark.asyncio
async def test_confidence_clamped_to_range():
    raw = json.dumps({"classification": "prebuild", "confidence": 2.5})
    v = await classify_intake({}, fake_llm(raw))
    assert v.confidence == 1.0
    raw = json.dumps({"classification": "prebuild", "confidence": -0.5})
    v = await classify_intake({}, fake_llm(raw))
    assert v.confidence == 0.0


@pytest.mark.asyncio
async def test_prebuild_drops_new_name_even_if_llm_returns_one():
    raw = json.dumps({
        "classification": "prebuild",
        "confidence": 0.9,
        "newDealershipName": "Should be ignored",
    })
    v = await classify_intake({}, fake_llm(raw))
    assert v.new_dealership_name is None
