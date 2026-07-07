"""Pure fan-out routing — one Send branch per widget that needs translation.

No I/O and no side effects (constitution: routing functions stay pure). The
LLM work happened in `check_node`; this only maps `to_translate` into `Send`s.
"""

from langgraph.types import Send

from .state import PageTranslateState


def route_to_widget_branches(state: PageTranslateState) -> list[Send]:
    dealer = state.get("dealer_name", "")
    return [
        Send("translate_widget", {"widget": widget, "dealer_name": dealer})
        for widget in state.get("to_translate", [])
    ]
