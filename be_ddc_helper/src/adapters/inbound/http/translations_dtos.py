"""Pydantic DTOs for the EN→es_US label translation endpoints."""

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
