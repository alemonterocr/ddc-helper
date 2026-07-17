"""Extract-staff node — LLM-driven staff-page parser.

One-node LangGraph because parsing staff HTML is non-deterministic (department
names vary, photo URLs need resolution, bios may span multiple elements).

State carries the raw HTML + base URL; the node calls `llm.extract_staff`,
filters out malformed rows, and returns a clean list of staff dicts. Trigger
buttons and `.heic` photos are already filtered by the prompt, but we
double-check on the way out.
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
        # Strip scripts/styles/svg/inline-style noise before the LLM sees it —
        # a raw staff page is mostly non-content that inflates tokens/latency.
        html = strip_noise(state.get("html", ""))
        base_url = state.get("base_url", "")

        await _progress("AI is reading the staff page")

        try:
            members = await llm.extract_staff(html, base_url)
        except Exception:
            await _progress("⚠ Staff extraction failed")
            return {"staff": [], "warnings": ["Staff extraction failed — try again"]}

        # Drop rows missing required fields. The LLM should already enforce
        # this; this is defensive against malformed JSON from the model.
        valid = [
            m for m in members
            if isinstance(m, dict)
            and m.get("name")
            and m.get("department")
        ]

        with_photo = sum(1 for m in valid if m.get("has_photo"))
        await _progress(
            f"✓ Found {len(valid)} staff member(s) ({with_photo} with photos)"
        )

        return {"staff": valid, "warnings": []}

    return extract_staff
