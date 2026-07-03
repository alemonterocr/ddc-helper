"""POST /salesforce/intake - drives the new Salesforce intake LangGraph.

Receives a Salesforce Board URL, parses out the boardId, kicks off the intake
graph (4 UI API GETs via the WS bridge → parse → LLM classify → assemble),
returns a `DealerBundleDTO`.

The graph is built per-request - it captures the bridge + chosen LLM + an
optional progress callback. The state machine handles its own error
collection; partial-success bundles always return with a `warnings` list
rather than 500-ing.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.adapters.outbound.llm_factory import LLMFactory
from src.application.salesforce.bundle_dtos import (
    ClassificationDTO,
    DealerBundleDTO,
    DesignChoiceMissingDTO,
    IntakeRequest,
    IntakeResponse,
    IntakeSourceDTO,
)
from src.application.salesforce.intake_graph import build_intake_graph
from src.domain.errors import ProviderNotConfiguredError
from src.domain.models import LLMProvider
from src.ports.outbound import LLMPort

from .dependencies import get_bridge, get_llm_factory

router = APIRouter()

_BOARD_URL_RE = re.compile(
    r"^https://casfx\.lightning\.force\.com/lightning/r/taskfeed1__Board__c/(?P<id>[A-Za-z0-9]+)/view$"
)


@router.post("/salesforce/intake", response_model=IntakeResponse)
async def salesforce_intake(
    body: IntakeRequest,
    factory: LLMFactory = Depends(get_llm_factory),
    bridge: WsBridgeAdapter = Depends(get_bridge),
) -> IntakeResponse:
    board_id = _parse_board_id(body.board_url)
    if not board_id:
        return IntakeResponse(error="Board URL is not a valid Salesforce Board link.")

    # LLM is optional - without it the classifier defaults to prebuild + confidence:0
    # and the FE banner asks the user to confirm. Intake still succeeds.
    llm: LLMPort | _NoOpLLM = _resolve_llm(factory, body.provider)

    async def progress(msg: str) -> None:
        # Route progress via the WS session the FE opened for this intake (key = board_id).
        await bridge.send_progress(board_id, msg)

    graph = build_intake_graph(bridge=bridge, llm=llm, progress=progress)

    state = await graph.ainvoke({
        "board_id": board_id,
        "ws_session_id": board_id,  # FE opens /ws/{board_id} for this flow
        "warnings": [],
    })

    bundle: DealerBundleDTO | None = state.get("bundle")
    if bundle is None:
        # Should never happen - assemble_bundle always returns a DTO. Defensive.
        bundle = DealerBundleDTO(
            classification=ClassificationDTO(value="prebuild", confidence=0.0, source="default"),
            source=IntakeSourceDTO(board_id=board_id, fetched_at=""),
            design_choice=DesignChoiceMissingDTO(),
            warnings=list(state.get("warnings") or []) + ["Intake graph returned no bundle"],
        )

    return IntakeResponse(bundle=bundle)


def _parse_board_id(url: str) -> str | None:
    m = _BOARD_URL_RE.match(url.strip())
    return m.group("id") if m else None


def _resolve_llm(factory: LLMFactory, requested: str | None):
    """Pick an LLM. Honour `requested` if given; else prefer DeepSeek (cheapest),
    then Anthropic, then Gemini. Returns _NoOpLLM if none registered - the
    classifier will fall back to default verdict.
    """
    # Honour an explicit request when valid + configured.
    if requested:
        try:
            requested_enum = LLMProvider(requested)
            return factory.get(requested_enum)
        except (ValueError, ProviderNotConfiguredError):
            pass
    for provider in (LLMProvider.DEEPSEEK, LLMProvider.ANTHROPIC, LLMProvider.GEMINI):
        if factory.is_configured(provider):
            return factory.get(provider)
    return _NoOpLLM()


class _NoOpLLM:
    """LLM stand-in used when no provider is configured. The classifier will
    catch the exception and fall back to default verdict + warning banner."""
    async def classify_intake(self, _rows: dict[str, str]) -> str:
        raise RuntimeError("No LLM provider configured for classify_intake")
