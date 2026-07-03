"""POST /parse-nav — parses a navigation menu HTML snippet into a page list.

Used during GM Prebuild project creation: the user pastes the source site's
nav HTML, this endpoint hands it to the LLM, returns the deduplicated list of
{title, url, category} entries. The frontend then creates pages for the
`general`-category entries.
"""

from fastapi import APIRouter, Depends

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.adapters.outbound.llm_factory import LLMFactory
from src.application.nav_parsing.nav_parser_graph import build_nav_parser_graph
from src.domain.errors import ProviderNotConfiguredError

from .dependencies import get_bridge, get_llm_factory
from .parse_nav_dtos import ParseNavPage, ParseNavRequest, ParseNavResponse

router = APIRouter()


@router.post("/parse-nav", response_model=ParseNavResponse)
async def parse_nav(
    body: ParseNavRequest,
    factory: LLMFactory = Depends(get_llm_factory),
    bridge: WsBridgeAdapter = Depends(get_bridge),
) -> ParseNavResponse:
    try:
        llm = factory.get(body.provider)
    except ProviderNotConfiguredError as e:
        return ParseNavResponse(pages=[], warnings=[], error=str(e))

    async def progress(msg: str) -> None:
        await bridge.send_progress(body.dealer_id, msg)

    state: dict = {
        "html": body.html,
        "base_url": body.base_url,
        "dealer_id": body.dealer_id,
        "pages": [],
        "warnings": [],
    }

    graph = build_nav_parser_graph(llm=llm, progress=progress)
    out = await graph.ainvoke(state)

    pages = [
        ParseNavPage(
            title=str(p.get("title", "")),
            url=str(p.get("url", "")),
            category=p.get("category", "general"),
        )
        for p in out.get("pages", [])
    ]

    return ParseNavResponse(
        pages=pages,
        warnings=out.get("warnings", []),
    )
