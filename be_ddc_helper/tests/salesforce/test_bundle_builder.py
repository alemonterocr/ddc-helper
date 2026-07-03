"""Tests for build_bundle - the coalescer that produces DealerBundleDTO."""

from src.application.salesforce.bundle_builder import build_bundle
from src.application.salesforce.classifier import ClassificationVerdict
from src.application.salesforce.questionnaire_parser import (
    DesignChoiceDescription,
    DesignChoiceJson,
    ParsedQuestionnaire,
)


def _verdict(value: str = "prebuild", confidence: float = 0.9, new_name: str | None = None) -> ClassificationVerdict:
    return ClassificationVerdict(value=value, confidence=confidence, reasoning="ok", new_dealership_name=new_name)


def test_full_prebuild_bundle():
    parsed = ParsedQuestionnaire(
        dealership_name="McElveen Buick GMC",
        dealership_address="117 Farmington Road, Summerville, SC 29486",
        leads_email="mcelveenbuickgmc@newsales.leads.cmdlr.com",
        primary_url="https://mcelveen.com",
        design_choice=DesignChoiceJson(value={"color": "86"}),
    )
    bundle = build_bundle(
        board_id="a9CPe00000275GLMAY",
        questionnaire_insight_id="a96Pe000001QyUbIAK",
        precursive_project_id="a9tPe000002FydpIAC",
        ppr="PPR-340445",
        dealer_id="mcelveenbgmc",
        parsed=parsed,
        verdict=_verdict(),
    )
    assert bundle.ppr == "PPR-340445"
    assert bundle.dealer_id == "mcelveenbgmc"
    assert bundle.dealership_name == "McElveen Buick GMC"
    # Prebuild → new_dealership_name should be the literal dash.
    assert bundle.new_dealership_name == "-"
    assert bundle.classification.value == "prebuild"
    assert bundle.classification.source == "llm"
    assert bundle.design_choice.kind == "json"


def test_missing_fields_become_dash():
    parsed = ParsedQuestionnaire()  # all None
    bundle = build_bundle(
        board_id="boardX",
        questionnaire_insight_id=None,
        precursive_project_id=None,
        ppr=None,
        dealer_id=None,
        parsed=parsed,
        verdict=_verdict(confidence=0.0),
    )
    assert bundle.ppr == "-"
    assert bundle.dealer_id == "-"
    assert bundle.dealership_name == "-"
    assert bundle.leads_email == "-"
    assert bundle.classification.source == "default"  # zero confidence → fallback


def test_buysell_carries_new_name():
    parsed = ParsedQuestionnaire(dealership_name="Smith Chevrolet of Tampa")
    bundle = build_bundle(
        board_id="b",
        questionnaire_insight_id="q",
        precursive_project_id="p",
        ppr="PPR-1",
        dealer_id="d",
        parsed=parsed,
        verdict=_verdict(value="buysell", new_name="Bay Area Chevrolet"),
    )
    assert bundle.classification.value == "buysell"
    assert bundle.dealership_name == "Smith Chevrolet of Tampa"  # original
    assert bundle.new_dealership_name == "Bay Area Chevrolet"


def test_description_design_choice_passes_through():
    parsed = ParsedQuestionnaire(
        design_choice=DesignChoiceDescription(raw="clean and modern"),
    )
    bundle = build_bundle(
        board_id="b", questionnaire_insight_id=None, precursive_project_id=None,
        ppr=None, dealer_id=None, parsed=parsed, verdict=_verdict(),
    )
    assert bundle.design_choice.kind == "description"
    assert bundle.design_choice.raw == "clean and modern"
    assert bundle.design_choice.needs_human_input is True


def test_source_has_iso_timestamp():
    parsed = ParsedQuestionnaire()
    bundle = build_bundle(
        board_id="b", questionnaire_insight_id="q", precursive_project_id="p",
        ppr="PPR-1", dealer_id="d", parsed=parsed, verdict=_verdict(),
    )
    # Just make sure it's an ISO 8601 string we can parse.
    from datetime import datetime
    datetime.fromisoformat(bundle.source.fetched_at)
