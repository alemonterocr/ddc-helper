"""LangGraph wiring for the GM nav-parsing flow.

Linear (1-node) graph today:
  parse_nav → END

Kept as a graph rather than a free function so future nodes can extend it
without restructuring the orchestration. Likely future additions:
  - validate node (sanity-check that all URLs are reachable, optional)
  - dedup_existing node (skip URLs that are already pages in this project)
"""

from typing import Awaitable, Callable

from langgraph.graph import END, StateGraph

from src.ports.outbound import LLMPort

from .parse_nav_node import NavParseState, build_parse_nav_node

Progress = Callable[[str], Awaitable[None]]


def build_nav_parser_graph(
    llm: LLMPort,
    progress: Progress | None = None,
):
    graph = StateGraph(NavParseState)

    graph.add_node("parse_nav", build_parse_nav_node(llm, progress))

    graph.set_entry_point("parse_nav")
    graph.add_edge("parse_nav", END)

    return graph.compile()
