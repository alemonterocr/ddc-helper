import logging
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.adapters.outbound.llm_factory import LLMFactory
from src.application.migration.migration_graph import build_migration_graph
from src.domain.catalog import load_catalog
from src.domain.errors import ProviderNotConfiguredError
from src.domain.models import DOMNode, DOMSkeleton, LLMProvider, TokenInfo

from .dependencies import get_bridge, get_llm_factory

logger = logging.getLogger(__name__)

router = APIRouter()

# LLM widget-type review: classify content widgets that the algo flagged
# with structural signals (form, hours, contact_info, drop) — bounded 5-class.
_TYPIFY_ENABLED = True
# LLM widget-level structural review: promote residual <img> tags inside
# content widgets to their own image widgets when the deterministic chunker
# missed them. Safe to leave on — defaults to no-op on LLM failure.
_IMAGE_SPLIT_ENABLED = True
# HTML beautifier: LLM cleans raw HTML snippets produced by the algo.
_ENRICH_ENABLED = True


class AnalyzeRequest(BaseModel):
    dom_skeleton: dict
    dealer_id: str
    provider: LLMProvider


class TokenUsageDTO(BaseModel):
    provider: str
    model: str
    stage: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class TokenInfoDTO(BaseModel):
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_stage: list[TokenUsageDTO] = []


class AnalyzeResponse(BaseModel):
    section_plan: list[dict]
    warnings: list[str]
    page_alias: str
    page_title: str
    token_info: TokenInfoDTO = TokenInfoDTO()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_page(
    body: AnalyzeRequest,
    factory: LLMFactory = Depends(get_llm_factory),
    bridge: WsBridgeAdapter = Depends(get_bridge),
) -> AnalyzeResponse:
    # LLM is optional — deterministic algo handles most pages alone. The graph
    # gracefully no-ops LLM steps when llm is None.
    llm = None
    try:
        llm = factory.get(body.provider)
    except ProviderNotConfiguredError:
        pass

    # Fresh slate for per-request token accounting. The graph may make 0–N LLM
    # calls; whatever it makes ends up in llm.usage_log for aggregation below.
    if llm is not None:
        llm.reset_usage()

    async def progress(msg: str) -> None:
        await bridge.send_progress(body.dealer_id, msg)

    skeleton = DOMSkeleton.model_validate(body.dom_skeleton)
    page_alias, page_title = _derive_page_meta(body.dom_skeleton)

    # Override page title with the first H1 — cleaner than document.title
    # which often has site-name suffixes like "| Mazda of South Charlotte".
    h1_text = _find_first_h1(skeleton.structure)
    if h1_text:
        page_title = h1_text

    state: dict = {
        "dealer_id": body.dealer_id,
        "site_id": "",
        "page_alias": page_alias,
        "page_title": page_title,
        "dom_skeleton": body.dom_skeleton,
        "pruned_tree": {},
        "det_plan": [],
        "section_plan": [],
        "warnings": [],
    }

    graph = build_migration_graph(
        llm=llm,
        catalog=load_catalog(),
        progress=progress,
        typify_enabled=_TYPIFY_ENABLED,
        image_split_enabled=_IMAGE_SPLIT_ENABLED,
        enrich_enabled=_ENRICH_ENABLED,
    )
    out = await graph.ainvoke(state)

    # Aggregate token usage from whatever LLM calls the graph fired.
    token_info_dto = TokenInfoDTO()
    if llm is not None:
        info = TokenInfo.from_log(llm.usage_log)
        token_info_dto = TokenInfoDTO(
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

    return AnalyzeResponse(
        section_plan=out.get("section_plan", []),
        warnings=out.get("warnings", []),
        page_alias=page_alias,
        page_title=page_title,
        token_info=token_info_dto,
    )


# ── Router-only helpers ──────────────────────────────────────────────────────


def _derive_page_meta(skeleton: dict) -> tuple[str, str]:
    """Derive DDC page alias (must end in .htm) and title from the DOM skeleton."""
    raw_url: str = skeleton.get("url", "")
    raw_title: str = skeleton.get("title", "Migrated Page").strip() or "Migrated Page"

    try:
        path = urlparse(raw_url).path.rstrip("/")
        segments = [s for s in path.split("/") if s]
        url_slug_raw = "-".join(segments) if segments else ""
    except Exception:
        url_slug_raw = ""

    url_slug = re.sub(r"[^a-z0-9-]", "-", url_slug_raw.lower())
    url_slug = re.sub(r"-{2,}", "-", url_slug).strip("-")

    title_slug = re.sub(r"[^a-z0-9-]", "-", raw_title.lower())
    title_slug = re.sub(r"-{2,}", "-", title_slug).strip("-") or "migrated-page"
    title_slug = title_slug[:60].strip("-")

    def _looks_like_system_id(slug: str) -> bool:
        if not slug:
            return True
        if re.search(r"\d{2,}", slug):
            return True
        if len(slug) <= 3:
            return True
        return False

    url_is_readable = not _looks_like_system_id(url_slug)
    title_is_long = len(raw_title) > 60

    slug = url_slug if url_is_readable else title_slug
    if url_is_readable and title_is_long:
        slug = url_slug

    slug = slug or "home"
    if not slug.endswith(".htm"):
        slug = f"{slug}.htm"

    return slug, raw_title


def _find_first_h1(node) -> str | None:
    """Depth-first search for the first <h1> text in the DOM tree."""
    if not isinstance(node, DOMNode):
        return None
    if node.tag == "h1" and node.text and node.text.strip():
        return node.text.strip()
    for child in node.children:
        result = _find_first_h1(child)
        if result:
            return result
    return None
