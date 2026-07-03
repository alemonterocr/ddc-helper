"""Pydantic DTOs for the /parse-nav endpoint.

Lives in the inbound HTTP layer (Pydantic + the request/response contract are
HTTP-shaped).
"""

from typing import Literal

from pydantic import BaseModel

from src.domain.models import LLMProvider


class ParseNavRequest(BaseModel):
    dealer_id: str
    html: str
    base_url: str
    provider: LLMProvider


class ParseNavPage(BaseModel):
    title: str
    url: str
    category: Literal["general", "model_specific"]


class ParseNavResponse(BaseModel):
    pages: list[ParseNavPage]
    warnings: list[str] = []
    error: str | None = None
