"""Extract-staff node — LLM-driven staff-page parser.

One-node LangGraph because parsing staff HTML is non-deterministic (department
names vary, photo URLs need resolution, bios may span multiple elements).

Single LLM call over the whole (noise-stripped) page. The page fits the model's
context easily (~18-27k input tokens vs a 200k window), and one call lets the
model see every department together — so department names stay consistent rather
than being re-invented per chunk. Output room, not input room, is the real
constraint, so the adapter sets a generous `max_tokens` (still well under the
model's 64k output cap).
"""

from typing import Awaitable, Callable, TypedDict

from src.ports.outbound import LLMPort

from .html_clean import strip_noise

Progress = Callable[[str], Awaitable[None]]


class StaffExtractState(TypedDict, total=False):
    html: str
    base_url: str
    dealer_id: str
    staff: list[dict]
    warnings: list[str]


def build_extract_staff_node(
    llm: LLMPort,
    progress: Progress | None = None,
):
    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def extract_staff(state: StaffExtractState) -> dict:
        # Strip scripts/styles/svg/inline-style noise before the LLM sees it.
        html = strip_noise(state.get("html", ""))
        base_url = state.get("base_url", "")

        # Report the input magnitude up front — streams to the progress log so
        # the size is visible even if the call then hangs or fails.
        approx_tokens = max(1, len(html) // 4)
        await _progress(
            f"AI is reading the staff page — {len(html):,} chars "
            f"(~{approx_tokens:,} tokens)"
        )

        try:
            members = await llm.extract_staff(html, base_url)
        except Exception:
            await _progress("⚠ Staff extraction failed")
            return {"staff": [], "warnings": ["Staff extraction failed — try again"]}

        # Drop rows missing required fields (defensive against malformed output).
        valid = [
            m for m in members
            if isinstance(m, dict) and m.get("name") and m.get("department")
        ]

        with_photo = sum(1 for m in valid if m.get("has_photo"))
        await _progress(
            f"✓ Found {len(valid)} staff member(s) ({with_photo} with photos)"
        )

        return {"staff": valid, "warnings": []}

    return extract_staff
