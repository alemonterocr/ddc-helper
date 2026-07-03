"""Prune node — wraps the deterministic strip_chrome pass.

Hard-drops definite chrome (`<header>`, `<footer>`, `<nav>`, `<aside>`) and
marks class-word-flagged subtrees with `_chrome_candidate: True` for the
chrome_review node to decide on.
"""

from typing import Awaitable, Callable

from src.domain.deterministic_migrate import strip_chrome
from src.domain.models import MigrationState

Progress = Callable[[str], Awaitable[None]]


def build_prune_node(progress: Progress | None = None):
    async def prune(state: MigrationState) -> dict:
        if progress is not None:
            await progress("Trimming chrome")
        structure = state["dom_skeleton"].get("structure", {})
        return {"pruned_tree": strip_chrome(structure)}

    return prune
