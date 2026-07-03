"""Chrome-review node — LLM-decides KEEP/DROP for chrome candidates.

Walks the pruned tree for `_chrome_candidate: True` nodes (set by the
deterministic `strip_chrome` pass), asks the LLM whether each subtree is
real dealer content or page chrome, then removes DROP subtrees in place.

Runs BEFORE build so layout discovery sees only content.

One batched LLM call per request via `LLMPort.classify_chrome_batch`. On
transport/parse failure the port returns all-KEEP — safer to over-include
than to drop real content.
"""

from typing import Awaitable, Callable

from src.domain.deterministic_migrate import render_html
from src.domain.models import MigrationState
from src.ports.outbound import LLMPort

Progress = Callable[[str], Awaitable[None]]


def build_chrome_review_node(
    llm: LLMPort | None,
    progress: Progress | None = None,
):
    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def chrome_review(state: MigrationState) -> dict:
        tree = state["pruned_tree"]
        candidates = _collect_candidates(tree)

        if not candidates:
            return {"pruned_tree": tree}

        if llm is None:
            await _progress("⚠ AI unavailable — keeping all chrome candidates")
            return {"pruned_tree": _filter_tree(tree, drop_ids=set())}

        await _progress("AI is reviewing chrome candidates")

        snippets = [render_html(c) for c in candidates]
        try:
            verdicts = await llm.classify_chrome_batch(snippets)
        except Exception:
            await _progress("⚠ Chrome review failed — keeping all")
            verdicts = ["KEEP"] * len(candidates)

        drop_ids: set[int] = set()
        for cand, verdict in zip(candidates, verdicts):
            if verdict == "DROP":
                drop_ids.add(id(cand))

        return {"pruned_tree": _filter_tree(tree, drop_ids)}

    return chrome_review


def _collect_candidates(node) -> list[dict]:
    """Depth-first collect of dict refs flagged `_chrome_candidate: True`."""
    out: list[dict] = []
    if not isinstance(node, dict):
        return out
    if node.get("_chrome_candidate"):
        out.append(node)
    for c in node.get("children", []):
        out.extend(_collect_candidates(c))
    return out


def _filter_tree(node, drop_ids: set[int]):
    """Return a copy of `node` with DROP-marked subtrees removed and
    `_chrome_candidate` flags cleared from survivors."""
    if not isinstance(node, dict):
        return node
    if id(node) in drop_ids:
        return None
    out = dict(node)
    out.pop("_chrome_candidate", None)
    kept: list = []
    for c in node.get("children", []):
        keep = _filter_tree(c, drop_ids)
        if keep is not None:
            kept.append(keep)
    out["children"] = kept
    return out
