"""Translate-label node — tool-assisted translation + LLM guardrail.

Flow per request:
  1. Translator with glossary_lookup tool access (multi-turn inside adapter)
  2. Structural validator (deterministic — tag count, href, brackets)
  3. Semantic guardrail (LLM-as-judge) — skipped when structural already failed
  4. If anything failed → ONE corrective retry with combined hint
  5. After retry, return whatever we have with status reflecting issues

The retry budget is intentionally tight (1 retry total). The original code's
trade-off — let the user hand-edit on persistent failure rather than spin
through endless retries — still applies.
"""

from dataclasses import dataclass
from typing import TypedDict

from src.domain.translations import glossary_search
from src.ports.outbound import LLMPort

from .validator import validate_translation


class TranslateLabelState(TypedDict, total=False):
    alias: str
    en_html: str
    dealer_name: str
    es_html: str
    status: str          # "ready" | "error"
    warnings: list[str]
    raw: str | None      # populated only when status == "error"
    reasoning: str       # translator's brief reasoning, surfaced to FE


@dataclass(frozen=True)
class _Attempt:
    """Result of one translate-label attempt, before validation."""
    es: str
    reasoning: str


# ── LLM-side helpers ─────────────────────────────────────────────────────────


async def _judge(llm: LLMPort, en: str, es: str, dealer: str) -> dict:
    try:
        verdict = await llm.judge_translation(en, es, dealer)
    except Exception:
        # Failing closed would block the entire pipeline; let it through.
        return {"ok": True, "reason": ""}
    if not isinstance(verdict, dict):
        return {"ok": True, "reason": ""}
    return {"ok": bool(verdict.get("ok", True)), "reason": str(verdict.get("reason", ""))}


async def _try_translate(
    llm: LLMPort, en_html: str, dealer: str, extra_hint: str | None = None
) -> _Attempt | None:
    """One translator call. Returns the attempt or None if the LLM raised."""
    try:
        result = (
            await llm.translate_label_with_tools(en_html, dealer, glossary_search, extra_hint=extra_hint)
            if extra_hint is not None
            else await llm.translate_label_with_tools(en_html, dealer, glossary_search)
        )
    except Exception:
        return None
    return _Attempt(es=result.get("translation", ""), reasoning=result.get("reasoning", ""))


async def _check(llm: LLMPort, en_html: str, es: str, dealer: str) -> tuple[list[str], dict]:
    """Run structural + semantic checks. Skip the judge when structural already failed."""
    structural = validate_translation(en_html, es)
    verdict = (
        {"ok": False, "reason": "structural issues — skipping semantic review"}
        if structural
        else await _judge(llm, en_html, es, dealer)
    )
    return structural, verdict


def _build_retry_hint(structural: list[str], verdict: dict) -> str:
    parts: list[str] = []
    if structural:
        parts.append("Structural issues to fix: " + "; ".join(structural))
    if not verdict.get("ok") and verdict.get("reason"):
        parts.append("Reviewer feedback: " + verdict["reason"])
    return " ".join(parts)


# ── Response builders ────────────────────────────────────────────────────────


def _error_state(warnings: list[str], reasoning: str = "") -> dict:
    return {"es_html": "", "status": "error", "warnings": warnings, "raw": None, "reasoning": reasoning}


def _ready_state(es: str, reasoning: str) -> dict:
    return {"es_html": es, "status": "ready", "warnings": [], "raw": None, "reasoning": reasoning}


def _final_state(
    es: str, reasoning: str, structural: list[str], verdict: dict
) -> dict:
    warnings = list(structural)
    if not verdict["ok"]:
        warnings.append(f"Reviewer: {verdict['reason']}")
    passed = not structural and verdict["ok"]
    return {
        "es_html": es,
        "status": "ready" if passed else "error",
        "warnings": warnings,
        "raw": None if passed else es,
        "reasoning": reasoning,
    }


def _retry_failed_state(first: _Attempt, structural: list[str], verdict: dict) -> dict:
    """Retry LLM raised: return the first attempt with the first-round validation
    context so the user can see WHY it wasn't accepted."""
    warnings = list(structural)
    if not verdict["ok"]:
        warnings.append(f"Reviewer: {verdict['reason']}")
    return {
        "es_html": first.es,
        "status": "error",
        "warnings": warnings,
        "raw": first.es,
        "reasoning": first.reasoning,
    }


# ── Node builder ─────────────────────────────────────────────────────────────


def build_translate_label_node(llm: LLMPort):
    async def translate_label(state: TranslateLabelState) -> dict:
        en_html = state.get("en_html", "")
        dealer = state.get("dealer_name", "")
        if not en_html.strip():
            return _error_state(["Empty input"])

        first = await _try_translate(llm, en_html, dealer)
        if first is None:
            return _error_state(["LLM call failed"])

        structural, verdict = await _check(llm, en_html, first.es, dealer)
        if not structural and verdict["ok"]:
            return _ready_state(first.es, first.reasoning)

        hint = _build_retry_hint(structural, verdict)
        retry = await _try_translate(llm, en_html, dealer, extra_hint=hint)
        if retry is None:
            return _retry_failed_state(first, structural, verdict)

        structural_retry, verdict_retry = await _check(llm, en_html, retry.es, dealer)
        return _final_state(retry.es, retry.reasoning, structural_retry, verdict_retry)

    return translate_label
