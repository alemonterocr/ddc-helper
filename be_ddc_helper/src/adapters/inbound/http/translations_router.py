"""POST /translations/sanitize and POST /translations/translate.

Both endpoints are stateless and FE-driven. The FE pastes a raw alias blob,
hits /sanitize once to get a clean array, then loops alias-by-alias calling
GET-label on DDC (extension side) + /translate here, reviews the result,
saves to DDC, advances to the next alias.

There is no batching at this layer on purpose — the user reviews each
translation before saving, and the cost of one /translate call is small.
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
