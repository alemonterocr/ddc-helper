"""Graph state for the streaming page-translation workflow.

`results` uses an additive reducer so the parallel `Send` branches can each
append their single widget result concurrently without clobbering one another.
"""

import operator
from typing import Annotated, TypedDict


class PageTranslateState(TypedDict, total=False):
    # ── inputs ──
    en_page_html: str
    es_page_html: str
    dealer_name: str
    provider: str
    # ── produced by extract_node ──
    candidates: list[dict]        # all paired widgets (PageWidget-shaped dicts)
    # ── produced by check_node ──
    to_translate: list[dict]      # drives the Send fan-out
    skipped: list[dict]
    # ── fan-in accumulator (parallel-safe) ──
    results: Annotated[list[dict], operator.add]
