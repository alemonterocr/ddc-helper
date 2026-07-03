"""LangGraph wiring for the Salesforce intake flow.

Parallel fan-out from START - both 4-step chains start independently. The
implicit join happens at `parse_and_classify`, which reads keys that both
chains have written.

   START ──┬──► fetch_insight_id ──► fetch_questionnaire_text ──┐
           │                                                     ├──► parse_and_classify ──► assemble_bundle ──► END
           └──► fetch_project_id  ──► fetch_ppr_dealer ──────────┘

This is a NEW graph - independent from `nav_parser_graph` and
`migration_graph`. They share no state, no nodes, no compiled graph instance.
"""

from typing import Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.ports.outbound import LLMPort

from .intake_nodes import (
    IntakeState,
    build_assemble_bundle_node,
    build_extract_fields_node,
    build_fetch_insight_id_node,
    build_fetch_ppr_dealer_node,
    build_fetch_project_id_node,
    build_fetch_questionnaire_text_node,
    build_parse_and_classify_node,
)

Progress = Callable[[str], Awaitable[None]]


def build_intake_graph(
    bridge: WsBridgeAdapter,
    llm: LLMPort,
    progress: Progress | None = None,
):
    graph = StateGraph(IntakeState)

    graph.add_node("fetch_insight_id", build_fetch_insight_id_node(bridge, progress))
    graph.add_node("fetch_questionnaire_text", build_fetch_questionnaire_text_node(bridge, progress))
    graph.add_node("fetch_project_id", build_fetch_project_id_node(bridge, progress))
    graph.add_node("fetch_ppr_dealer", build_fetch_ppr_dealer_node(bridge, progress))
    graph.add_node("parse_and_classify", build_parse_and_classify_node(llm, progress))
    graph.add_node("extract_fields", build_extract_fields_node(llm, progress))
    graph.add_node("assemble_bundle", build_assemble_bundle_node(progress))

    # Fan-out from START - both chains start concurrently.
    graph.add_edge(START, "fetch_insight_id")
    graph.add_edge(START, "fetch_project_id")

    # Chain 1: insight id → questionnaire text → parse_and_classify
    graph.add_edge("fetch_insight_id", "fetch_questionnaire_text")
    graph.add_edge("fetch_questionnaire_text", "parse_and_classify")

    # Chain 2: project id → PPR + dealer → parse_and_classify (join)
    graph.add_edge("fetch_project_id", "fetch_ppr_dealer")
    graph.add_edge("fetch_ppr_dealer", "parse_and_classify")

    # parse_and_classify joins both chains (LangGraph waits for all in-edges)
    graph.add_edge("parse_and_classify", "extract_fields")
    graph.add_edge("extract_fields", "assemble_bundle")
    graph.add_edge("assemble_bundle", END)

    return graph.compile()
