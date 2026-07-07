"""LangGraph wiring for the streaming page-translation workflow.

  extract_widgets → check → (Send fan-out) → translate_widget → END

The check node returns nothing about routing; `route_to_widget_branches` (a pure
conditional edge) fans out one `translate_widget` branch per to-translate widget.
When nothing needs translation the conditional edge returns [] and the run ends
with an empty `results` list.
"""

from langgraph.graph import END, StateGraph

from src.ports.outbound import LLMPort

from .check_node import build_check_node
from .extract_node import build_extract_node
from .routing import route_to_widget_branches
from .state import PageTranslateState
from .translate_widget_node import build_translate_widget_node


def build_translate_page_graph(llm: LLMPort):
    graph = StateGraph(PageTranslateState)

    graph.add_node("extract_widgets", build_extract_node())
    graph.add_node("check", build_check_node(llm))
    graph.add_node("translate_widget", build_translate_widget_node(llm))

    graph.set_entry_point("extract_widgets")
    graph.add_edge("extract_widgets", "check")
    graph.add_conditional_edges("check", route_to_widget_branches, ["translate_widget"])
    graph.add_edge("translate_widget", END)

    return graph.compile()
