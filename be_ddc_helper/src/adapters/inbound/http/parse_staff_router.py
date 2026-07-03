"""POST /parse-staff — extracts a list of staff members from a page's HTML.

Used during the staff-migration flow: the FE captures the page via
extractorPort (giving us `skeleton.raw_html` and `skeleton.url`), this
endpoint hands them to the LLM, returns the parsed list. The FE then lets
the user review/edit before calling /execute-staff.
"""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.adapters.outbound.llm_factory import LLMFactory
from src.application.staff_migration.staff_graph import build_staff_extraction_graph
from src.domain.errors import ProviderNotConfiguredError
from src.domain.models import TokenInfo

from .dependencies import get_bridge, get_llm_factory
from .staff_dtos import (
    ParseStaffRequest,
    ParseStaffResponse,
    StaffMemberDTO,
    TokenInfoDTO,
    TokenUsageDTO,
)

router = APIRouter()


@router.post("/parse-staff", response_model=ParseStaffResponse)
async def parse_staff(
    body: ParseStaffRequest,
    factory: LLMFactory = Depends(get_llm_factory),
    bridge: WsBridgeAdapter = Depends(get_bridge),
) -> ParseStaffResponse:
    try:
        llm = factory.get(body.provider)
    except ProviderNotConfiguredError as e:
        return ParseStaffResponse(staff=[], warnings=[], error=str(e))
    llm.reset_usage()

    html, base_url = _extract_page_context(body.dom_skeleton)
    if not html.strip():
        return ParseStaffResponse(
            staff=[],
            warnings=["No HTML captured from the page — skeleton.raw_html is empty"],
            error="empty_html",
        )

    async def progress(msg: str) -> None:
        await bridge.send_progress(body.dealer_id, msg)

    graph = build_staff_extraction_graph(llm=llm, progress=progress)
    out = await graph.ainvoke(_initial_state(html, base_url, body.dealer_id))

    return ParseStaffResponse(
        staff=_to_staff_dtos(out.get("staff", [])),
        warnings=out.get("warnings", []),
        token_info=_build_token_info_dto(llm.usage_log),
    )


# ── Handler helpers ──────────────────────────────────────────────────────────


def _extract_page_context(dom_skeleton: dict) -> tuple[str, str]:
    """Pull the raw HTML + a base URL out of the skeleton the FE sent."""
    html = str(dom_skeleton.get("raw_html") or "")
    page_url = str(dom_skeleton.get("url") or "")
    return html, _derive_base_url(page_url)


def _initial_state(html: str, base_url: str, dealer_id: str) -> dict:
    return {
        "html": html,
        "base_url": base_url,
        "dealer_id": dealer_id,
        "staff": [],
        "warnings": [],
    }


def _to_staff_dtos(raw_staff: list[dict]) -> list[StaffMemberDTO]:
    return [
        StaffMemberDTO(
            department=str(s.get("department", "")),
            name=str(s.get("name", "")),
            title=s.get("title"),
            phone=s.get("phone"),
            email=s.get("email"),
            bio=s.get("bio"),
            has_photo=bool(s.get("has_photo", False)),
            original_photo_url=s.get("original_photo_url"),
        )
        for s in raw_staff
    ]


def _build_token_info_dto(usage_log: list) -> TokenInfoDTO:
    info = TokenInfo.from_log(usage_log)
    return TokenInfoDTO(
        total_input_tokens=info.total_input_tokens,
        total_output_tokens=info.total_output_tokens,
        total_cost_usd=info.total_cost_usd,
        by_stage=[
            TokenUsageDTO(
                provider=u.provider,
                model=u.model,
                stage=u.stage,
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cost_usd=u.cost_usd,
            )
            for u in info.by_stage
        ],
    )


def _derive_base_url(page_url: str) -> str:
    """Reduce `https://www.dealer.com/about/staff/?ref=foo` → `https://www.dealer.com`."""
    try:
        parsed = urlparse(page_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return page_url  # fallback: pass through whatever the FE sent
