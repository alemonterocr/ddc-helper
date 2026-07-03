"""DDC migration prototype v2 — deterministic, geometry-based pipeline.

Two-phase:
  1. Section discovery is recursive, geometry-based. Groups children into rows
     (stacked) or columns (side-by-side) from x/y/w/h, then classifies
     multi-column groups into one of the 5 DDC layouts via width ratios.
  2. Editorial chunking — within each section slot, split at heading and
     standalone-image boundaries.

Backward-compat shim after the 2026-07-01 split. Historically this module
held every predicate + rendering helper (890 LOC). The implementation now
lives in `src.domain.migration.*`:

    _atoms       — shared bootstrap col-width parser
    chrome       — chrome detection + pruning
    tree_cleanup — unwrap singletons + filter meaningful
    buttons      — button detection + DTO extraction
    chunking     — editorial chunking + HTML rendering
    discovery    — row/column grouping + section discovery

Every symbol external callers used is re-exported below so
`from src.domain.deterministic_migrate import ...` keeps working.
"""
from __future__ import annotations

# Re-export the surface external modules use.  build_node imports
# discover_sections/editorial_chunk, prune_node imports strip_chrome,
# chrome_review_node imports render_html, analyze_deterministic_router
# imports migrate.  Tests hit migrate as well.
from src.domain.migration.chrome import strip_chrome
from src.domain.migration.chunking import editorial_chunk, render_html
from src.domain.migration.discovery import discover_sections

__all__ = [
    "discover_sections",
    "editorial_chunk",
    "migrate",
    "render_html",
    "strip_chrome",
]


def migrate(skeleton: dict) -> list[dict]:
    """Run the deterministic migration pipeline on a raw skeleton dict.

    Returns a list of section dicts:
      {
        section:     str,                   # DDC layout name
        slots:       list[list[widget]],    # editorial chunks per slot
        _slot_nodes: list[dict],            # raw DOM nodes (for LLM fallback)
      }
    where each widget is { type, html?, preview?, url?, node_count? }.
    _slot_nodes is an internal field consumed by the analyze router; it is
    not forwarded to the frontend.
    """
    structure = skeleton.get('structure', {})
    root = strip_chrome(structure)
    sections = discover_sections(root)
    plan = []
    for layout, slot_nodes in sections:
        slots = [editorial_chunk(n) for n in slot_nodes]
        plan.append({
            'section': layout,
            'slots': slots,
            '_slot_nodes': slot_nodes,
        })
    return plan
