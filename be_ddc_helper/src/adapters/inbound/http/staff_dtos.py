"""Pydantic DTOs for the staff-migration endpoints."""

from typing import Literal

from pydantic import BaseModel

from src.domain.models import LLMProvider


ProjectType = Literal["cm", "gm-prebuild"]


class StaffMemberDTO(BaseModel):
    department: str
    name: str
    title: str | None = None
    phone: str | None = None
    email: str | None = None
    bio: str | None = None
    has_photo: bool = False
    original_photo_url: str | None = None
    photo: str | None = None


# ── /parse-staff ────────────────────────────────────────────────────────────


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


class ParseStaffRequest(BaseModel):
    dealer_id: str
    project_type: ProjectType
    dom_skeleton: dict          # carries raw_html + url for base_url derivation
    provider: LLMProvider


class ParseStaffResponse(BaseModel):
    staff: list[StaffMemberDTO]
    warnings: list[str] = []
    token_info: TokenInfoDTO = TokenInfoDTO()
    error: str | None = None


# ── /execute-staff (Phase 3 — Pydantic shape only for now) ──────────────────


class ExecuteStaffRequest(BaseModel):
    dealer_id: str
    project_type: ProjectType
    page_alias: str | None = None
    page_title: str | None = None
    staff: list[StaffMemberDTO]


class ExecuteStaffResponse(BaseModel):
    ok: bool
    warnings: list[str] = []
    error: str | None = None
