"""Extract-staff node — LLM-driven staff-page parser.

One-node LangGraph because parsing staff HTML is non-deterministic (department
names vary, photo URLs need resolution, bios may span multiple elements).

State carries the raw HTML + base URL. The node strips non-content noise, then
extracts staff. Large rosters are split into overlapping chunks and extracted
in parallel — a single call can't emit the JSON for dozens of people without
truncating — and the results are merged and deduped. Malformed rows are
filtered on the way out.
"""

import asyncio
from typing import Awaitable, Callable, TypedDict

from src.ports.outbound import LLMPort

from .html_clean import chunk_html, dedup_staff, strip_noise

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

        # A big roster's JSON output won't fit one response — chunk it.
        chunks = chunk_html(html)

        # Report input magnitude + chunk count up front — streams to the
        # progress log so the size is visible even if the calls then fail.
        approx_tokens = max(1, len(html) // 4)
        await _progress(
            f"AI is reading the staff page — {len(html):,} chars "
            f"(~{approx_tokens:,} tokens) in {len(chunks)} chunk(s)"
        )

        results = await asyncio.gather(
            *(llm.extract_staff(chunk, base_url) for chunk in chunks),
            return_exceptions=True,
        )

        members: list[dict] = []
        failures = 0
        for result in results:
            if isinstance(result, BaseException):
                failures += 1
                continue
            members.extend(result)

        if failures == len(results):
            await _progress("⚠ Staff extraction failed")
            return {"staff": [], "warnings": ["Staff extraction failed — try again"]}

        # Merge overlapping-chunk duplicates, then drop rows missing required
        # fields (defensive against malformed model output).
        valid = [
            m for m in dedup_staff(members)
            if m.get("name") and m.get("department")
        ]

        warnings: list[str] = []
        if failures:
            warnings.append(
                f"{failures} of {len(results)} page chunk(s) failed — "
                "some staff may be missing."
            )

        with_photo = sum(1 for m in valid if m.get("has_photo"))
        await _progress(
            f"✓ Found {len(valid)} staff member(s) ({with_photo} with photos)"
        )

        return {"staff": valid, "warnings": warnings}

    return extract_staff
