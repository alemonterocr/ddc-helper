"""Extract node — turns the two page renders into paired widget candidates."""

from .state import PageTranslateState
from .widget_extract import extract_widgets


def build_extract_node():
    async def extract(state: PageTranslateState) -> dict:
        candidates = extract_widgets(
            state.get("en_page_html", ""),
            state.get("es_page_html", ""),
        )
        return {"candidates": candidates}

    return extract
