"""Golden tests for the deterministic migration algorithm.

Each test loads a real DOM skeleton captured from `/analyze` (frozen in
`tests/fixtures/skeleton_*.json`) and asserts that running `migrate()` on it
produces exactly the frozen expected output (`*_expected.json`).

Purpose: this is the safety net for Phase 8 of the backend refactor SDD
(splitting `deterministic_migrate.py` into `domain/migration/*` modules).
Any predicate, threshold, or tie-breaker drift during the split makes one of
these tests go red.

To regenerate the expected outputs after a *deliberate* algorithm change:
capture a fresh DOM skeleton (e.g. `print(body.dom_skeleton)` inside
`analyze_router.py` during a real `/analyze` call, or save the request body
from the browser's network tab), replace one of `skeleton_{small,medium,large}.json`,
then run migrate() on it and freeze the sanitized output as the matching
`*_expected.json`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.domain.deterministic_migrate import migrate

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _sanitize_plan(plan: list[dict]) -> list[dict]:
    """Drop `_slot_nodes` — raw DOM refs used only by the analyze router for
    LLM fallback. Not stable across runs (dict identity) and not meaningful
    for behavior equality."""
    return [{k: v for k, v in section.items() if k != "_slot_nodes"} for section in plan]


def _load(name: str) -> dict | list:
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize(
    "size",
    ["small", "medium", "large"],
    ids=["small", "medium", "large"],
)
def test_migrate_golden(size: str) -> None:
    skeleton = _load(f"skeleton_{size}.json")
    expected = _load(f"skeleton_{size}_expected.json")
    actual = _sanitize_plan(migrate(skeleton))
    assert actual == expected, (
        f"migrate() output drifted from the golden {size} fixture. "
        f"If this drift is intentional, regenerate the matching "
        f"skeleton_{size}_expected.json (see module docstring)."
    )
