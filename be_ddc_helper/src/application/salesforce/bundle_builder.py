"""Combine parser + classifier + step metadata into a DealerBundleDTO.

Pure function - no I/O. The orchestrator wires it once all 4 steps have
returned. Centralises the "missing value → '-'" coalescing so the DTO defaults
in `bundle_dtos.py` aren't the only line of defense.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .bundle_dtos import (
    ClassificationDTO,
    DealerBundleDTO,
    DesignChoiceDescriptionDTO,
    DesignChoiceJsonDTO,
    DesignChoiceMissingDTO,
    DesignChoiceDTO,
    IntakeSourceDTO,
)
from .classifier import ClassificationVerdict
from .questionnaire_parser import (
    DesignChoiceDescription,
    DesignChoiceJson,
    DesignChoiceMissing,
    ParsedQuestionnaire,
)

MISSING = "-"


def build_bundle(
    *,
    board_id: str,
    questionnaire_insight_id: str | None,
    precursive_project_id: str | None,
    ppr: str | None,
    dealer_id: str | None,
    parsed: ParsedQuestionnaire,
    verdict: ClassificationVerdict,
    warnings: list[str] | None = None,
) -> DealerBundleDTO:
    """Assemble the bundle the FE renders.

    Every `None` becomes `"-"` so the FE never has to handle missing values.
    The classification verdict's `new_dealership_name` is honoured even when
    `parsed.dealership_name` is also set - the LLM extracts the new name from
    the description body, which may differ from the top-level Name row.
    """
    warnings = list(warnings or [])

    return DealerBundleDTO(
        ppr=_coalesce(ppr),
        dealer_id=_coalesce(dealer_id),
        dealership_name=_coalesce(parsed.dealership_name),
        new_dealership_name=_coalesce(verdict.new_dealership_name),
        dealership_address=_coalesce(parsed.dealership_address),
        leads_email=_coalesce(parsed.leads_email),
        primary_url=_coalesce(parsed.primary_url),
        new_primary_url=_coalesce(parsed.new_primary_url),
        design_choice=_map_design_choice(parsed.design_choice),
        classification=ClassificationDTO(
            value=verdict.value,
            confidence=verdict.confidence,
            reasoning=verdict.reasoning,
            source="llm" if verdict.confidence > 0 else "default",
        ),
        source=IntakeSourceDTO(
            board_id=board_id,
            questionnaire_insight_id=_coalesce(questionnaire_insight_id),
            precursive_project_id=_coalesce(precursive_project_id),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=warnings,
    )


def _coalesce(value: str | None) -> str:
    """Return the value or the literal '-' sentinel."""
    if value is None:
        return MISSING
    stripped = value.strip()
    return stripped if stripped else MISSING


def _map_design_choice(
    choice: DesignChoiceJson | DesignChoiceDescription | DesignChoiceMissing,
) -> DesignChoiceDTO:
    if isinstance(choice, DesignChoiceJson):
        return DesignChoiceJsonDTO(value=choice.value)
    if isinstance(choice, DesignChoiceDescription):
        return DesignChoiceDescriptionDTO(raw=choice.raw)
    return DesignChoiceMissingDTO()
