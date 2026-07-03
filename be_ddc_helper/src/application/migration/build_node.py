"""Build node — the deterministic core.

Runs `discover_sections` (geometric row/column grouping → DDC layout) and
`editorial_chunk` (split each slot at headings/standalone images) on the
already-pruned, chrome-reviewed tree.

This is the section-discovery engine. The LangGraph wrapper exists to expose
it as a step; the algorithm itself lives in `domain/deterministic_migrate.py`
and is intentionally not touched here.
"""

from typing import Awaitable, Callable

from src.domain.deterministic_migrate import discover_sections, editorial_chunk
from src.domain.models import MigrationState

Progress = Callable[[str], Awaitable[None]]


def build_build_node(progress: Progress | None = None):
    async def build(state: MigrationState) -> dict:
        if progress is not None:
            await progress("Identifying structure")
        tree = state["pruned_tree"]
        sections = discover_sections(tree)
        plan: list[dict] = []
        for layout, slot_nodes in sections:
            slots = [editorial_chunk(n) for n in slot_nodes]
            plan.append({
                "section": layout,
                "slots": slots,
                "_slot_nodes": slot_nodes,
            })
        return {"det_plan": plan}

    return build
