"""Recursive geometric section discovery.

`discover_sections` walks a chrome-stripped tree, groups sibling nodes into
rows by y-overlap, and classifies each row's column ratios into a DDC layout.
Sections it can't classify recurse into their children until a match is found
or a slot resolves to `empty-one`.

Consecutive `empty-one` runs at the same parent are merged so stacked editorial
content (heading → image → text → button) stays together as one section.
"""
from __future__ import annotations

from src.domain.migration._atoms import get_bootstrap_col_width
from src.domain.migration.buttons import is_button_anchor
from src.domain.migration.chunking import flatten_to_semantic
from src.domain.migration.tree_cleanup import (
    filter_meaningful,
    is_container_like,
    unwrap_singletons,
)


def group_into_rows(children: list, y_overlap_threshold: float = 0.5) -> list[list]:
    """Group siblings into rows by y-overlap.

    Backward-compat fallback: if no geometry data is present, use document
    order with a Bootstrap-class hint — all children with col-* classes are
    treated as one row; otherwise each child becomes its own (stacked) row.
    """
    if not children:
        return []

    has_geom = any(c.get('h', 0) > 0 for c in children)
    if not has_geom:
        if len(children) > 1 and all(is_likely_column(c) for c in children):
            return [list(children)]
        return [[c] for c in children]

    sorted_kids = sorted(children, key=lambda c: (c.get('y', 0), c.get('x', 0)))

    rows: list[list] = [[sorted_kids[0]]]
    for ch in sorted_kids[1:]:
        current_row = rows[-1]
        # Defensive: use .get() throughout. filter_meaningful already drops
        # `#text` pseudo-children before we get here, but a future schema gap
        # shouldn't crash production — group siblings missing geometry as if
        # they share y=0.
        row_y_min = min(c.get('y', 0) for c in current_row)
        row_y_max = max(c.get('y', 0) + c.get('h', 0) for c in current_row)
        ch_y_min = ch.get('y', 0)
        ch_y_max = ch.get('y', 0) + ch.get('h', 0)

        overlap = max(0, min(row_y_max, ch_y_max) - max(row_y_min, ch_y_min))
        shorter = min(ch.get('h', 0), row_y_max - row_y_min)
        ratio = overlap / shorter if shorter > 0 else 0

        if ratio > y_overlap_threshold:
            current_row.append(ch)
        else:
            rows.append([ch])

    for row in rows:
        row.sort(key=lambda c: c.get('x', 0))
    return rows


def classify_columns_by_geometry(row_children: list, tolerance: float = 0.08) -> str | None:
    """Classify side-by-side columns into a DDC layout from width ratios."""
    if len(row_children) < 2:
        return None

    # Reject overlapping-children rows (not real columns). Real side-by-side
    # columns occupy disjoint x ranges, so the sum of widths is ~equal to the
    # spanning width. When children stack on top of each other (e.g. a video
    # widget's swatch + player chrome) the widths sum well above the span and
    # we'd otherwise misclassify them as `empty-fifty-fifty` with an empty
    # second slot.
    geom_kids = [c for c in row_children if c.get('w', 0) > 0]
    if len(geom_kids) >= 2:
        spanning = (
            max(c['x'] + c['w'] for c in geom_kids)
            - min(c['x'] for c in geom_kids)
        )
        total_w = sum(c['w'] for c in geom_kids)
        if spanning > 0 and total_w > spanning * 1.2:
            return None

    total = sum(c.get('w', 0) for c in row_children)
    if total > 0:
        ratios = [c['w'] / total for c in row_children]
        if len(ratios) == 2:
            r0 = ratios[0]
            if abs(r0 - 0.5) < tolerance:
                return 'empty-fifty-fifty'
            if abs(r0 - 2 / 3) < tolerance:
                return 'empty-66-33'
            if abs(r0 - 1 / 3) < tolerance:
                return 'empty-33-66'
        elif len(ratios) == 3:
            if all(abs(r - 1/3) < tolerance for r in ratios):
                return 'empty-thirds'
        elif len(ratios) == 4:
            if all(abs(r - 0.25) < tolerance for r in ratios):
                return 'empty-fourths'
        elif len(ratios) == 5:
            if all(abs(r - 0.2) < tolerance for r in ratios):
                return 'empty-fifths'
    # Geometry didn't resolve — fall back to Bootstrap col-* classes.
    return classify_columns_by_bootstrap(row_children)


def classify_columns_by_bootstrap(row_children: list) -> str | None:
    cols = [get_bootstrap_col_width(c) for c in row_children]
    if not all(cols):
        return None
    if cols == [6, 6]:
        return 'empty-fifty-fifty'
    if cols == [8, 4]:
        return 'empty-66-33'
    if cols == [4, 8]:
        return 'empty-33-66'
    if len(cols) == 5:
        return 'empty-fifths'
    if cols == [4, 4, 4]:
        return 'empty-thirds'
    if cols == [3, 3, 3, 3]:
        return 'empty-fourths'
    # Approximate fallback for 2-column "main + sidebar" layouts whose widths
    # sum to 12 but miss an exact bucket (e.g. 9/3, 10/2, 7/5). Snap to the
    # nearest two-column DDC layout. Threshold ≥7 for "main", ≤5 for
    # "sidebar" — anything more balanced than that (6/6) was already matched
    # above as empty-fifty-fifty.
    if len(cols) == 2 and sum(cols) == 12:
        a, b = cols
        if a >= 7 and b <= 5:
            return 'empty-66-33'
        if b >= 7 and a <= 5:
            return 'empty-33-66'
    return None


def is_likely_column(node: dict) -> bool:
    """True if the node has any Bootstrap col-* class."""
    return get_bootstrap_col_width(node) is not None


def _row_is_button_only(row_children: list) -> bool:
    """True if every element in the row is a button-only column.

    Side-by-side buttons (e.g. two CTAs inside a button-group wrapper) can
    trigger classify_columns_by_geometry because their wrappers sit at the
    same y-level with a ≈50/50 width ratio, but they're not a structural
    multi-column layout. Flatten each candidate column to semantic elements;
    if every element is a button anchor, the row is a button group that
    should remain empty-one → editorial_chunk produces links widgets.
    """
    for col in row_children:
        flat = flatten_to_semantic(col)
        if not flat or not all(is_button_anchor(el) for el in flat):
            return False
    return True


def discover_sections(node: dict) -> list[tuple[str, list]]:
    """Recursively find DDC sections. Returns list of (layout, slot_nodes)."""
    node = unwrap_singletons(node)
    if not isinstance(node, dict):
        return []

    children = filter_meaningful(node.get('children', []))

    if not children:
        return [('empty-one', [node])]

    if len(children) == 1:
        only = children[0]
        if is_container_like(only):
            return discover_sections(only)
        return [('empty-one', [node])]

    # NB: an earlier design had a "mixed children" branch here that recursed
    # into each container child individually whenever any sibling was
    # semantic (typically a stray <h1>/<h2>). The problem with that branch
    # was that adjacent container children (like col-md-7 + col-md-5 inside
    # a <div class="row"> alongside an <h1>) never got grouped for multi-col
    # classification. group_into_rows below handles the mixed case correctly
    # — the <h1> ends up in its own y-row, and the cols form their own
    # multi-col row — so no special branch is needed.

    rows = group_into_rows(children)

    if len(rows) == 1:
        row = rows[0]
        layout = classify_columns_by_geometry(row)
        if layout:
            if len(row) >= 2 and _row_is_button_only(row):
                return [('empty-one', [node])]
            return [(layout, row)]
        # Symmetry with the multi-row branch below: an unclassifiable row with
        # multiple children shouldn't collapse the parent to empty-one — recurse
        # into each child so genuine sub-sections can still be discovered.
        # Catches the case where a sticky/overlay sibling (e.g. di-action-bar)
        # y-overlaps with the main content div and gets grouped into the same
        # row, blocking classification.
        if len(row) > 1:
            sub_sections: list[tuple[str, list]] = []
            for col in row:
                sub_sections.extend(discover_sections(col))
            if sub_sections and not (
                len(sub_sections) == 1 and sub_sections[0][0] == 'empty-one'
            ):
                return sub_sections
        return [('empty-one', [node])]

    sections: list[tuple[str, list]] = []
    for row in rows:
        if len(row) == 1:
            sections.extend(discover_sections(row[0]))
        else:
            layout = classify_columns_by_geometry(row)
            if layout:
                if len(row) >= 2 and _row_is_button_only(row):
                    sections.append(('empty-one', [node]))
                else:
                    sections.append((layout, row))
            else:
                for col in row:
                    sections.extend(discover_sections(col))

    # Merge consecutive empty-one runs into single sections so stacked
    # editorial content (heading → image → text → button) within the same
    # parent container stays together. Multi-column sections (empty-fifty-
    # fifty, empty-thirds, etc.) break the merge run naturally.
    if len(sections) > 1:
        merged: list[tuple[str, list]] = []
        idx = 0
        while idx < len(sections):
            layout, slot_nodes = sections[idx]
            if layout != 'empty-one':
                merged.append((layout, slot_nodes))
                idx += 1
                continue
            run_end = idx + 1
            while run_end < len(sections) and sections[run_end][0] == 'empty-one':
                run_end += 1
            if run_end - idx == 1:
                merged.append((layout, slot_nodes))
            else:
                run_nodes = []
                for j in range(idx, run_end):
                    run_nodes.extend(sections[j][1])
                batch_parent = {
                    'tag': 'div', 'children': run_nodes,
                    'text': '', 'cls': '',
                }
                merged.append(('empty-one', [batch_parent]))
            idx = run_end
        sections = merged

    if len(sections) == 1 and sections[0][0] == 'empty-one' and not _has_grid_descendants(node):
        return [('empty-one', [node])]

    return sections


def _has_grid_descendants(node: dict) -> bool:
    """Check if a node tree contains any row/col Bootstrap grid patterns.

    Prevents discover_sections from collapsing a tree that contains
    multi-column layouts at deeper levels even when the immediate
    children all resolved to a single merged empty-one.
    """
    if not isinstance(node, dict):
        return False
    cls = (' ' + (node.get('cls') or '') + ' ').lower()
    if ' row ' in cls:
        col_children = [
            c for c in node.get('children', [])
            if isinstance(c, dict) and is_likely_column(c)
        ]
        if len(col_children) >= 2:
            return True
    return any(_has_grid_descendants(c) for c in node.get('children', []))
