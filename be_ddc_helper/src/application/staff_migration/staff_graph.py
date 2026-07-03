"""LangGraph wiring for the staff-page extraction flow.

Linear (1-node) graph today:
  extract_staff → END

Kept as a graph rather than a free function so future nodes can extend it
without restructuring the orchestration. Likely future additions:
  - dedup node (same name appears twice → merge)
  - validate_photos node (probe original_photo_url for 200)
"""

from typing import Awaitable, Callable

from langgraph.graph import END, StateGraph

from src.ports.outbound import LLMPort

from .extract_staff_node import StaffExtractState, build_extract_staff_node

Progress = Callable[[str], Awaitable[None]]


def build_staff_extraction_graph(
    llm: LLMPort,
    progress: Progress | None = None,
):
    graph = StateGraph(StaffExtractState)

    graph.add_node("extract_staff", build_extract_staff_node(llm, progress))

    graph.set_entry_point("extract_staff")
    graph.add_edge("extract_staff", END)

    return graph.compile()
