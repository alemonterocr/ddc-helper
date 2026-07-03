"""DTOs for the Salesforce intake response.

Mirrored on the FE as `DealerBundle` (see SDD §7). Every string field is
guaranteed to be a string in the response - the orchestrator coalesces missing
values to `"-"` at build time so the FE never has to deal with null. Structured
fields (`design_choice`, `classification`) keep their object shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Inputs ─────────────────────────────────────────────────────────────────


class IntakeRequest(BaseModel):
    """POST /salesforce/intake body."""
    board_url: str = Field(..., description="Full SF Board URL the specialist receives.")
    provider: str | None = Field(
        None,
        description="LLM provider for classification. If omitted, falls back to whichever is configured.",
    )


# ── Design choice variants ─────────────────────────────────────────────────


class DesignChoiceJsonDTO(BaseModel):
    kind: Literal["json"] = "json"
    value: dict


class DesignChoiceDescriptionDTO(BaseModel):
    kind: Literal["description"] = "description"
    raw: str
    needs_human_input: Literal[True] = True


class DesignChoiceMissingDTO(BaseModel):
    kind: Literal["missing"] = "missing"


DesignChoiceDTO = DesignChoiceJsonDTO | DesignChoiceDescriptionDTO | DesignChoiceMissingDTO


# ── Classification result ──────────────────────────────────────────────────


class ClassificationDTO(BaseModel):
    value: Literal["prebuild", "buysell"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = ""
    source: Literal["llm", "user-override", "default"] = "llm"


# ── Provenance (links the FE renders as "Verify in Salesforce ↗") ─────────


class IntakeSourceDTO(BaseModel):
    board_id: str
    questionnaire_insight_id: str = "-"
    precursive_project_id: str = "-"
    fetched_at: str  # ISO timestamp


# ── Top-level response ─────────────────────────────────────────────────────


class DealerBundleDTO(BaseModel):
    # From step 4 (PPR card on FE)
    ppr: str = "-"
    dealer_id: str = "-"

    # From questionnaire parse (Questionnaire card on FE)
    dealership_name: str = "-"
    new_dealership_name: str = "-"  # only meaningful when classification.value == "buysell"
    dealership_address: str = "-"
    leads_email: str = "-"
    primary_url: str = "-"
    new_primary_url: str = "-"  # only meaningful when classification.value == "buysell"
    design_choice: DesignChoiceDTO = DesignChoiceMissingDTO()

    # LLM verdict (SDD §5.3)
    classification: ClassificationDTO

    # Provenance for the two "Verify in Salesforce ↗" links + debugging
    source: IntakeSourceDTO

    # Soft warnings - partial-success info to surface on the wizard's review step.
    warnings: list[str] = Field(default_factory=list)


class IntakeResponse(BaseModel):
    """POST /salesforce/intake response."""
    bundle: DealerBundleDTO | None = None
    error: str | None = None
