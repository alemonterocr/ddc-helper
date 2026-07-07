"""POST /translations/sanitize, POST /translations/translate, and
POST /translations/nav-check.

sanitize + translate are stateless and FE-driven. The FE pastes a raw alias
blob, hits /sanitize once to get a clean array, then loops alias-by-alias
calling GET-label on DDC (extension side) + /translate here, reviews the
result, saves to DDC, advances to the next alias.

nav-check receives a raw LoadNavigation response JSON, walks the tree, and
returns which labels need translation vs. which already have Spanish text.
"""

import json
import re
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.adapters.outbound.llm_factory import LLMFactory
from src.application.translate_labels.translate_labels_graph import (
    build_translate_labels_graph,
)
from src.application.translate_pages.translate_page_graph import (
    build_translate_page_graph,
)
from src.domain.errors import ProviderNotConfiguredError

from .dependencies import get_llm_factory
from .translations_dtos import (
    NavCheckItem,
    NavCheckRequest,
    NavCheckResponse,
    SanitizeAliasesRequest,
    SanitizeAliasesResponse,
    TranslateLabelRequest,
    TranslateLabelResponse,
    TranslatePageRequest,
)

router = APIRouter(prefix="/translations", tags=["translations"])


# DDC aliases are uppercase identifiers: letters, digits, underscores. We
# accept trailing underscores (e.g. "ORANGE_BUYS_CARS_") because they exist
# in real dealer setups.
_ALIAS_RE = re.compile(r"^[A-Z0-9_]+$")
_SPLIT_RE = re.compile(r"[\s,;]+")


@router.post("/sanitize", response_model=SanitizeAliasesResponse)
async def sanitize_aliases(body: SanitizeAliasesRequest) -> SanitizeAliasesResponse:
    seen: set[str] = set()
    aliases: list[str] = []
    dropped: list[str] = []

    for raw_token in _SPLIT_RE.split(body.raw):
        token = raw_token.strip().strip(",").strip(";")
        if not token:
            continue
        # Be forgiving: accept lowercase paste, uppercase it.
        candidate = token.upper()
        if not _ALIAS_RE.match(candidate):
            dropped.append(token)
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        aliases.append(candidate)

    return SanitizeAliasesResponse(aliases=aliases, dropped=dropped)


@router.post("/translate", response_model=TranslateLabelResponse)
async def translate_label(
    body: TranslateLabelRequest,
    factory: LLMFactory = Depends(get_llm_factory),
) -> TranslateLabelResponse:
    try:
        llm = factory.get(body.provider)
    except ProviderNotConfiguredError as e:
        return TranslateLabelResponse(
            alias=body.alias,
            es_html="",
            status="error",
            warnings=[str(e)],
        )

    llm.reset_usage()

    state: dict = {
        "alias": body.alias,
        "en_html": body.en_html,
        "dealer_name": body.dealer_name,
    }

    graph = build_translate_labels_graph(llm=llm)
    out = await graph.ainvoke(state)

    return TranslateLabelResponse(
        alias=body.alias,
        es_html=str(out.get("es_html", "")),
        status=str(out.get("status", "error")),
        warnings=list(out.get("warnings", [])),
        raw=out.get("raw"),
        reasoning=str(out.get("reasoning", "")),
    )


# ── /translations/nav-check ─────────────────────────────────────────────────────


def _walk_nav_items(items: list[dict], depth: int = 0) -> list[tuple[str, str]]:
    """Recursively collect (alias, label) from a navigationItems.list array."""
    result: list[tuple[str, str]] = []
    for item in items:
        alias = (item.get("labelAlias") or "").strip()
        label = (item.get("label") or "").strip()
        if alias:
            result.append((alias, label))
        children = item.get("navigationItems", {}).get("list", [])
        if children:
            result.extend(_walk_nav_items(children, depth + 1))
    return result


@router.post("/nav-check", response_model=NavCheckResponse)
async def nav_check(body: NavCheckRequest) -> NavCheckResponse:
    raw_items: list[dict] = []
    try:
        dto = body.nav_json.get("result", {})  # type: ignore[union-attr]
        raw_items = dto.get("dto", {}).get("navigationItems", {}).get("list", [])
    except (AttributeError, KeyError):
        return NavCheckResponse(to_translate=[], skipped=[], total=0)

    all_items = _walk_nav_items(raw_items)
    seen: set[str] = set()

    to_translate: list[NavCheckItem] = []
    skipped: list[NavCheckItem] = []

    for alias, label in all_items:
        if alias in seen:
            continue
        seen.add(alias)
        item = NavCheckItem(alias=alias, label_es=label)
        if not label or _ALIAS_RE.match(label):
            to_translate.append(item)
        else:
            skipped.append(item)

    return NavCheckResponse(
        to_translate=to_translate,
        skipped=skipped,
        total=len(to_translate) + len(skipped),
    )


# ── /translations/translate-page ────────────────────────────────────────────────


def _pick(widget: dict) -> dict:
    """Project a candidate widget down to the PageWidget wire shape."""
    return {
        "window_id": widget.get("window_id", ""),
        "widget_type": widget.get("widget_type", ""),
        "en_html": widget.get("en_html", ""),
        "es_html": widget.get("es_html", ""),
    }


def _updates_to_events(node: str, update: dict) -> list[dict]:
    """Map one LangGraph node update to zero or more stream events."""
    if node == "extract_widgets":
        return [{"type": "extracted", "total": len(update.get("candidates", []))}]
    if node == "check":
        return [{
            "type": "checked",
            "to_translate": [_pick(w) for w in update.get("to_translate", [])],
            "skipped": [_pick(w) for w in update.get("skipped", [])],
        }]
    if node == "translate_widget":
        return [{"type": "widget", "widget": r} for r in update.get("results", [])]
    return []


async def _stream_page_translation(
    graph, initial_state: dict
) -> AsyncIterator[str]:
    """Yield NDJSON lines as the graph progresses; terminal done/error line."""
    try:
        async for chunk in graph.astream(initial_state, stream_mode="updates"):
            for node, update in chunk.items():
                # Parallel branches may batch as a list of partial updates.
                updates = update if isinstance(update, list) else [update]
                for one in updates:
                    for event in _updates_to_events(node, one):
                        yield json.dumps(event) + "\n"
        yield json.dumps({"type": "done"}) + "\n"
    except Exception as e:  # surface as a terminal event — status is already 200
        yield json.dumps({"type": "error", "message": str(e)}) + "\n"


@router.post("/translate-page")
async def translate_page(
    body: TranslatePageRequest,
    factory: LLMFactory = Depends(get_llm_factory),
) -> StreamingResponse:
    try:
        llm = factory.get(body.provider)
    except ProviderNotConfiguredError as e:
        async def _error_only() -> AsyncIterator[str]:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

        return StreamingResponse(_error_only(), media_type="application/x-ndjson")

    llm.reset_usage()
    graph = build_translate_page_graph(llm=llm)
    initial_state = {
        "en_page_html": body.en_page_html,
        "es_page_html": body.es_page_html,
        "dealer_name": body.dealer_name,
        "provider": str(body.provider),
    }
    return StreamingResponse(
        _stream_page_translation(graph, initial_state),
        media_type="application/x-ndjson",
    )
