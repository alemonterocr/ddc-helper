"""LangGraph nodes for the Salesforce intake flow.

Graph shape:

       START
       /    \\
      v      v
    fetch_   fetch_
    insight  project_id
      |        |
      v        v
    fetch_   fetch_
    text     ppr_dealer
        \\   /
         v v
       parse_and_classify
            |
            v
       build_bundle
            |
            v
           END

Two independent chains (steps 1+2 vs. 3+4) run concurrently - LangGraph fans
out from START, the join happens implicitly at `parse_and_classify` because it
reads keys both chains have written.

Why a graph (vs. a flat orchestrator function): the SDD's recommendation is to
mirror the analyze + nav_parsing pattern. Future extensions (intake cache
lookup, multi-rooftop fan-out) drop in as new nodes without rewiring callers.
"""

from __future__ import annotations

from typing import Awaitable, Callable, TypedDict

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.ports.outbound import LLMPort

from .bundle_builder import build_bundle
from .bundle_dtos import DealerBundleDTO
from .classifier import ClassificationVerdict, classify_intake_with_llm
from .extractor import extract_fields_with_llm
from .questionnaire_parser import ParsedQuestionnaire, parse_questionnaire_blob
from .sf_uiapi_client import (
    SfApiError,
    extract_ppr_and_dealer,
    extract_precursive_project_id,
    extract_questionnaire_insight_id,
    extract_questionnaire_text,
    path_record_board,
    path_record_precursive_project,
    path_record_questionnaire,
    path_related_list_insights,
    ui_api_get,
)

Progress = Callable[[str], Awaitable[None]]


class IntakeState(TypedDict, total=False):
    # Inputs
    board_id: str
    ws_session_id: str          # routing key for the WS bridge

    # Step outputs
    questionnaire_insight_id: str | None
    questionnaire_text: str | None
    precursive_project_id: str | None
    ppr: str | None
    dealer_id: str | None

    # Derived
    parsed: ParsedQuestionnaire | None
    verdict: ClassificationVerdict | None
    bundle: DealerBundleDTO | None

    # Soft errors per step - never raised, accumulated and surfaced on the bundle.
    warnings: list[str]


# ── Helper: append a warning without losing prior ones ─────────────────────


def _warn(state: IntakeState, msg: str) -> list[str]:
    prior = list(state.get("warnings") or [])
    prior.append(msg)
    return prior


# ── Step 1: fetch the Insight Id ───────────────────────────────────────────


def build_fetch_insight_id_node(bridge: WsBridgeAdapter, progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        board_id = state["board_id"]
        ws = state["ws_session_id"]
        if progress:
            await progress("Looking up onboarding questionnaire…")
        try:
            body = await ui_api_get(bridge, ws, path_related_list_insights(board_id))
            insight_id = extract_questionnaire_insight_id(body)
            if not insight_id:
                return {
                    "questionnaire_insight_id": None,
                    "warnings": _warn(state, "No onboarding questionnaire found on this Board"),
                }
            return {"questionnaire_insight_id": insight_id}
        except SfApiError as e:
            return {
                "questionnaire_insight_id": None,
                "warnings": _warn(state, f"Could not list Board Insights: {e}"),
            }

    return _node


# ── Step 2: fetch the Questionnaire description text ───────────────────────


def build_fetch_questionnaire_text_node(bridge: WsBridgeAdapter, progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        insight_id = state.get("questionnaire_insight_id")
        if not insight_id:
            return {"questionnaire_text": None}
        ws = state["ws_session_id"]
        if progress:
            await progress("Reading questionnaire fields…")
        try:
            body = await ui_api_get(bridge, ws, path_record_questionnaire(insight_id))
            text = extract_questionnaire_text(body)
            if not text:
                return {
                    "questionnaire_text": None,
                    "warnings": _warn(state, "Questionnaire record has no Description__c"),
                }
            return {"questionnaire_text": text}
        except SfApiError as e:
            return {
                "questionnaire_text": None,
                "warnings": _warn(state, f"Could not read questionnaire: {e}"),
            }

    return _node


# ── Step 3: fetch the Board (for psx__Project__c) ──────────────────────────


def build_fetch_project_id_node(bridge: WsBridgeAdapter, progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        board_id = state["board_id"]
        ws = state["ws_session_id"]
        if progress:
            await progress("Resolving Precursive Project reference…")
        try:
            body = await ui_api_get(bridge, ws, path_record_board(board_id))
            project_id = extract_precursive_project_id(body)
            if not project_id:
                return {
                    "precursive_project_id": None,
                    "warnings": _warn(state, "Board record has no psx__Project__c"),
                }
            return {"precursive_project_id": project_id}
        except SfApiError as e:
            return {
                "precursive_project_id": None,
                "warnings": _warn(state, f"Could not read Board record: {e}"),
            }

    return _node


# ── Step 4: fetch PPR + dealer id from Precursive Project ──────────────────


def build_fetch_ppr_dealer_node(bridge: WsBridgeAdapter, progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        project_id = state.get("precursive_project_id")
        if not project_id:
            return {"ppr": None, "dealer_id": None}
        ws = state["ws_session_id"]
        if progress:
            await progress("Reading PPR and dealer id…")
        try:
            body = await ui_api_get(bridge, ws, path_record_precursive_project(project_id))
            ppr, dealer_id = extract_ppr_and_dealer(body)
            warnings = list(state.get("warnings") or [])
            if not ppr:
                warnings.append("Precursive Project missing Project_ID__c (PPR)")
            if not dealer_id:
                warnings.append("Precursive Project missing Product_Fulfillment_Account__r.Name (dealer id)")
            return {"ppr": ppr, "dealer_id": dealer_id, "warnings": warnings}
        except SfApiError as e:
            return {
                "ppr": None,
                "dealer_id": None,
                "warnings": _warn(state, f"Could not read Precursive Project: {e}"),
            }

    return _node


# ── Parse + classify (joins both chains) ───────────────────────────────────


def build_parse_and_classify_node(llm: LLMPort, progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        if progress:
            await progress("Parsing questionnaire + classifying project type…")
        parsed = parse_questionnaire_blob(state.get("questionnaire_text") or "")
        verdict = await classify_intake_with_llm(parsed.all_rows, llm)
        return {"parsed": parsed, "verdict": verdict}

    return _node


# ── Extract typed fields (LLM, runs after classification) ──────────────────


def build_extract_fields_node(llm: LLMPort, progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        parsed = state.get("parsed") or ParsedQuestionnaire()
        verdict = state.get("verdict")
        if progress:
            await progress("Extracting dealer fields…")
        classification = verdict.value if verdict else "prebuild"
        fields, extra_warnings = await extract_fields_with_llm(
            parsed.all_rows, classification, llm,
        )
        # Merge into the parsed object so the existing bundle_builder code
        # path is unchanged.
        parsed.dealership_name = fields.dealership_name
        parsed.new_dealership_name = fields.new_dealership_name
        parsed.dealership_address = fields.dealership_address
        parsed.leads_email = fields.leads_email
        parsed.primary_url = fields.primary_url
        parsed.new_primary_url = fields.new_primary_url
        parsed.design_choice = fields.design_choice

        warnings = list(state.get("warnings") or [])
        warnings.extend(extra_warnings)
        return {"parsed": parsed, "warnings": warnings}

    return _node


# ── Bundle (final node) ────────────────────────────────────────────────────


def build_assemble_bundle_node(progress: Progress | None = None):
    async def _node(state: IntakeState) -> dict:
        if progress:
            await progress("Assembling dealer bundle…")
        bundle = build_bundle(
            board_id=state["board_id"],
            questionnaire_insight_id=state.get("questionnaire_insight_id"),
            precursive_project_id=state.get("precursive_project_id"),
            ppr=state.get("ppr"),
            dealer_id=state.get("dealer_id"),
            parsed=state.get("parsed") or ParsedQuestionnaire(),
            verdict=state.get("verdict") or ClassificationVerdict(
                value="prebuild", confidence=0.0,
                reasoning="classifier did not run", new_dealership_name=None,
            ),
            warnings=list(state.get("warnings") or []),
        )
        return {"bundle": bundle}

    return _node
