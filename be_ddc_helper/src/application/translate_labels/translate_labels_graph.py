"""LangGraph wiring for label EN→es_US translation.

Linear (1-node) graph today:
  translate_label → END

Kept as a graph so future nodes can extend it without restructuring the
orchestration. Likely future additions:
  - load_existing_es node (skip when es_US already present in DDC)
  - dictionary_postprocess node (deterministic post-edit pass)
"""

from langgraph.graph import END, StateGraph

from src.ports.outbound import LLMPort

from .translate_label_node import TranslateLabelState, build_translate_label_node


def build_translate_labels_graph(llm: LLMPort):
    graph = StateGraph(TranslateLabelState)
    graph.add_node("translate_label", build_translate_label_node(llm))
    graph.set_entry_point("translate_label")
    graph.add_edge("translate_label", END)
    return graph.compile()
