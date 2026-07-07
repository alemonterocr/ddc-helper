"""Translate-widget node — the per-widget fan-out branch.

Each Send branch runs one widget through the reused `translate_labels_graph`
(glossary tool → structural validator → semantic judge → 1 retry) and appends a
single result to the fan-in accumulator. The widget's inner HTML is just a
larger `en_html` than a label.
"""

from src.ports.outbound import LLMPort

from src.application.translate_labels.translate_labels_graph import (
    build_translate_labels_graph,
)


def build_translate_widget_node(llm: LLMPort):
    translate_graph = build_translate_labels_graph(llm=llm)

    async def translate_widget(state: dict) -> dict:
        widget: dict = state["widget"]
        out = await translate_graph.ainvoke(
            {
                "alias": widget["window_id"],
                "en_html": widget["en_html"],
                "dealer_name": state.get("dealer_name", ""),
            }
        )
        result = {
            "window_id": widget["window_id"],
            "widget_type": widget["widget_type"],
            "en_html": widget["en_html"],
            "es_html": str(out.get("es_html", "")),
            "status": str(out.get("status", "error")),
            "warnings": list(out.get("warnings", [])),
            "raw": out.get("raw"),
            "reasoning": str(out.get("reasoning", "")),
        }
        return {"results": [result]}

    return translate_widget
