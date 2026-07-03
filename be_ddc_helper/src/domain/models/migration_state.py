from typing import TypedDict


class MigrationState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────
    dealer_id: str
    site_id: str
    page_alias: str
    page_title: str

    # ── Input ─────────────────────────────────────────────────────────
    dom_skeleton: dict

    # ── Intermediate ──────────────────────────────────────────────────
    pruned_tree: dict           # after prune + chrome_review
    det_plan: list[dict]        # after build (sections with _slot_nodes)

    # ── Output ────────────────────────────────────────────────────────
    section_plan: list[dict]
    warnings: list[str]
