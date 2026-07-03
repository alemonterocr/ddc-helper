"""Prebuild vs. BuySell classifier.

Why LLM here when everything else is deterministic? Field labels in the
questionnaire drift across boards ("old name" / "previous name" / "former
dealership", etc.). The official `Is this a Buy/Sell` row is sometimes blank
or contradicted by the description body. A regex-and-rules classifier would
need constant maintenance; an LLM with a one-paragraph prompt handles drift
naturally for ~80 output tokens.

Inputs: the parsed questionnaire row dict (full dict - the LLM needs context
beyond the 5 normalised fields).

Output: ClassificationVerdict - value + confidence + reasoning + optional
newDealershipName for buysells.

Failure mode: any exception → default to prebuild + confidence:0. Never blocks
intake. The bundle builder marks the verdict's source as "default" so the FE
can surface a banner asking the user to confirm.

Prompts live in `adapters/outbound/prompts.py` and are invoked by each LLM
adapter's `classify_intake`. This module only orchestrates the call and parses
the response.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)


class _LLMLike(Protocol):
    """Minimal LLM surface this classifier needs - the slice of LLMPort we use.

    Defined as a structural Protocol so tests can pass a fake without importing
    the full LLMPort interface.
    """
    async def classify_intake(self, rows: dict[str, str]) -> str: ...


# Back-compat - pre-Phase-2b classifier accepted a Callable. Kept so existing
# tests in `tests/test_classifier.py` continue to pass without rewrite.
LLMClassifyCall = Callable[[str, str], Awaitable[str]]


@dataclass(frozen=True)
class ClassificationVerdict:
    value: str               # "prebuild" | "buysell"
    confidence: float        # 0.0..1.0
    reasoning: str           # "" on default
    new_dealership_name: str | None  # only when buysell


async def classify_intake_with_llm(
    rows: dict[str, str],
    llm: _LLMLike,
) -> ClassificationVerdict:
    """Production path - call LLMPort.classify_intake + parse + tolerate failure.

    On failure, logs the exception and returns a default verdict whose
    reasoning embeds the error class so the FE banner is more useful than
    "classifier unavailable".
    """
    try:
        raw = await llm.classify_intake(rows)
        verdict = _parse_response(raw)
        if verdict.confidence == 0.0 and verdict.value == "prebuild":
            # _parse_response defaulted - log the raw so we can see what came back.
            logger.warning("classify_intake: LLM response failed to parse: %r", raw[:300])
        return verdict
    except Exception as e:
        logger.exception("classify_intake: LLM call raised")
        return _default_verdict(reason=f"Classifier error ({type(e).__name__}): {e}")


async def classify_intake(
    rows: dict[str, str],
    llm_call: LLMClassifyCall,
) -> ClassificationVerdict:
    """Back-compat path - accepts a (system, user) → text Callable.

    The Callable receives the literal strings `"system"` and `"user"`; the
    prompt content lives inside the Callable's implementation. Used only by
    the existing test suite. Prefer `classify_intake_with_llm` in new code.
    """
    try:
        raw = await llm_call("system", "user")
        return _parse_response(raw)
    except Exception:
        return _default_verdict()


def _parse_response(raw: str) -> ClassificationVerdict:
    """Parse the LLM's JSON output. Tolerant of ```json fences or stray prose."""
    text = raw.strip()
    # Strip code fences if present.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()
    # Find the first { … } object - handles preambles like "Here's the JSON: {...}".
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return _default_verdict()
    candidate = text[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return _default_verdict()

    value = data.get("classification")
    if value not in ("prebuild", "buysell"):
        return _default_verdict()

    confidence = data.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reasoning = str(data.get("reasoning") or "").strip()

    new_name = data.get("newDealershipName")
    if isinstance(new_name, str):
        new_name = new_name.strip() or None
    else:
        new_name = None

    return ClassificationVerdict(
        value=value,
        confidence=confidence,
        reasoning=reasoning,
        new_dealership_name=new_name if value == "buysell" else None,
    )


def _default_verdict(reason: str | None = None) -> ClassificationVerdict:
    """Conservative fallback: assume prebuild, zero confidence. The FE will
    surface a banner asking the user to confirm. `reason` (when supplied)
    surfaces the concrete underlying error.
    """
    return ClassificationVerdict(
        value="prebuild",
        confidence=0.0,
        reasoning=reason or "LLM classifier unavailable. Please confirm classification manually.",
        new_dealership_name=None,
    )
