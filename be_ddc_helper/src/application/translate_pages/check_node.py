"""Check node — decide which widgets still need translation.

Three-way, deterministic-first:
  - es empty                     → translate (no LLM)
  - es.strip() == en.strip()     → translate (DDC serves the English fallback)
  - otherwise                    → judge_translation: keep only genuine translations

The LLM is spent only on the ambiguous middle case — a non-empty es that differs
from en, which may be a real translation OR the Spanish placeholder text DDC
auto-injects. Ambiguous checks run concurrently under a semaphore.
"""

import asyncio

from src.ports.outbound import LLMPort

from .state import PageTranslateState

_MAX_CONCURRENT_JUDGES = 5


def _needs_translation_deterministic(widget: dict) -> bool | None:
    """True/False when decidable without an LLM; None when ambiguous."""
    en = widget.get("en_html", "")
    es = widget.get("es_html", "")
    if not es.strip():
        return True
    if es.strip() == en.strip():
        return True
    return None


def build_check_node(llm: LLMPort):
    async def check(state: PageTranslateState) -> dict:
        candidates: list[dict] = state.get("candidates", [])
        dealer = state.get("dealer_name", "")

        ambiguous: list[dict] = []
        to_translate: list[dict] = []
        skipped: list[dict] = []

        for widget in candidates:
            decided = _needs_translation_deterministic(widget)
            if decided is True:
                to_translate.append(widget)
            else:
                ambiguous.append(widget)

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_JUDGES)

        async def is_faithful(widget: dict) -> bool:
            async with semaphore:
                verdict = await llm.judge_translation(
                    widget.get("en_html", ""), widget.get("es_html", ""), dealer
                )
            return bool(verdict.get("ok", True)) if isinstance(verdict, dict) else True

        if ambiguous:
            verdicts = await asyncio.gather(*(is_faithful(w) for w in ambiguous))
            for widget, faithful in zip(ambiguous, verdicts):
                (skipped if faithful else to_translate).append(widget)

        return {"to_translate": to_translate, "skipped": skipped}

    return check
