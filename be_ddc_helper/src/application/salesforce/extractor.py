"""LLM-driven typed-field extraction for Salesforce questionnaires.

Replaces the deterministic label-matching pass that lived in
`questionnaire_parser.py`. The labels drift across boards (same reason
classification uses an LLM — see `classifier.py:3-8`), so we hand the full
row dict + classification verdict to the LLM and let it pick the right
values via a structured tool call.

The application layer applies cheap, deterministic post-processing
(URL `https://` prefix, smart-title-case address, lowercase email,
design-choice JSON probe) to the LLM's raw strings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.ports.outbound import LLMPort

from .questionnaire_parser import (
    DesignChoice,
    DesignChoiceDescription,
    DesignChoiceJson,
    DesignChoiceMissing,
    _clean_or_none,
    _normalise_url,
    _parse_design_choice,
)
from .title_case import smart_title_case

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFields:
    """Typed-field output, post-processed and ready for the bundle builder."""
    dealership_name: str | None = None
    new_dealership_name: str | None = None
    dealership_address: str | None = None
    leads_email: str | None = None
    primary_url: str | None = None
    new_primary_url: str | None = None
    design_choice: DesignChoice = field(default_factory=DesignChoiceMissing)


_EMPTY_RAW: dict = {
    "dealership_name": None,
    "new_dealership_name": None,
    "dealership_address": None,
    "leads_email": None,
    "primary_url": None,
    "new_primary_url": None,
    "design_choice": None,
}


async def extract_fields_with_llm(
    rows: dict[str, str],
    classification: str,
    llm: LLMPort,
) -> tuple[ExtractedFields, list[str]]:
    """Production path — call LLMPort.extract_intake_fields + post-process.

    Returns (fields, warnings). On any LLM failure, fields are all-None and
    one warning describing the error class is appended. Never raises.
    """
    warnings: list[str] = []

    if not rows:
        return ExtractedFields(), warnings

    try:
        raw = await llm.extract_intake_fields(rows, classification)
    except Exception as e:
        logger.exception("extract_intake_fields: LLM call raised")
        warnings.append(f"Field extractor unavailable ({type(e).__name__}); typed fields left empty.")
        raw = dict(_EMPTY_RAW)

    if not isinstance(raw, dict):
        warnings.append("Field extractor returned non-dict; typed fields left empty.")
        raw = dict(_EMPTY_RAW)

    # Apply deterministic post-processing.
    address_raw = _clean_or_none(raw.get("dealership_address"))
    email_raw = _clean_or_none(raw.get("leads_email"))

    return ExtractedFields(
        dealership_name=_clean_or_none(raw.get("dealership_name")),
        new_dealership_name=_clean_or_none(raw.get("new_dealership_name"))
            if classification == "buysell" else None,
        dealership_address=smart_title_case(address_raw) if address_raw else None,
        leads_email=email_raw.lower() if email_raw else None,
        primary_url=_normalise_url(_clean_or_none(raw.get("primary_url"))),
        new_primary_url=_normalise_url(_clean_or_none(raw.get("new_primary_url")))
            if classification == "buysell" else None,
        design_choice=_parse_design_choice(raw.get("design_choice")),
    ), warnings
