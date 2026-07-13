"""Pydantic DTOs for the EN→es_US label translation endpoints."""

from enum import Enum

from pydantic import BaseModel

from src.domain.models import LLMProvider


# ── /translations/sanitize ─────────────────────────────────────────────────────


class SanitizeAliasesRequest(BaseModel):
    raw: str  # the user's pasted blob — newlines, commas, anything


class SanitizeAliasesResponse(BaseModel):
    aliases: list[str]
    dropped: list[str] = []  # entries that didn't look like a valid alias


# ── /translations/translate ────────────────────────────────────────────────────


class TranslateLabelRequest(BaseModel):
    alias: str
    en_html: str
    dealer_name: str
    provider: LLMProvider = LLMProvider.ANTHROPIC


class TranslateLabelResponse(BaseModel):
    alias: str
    es_html: str
    status: str  # "ready" | "error"
    warnings: list[str] = []
    raw: str | None = None  # only populated when status == "error"
    reasoning: str = ""     # translator's brief reasoning; empty on legacy paths


# ── /translations/nav-check ─────────────────────────────────────────────────────


class NavCheckItem(BaseModel):
    alias: str
    label_es: str


class NavCheckRequest(BaseModel):
    nav_json: object  # the raw LoadNavigation response body
    dealer_name: str


class NavCheckResponse(BaseModel):
    to_translate: list[NavCheckItem]
    skipped: list[NavCheckItem]
    total: int


# ── /translations/translate-page ────────────────────────────────────────────────


class WidgetType(str, Enum):
    CONTENT = "content"
    RAW = "raw"


class PageWidget(BaseModel):
    window_id: str          # raw div id, WITH the -editable suffix
    widget_type: WidgetType
    en_html: str            # inner HTML of the en_US widget
    es_html: str            # inner HTML of the es_US widget ("" if absent)


class TranslatePageRequest(BaseModel):
    en_page_html: str       # full en_US render (~0.5–2 MB)
    es_page_html: str       # full es_US render
    dealer_name: str        # so brand/model names stay untranslated
    provider: LLMProvider = LLMProvider.ANTHROPIC
