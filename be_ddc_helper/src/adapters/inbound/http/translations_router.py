"""POST /translations/sanitize, POST /translations/translate, and
POST /translations/nav-check.

sanitize + translate are stateless and FE-driven. The FE pastes a raw alias
blob, hits /sanitize once to get a clean array, then loops alias-by-alias
calling GET-label on DDC (extension side) + /translate here, reviews the
result, saves to DDC, advances to the next alias.

nav-check receives a raw LoadNavigation response JSON, walks the tree, and
returns which labels need translation vs. which already have Spanish text.
"""

import re

from fastapi import APIRouter, Depends

from src.adapters.outbound.llm_factory import LLMFactory
from src.application.translate_labels.translate_labels_graph import (
    build_translate_labels_graph,
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
