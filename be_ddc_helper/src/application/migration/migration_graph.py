"""LangGraph wiring for the deterministic+LLM hybrid migration pipeline.

Linear flow:
  prune → chrome_review → build → typify → image_split → convert → enrich → END.

The deterministic algorithm in `domain/deterministic_migrate.py` is the
engine. Nodes here are thin orchestrators that call into it; LLM steps only
resolve uncertainty surfaced by the deterministic layer:

  * chrome_review — KEEP/DROP per chrome candidate (binary)
  * typify       — what widget type is this? (bounded 5-class, anchored on
                   concrete textual signals — see typify_node.py)
  * image_split  — promote/keep per residual <img> in content widgets (binary)
  * enrich       — HTML beautify + intent copywriting (not a structural call)

The LLM is never asked to pick a DDC layout from 5 abstract options based on
geometry — that's the reclassify case that was deleted. Bounded N-class on
textual widget type is allowed; abstract layout picking is not.

The factory takes runtime deps (llm, catalog, progress, feature flags) and
builds the graph fresh per request. Compilation is in-memory and cheap;
this keeps the state TypedDict clean of callables.
"""

from typing import Awaitable, Callable

from langgraph.graph import END, StateGraph

from src.domain.models import MigrationState
from src.ports.outbound import LLMPort

from .build_node import build_build_node
from .chrome_review_node import build_chrome_review_node
from .convert_node import build_convert_node
from .enrich_node import build_enrich_node
from .image_split_node import build_image_split_node
from .prune_node import build_prune_node
from .typify_node import build_typify_node

Progress = Callable[[str], Awaitable[None]]


def build_migration_graph(
    llm: LLMPort | None = None,
    catalog: list[dict] | None = None,
    progress: Progress | None = None,
    typify_enabled: bool = True,
    image_split_enabled: bool = True,
    enrich_enabled: bool = True,
):
    graph = StateGraph(MigrationState)

    graph.add_node("prune", build_prune_node(progress))
    graph.add_node("chrome_review", build_chrome_review_node(llm, progress))
    graph.add_node("build", build_build_node(progress))
    graph.add_node("typify", build_typify_node(llm, progress, typify_enabled))
    graph.add_node("image_split", build_image_split_node(llm, progress, image_split_enabled))
    graph.add_node("convert", build_convert_node(catalog or [], progress))
    graph.add_node("enrich", build_enrich_node(llm, progress, enrich_enabled))

    graph.set_entry_point("prune")
    graph.add_edge("prune", "chrome_review")
    graph.add_edge("chrome_review", "build")
    graph.add_edge("build", "typify")
    graph.add_edge("typify", "image_split")
    graph.add_edge("image_split", "convert")
    graph.add_edge("convert", "enrich")
    graph.add_edge("enrich", END)

    return graph.compile()
