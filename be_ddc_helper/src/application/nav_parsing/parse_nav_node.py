"""Parse-nav node — LLM-driven navigation parser.

Takes a navigation-menu HTML snippet and a base URL, asks the LLM to extract
all navigation links with title, absolute URL, and category (`general` vs
`model_specific`). Returns the deduplicated list.

Single-node LangGraph because nav parsing is non-deterministic (extract +
dedupe + categorize + URL resolution). Kept as a graph for architectural
consistency with the analyze pipeline and to leave room for future nodes
(e.g. validation, dedup-against-existing-pages).
"""

from typing import Awaitable, Callable, TypedDict

from src.ports.outbound import LLMPort

Progress = Callable[[str], Awaitable[None]]


class NavParseState(TypedDict, total=False):
    html: str
    base_url: str
    dealer_id: str
    pages: list[dict]
    warnings: list[str]


def build_parse_nav_node(
    llm: LLMPort,
    progress: Progress | None = None,
):
    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def parse_nav(state: NavParseState) -> dict:
        html = state.get("html", "")
        base_url = state.get("base_url", "")

        await _progress("AI is parsing navigation links")

        try:
            pages = await llm.parse_nav(html, base_url)
        except Exception:
            await _progress("⚠ Nav parsing failed")
            return {"pages": [], "warnings": ["Nav parsing failed — try again"]}

        # Filter trigger buttons (LLM should already skip these, but belt + suspenders)
        valid = [
            p for p in pages
            if isinstance(p, dict)
            and p.get("url")
            and p["url"] != "N/A"
            and p.get("title")
        ]

        general_count = sum(1 for p in valid if p.get("category") == "general")
        await _progress(f"✓ Found {len(valid)} page(s) ({general_count} general)")

        return {"pages": valid, "warnings": []}

    return parse_nav
