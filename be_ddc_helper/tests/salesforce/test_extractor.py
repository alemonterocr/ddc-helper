"""Tests for the LLM-driven typed-field extractor.

Mocks LLMPort with a fake that returns scripted payloads. Validates the
post-processing (URL normalisation, smart-title-case, lowercase email,
design-choice JSON probe) and the classification-aware nulling of buysell-
only fields.
"""

import pytest

from src.application.salesforce.extractor import extract_fields_with_llm
from src.application.salesforce.questionnaire_parser import (
    DesignChoiceDescription,
    DesignChoiceJson,
    DesignChoiceMissing,
)


class FakeLLM:
    def __init__(self, payload: dict | Exception):
        self._payload = payload
        self.calls: list[tuple[dict, str]] = []

    async def extract_intake_fields(self, rows: dict[str, str], classification: str):
        self.calls.append((rows, classification))
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.mark.anyio
async def test_prebuild_happy_path_normalises_fields():
    llm = FakeLLM(payload={
        "dealership_name": "Bob's Garage",
        "new_dealership_name": None,
        "dealership_address": "123 main st, anywhere, CA 90210",
        "leads_email": "Leads@DEALER.COM",
        "primary_url": "bobsgarage.com",
        "new_primary_url": None,
        "design_choice": '{"color":"42"}',
    })
    fields, warnings = await extract_fields_with_llm(
        {"any": "row"}, "prebuild", llm,
    )

    assert warnings == []
    assert fields.dealership_name == "Bob's Garage"
    assert fields.new_dealership_name is None
    assert fields.dealership_address == "123 Main St, Anywhere, CA 90210"
    assert fields.leads_email == "leads@dealer.com"
    assert fields.primary_url == "https://bobsgarage.com"
    assert fields.new_primary_url is None
    assert isinstance(fields.design_choice, DesignChoiceJson)
    assert fields.design_choice.value == {"color": "42"}


@pytest.mark.anyio
async def test_buysell_extracts_both_urls():
    llm = FakeLLM(payload={
        "dealership_name": "H&K Chevrolet of New Haven Inc.",
        "new_dealership_name": "Lakeside Chevrolet of New Haven",
        "dealership_address": "624 State Route 930 E, New Haven, IN, 46774",
        "leads_email": None,
        "primary_url": "https://www.hkchevyofnewhaven.com/",
        "new_primary_url": "lakesidenewhaven.com",
        "design_choice": "use design that Lakeside Warsaw uses",
    })
    fields, warnings = await extract_fields_with_llm(
        {"any": "row"}, "buysell", llm,
    )

    assert warnings == []
    assert fields.dealership_name == "H&K Chevrolet of New Haven Inc."
    assert fields.new_dealership_name == "Lakeside Chevrolet of New Haven"
    assert fields.primary_url == "https://www.hkchevyofnewhaven.com/"
    assert fields.new_primary_url == "https://lakesidenewhaven.com"
    assert isinstance(fields.design_choice, DesignChoiceDescription)


@pytest.mark.anyio
async def test_buysell_fields_are_nulled_for_prebuild():
    """Even if the LLM hallucinates a new_dealership_name for a Prebuild,
    the extractor zeros it out — classification is the source of truth."""
    llm = FakeLLM(payload={
        "dealership_name": "Bob's Garage",
        "new_dealership_name": "Hallucinated Name",
        "dealership_address": None,
        "leads_email": None,
        "primary_url": "bobsgarage.com",
        "new_primary_url": "https://hallucinated.com",
        "design_choice": None,
    })
    fields, _warnings = await extract_fields_with_llm(
        {"any": "row"}, "prebuild", llm,
    )

    assert fields.new_dealership_name is None
    assert fields.new_primary_url is None
    assert fields.primary_url == "https://bobsgarage.com"


@pytest.mark.anyio
async def test_llm_failure_returns_empty_fields_with_warning():
    llm = FakeLLM(payload=RuntimeError("boom"))
    fields, warnings = await extract_fields_with_llm(
        {"any": "row"}, "prebuild", llm,
    )

    assert fields.dealership_name is None
    assert fields.primary_url is None
    assert isinstance(fields.design_choice, DesignChoiceMissing)
    assert len(warnings) == 1
    assert "RuntimeError" in warnings[0]


@pytest.mark.anyio
async def test_empty_rows_short_circuits():
    llm = FakeLLM(payload={"dealership_name": "shouldn't be called"})
    fields, warnings = await extract_fields_with_llm({}, "prebuild", llm)

    assert fields.dealership_name is None
    assert warnings == []
    assert llm.calls == []  # LLM was never called


@pytest.fixture
def anyio_backend():
    return "asyncio"
