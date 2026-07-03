"""Pytest configuration.

Make `src.*` importable from tests. Pytest normally does this automatically
when there's a conftest.py at the tests root, but only if the parent directory
is on sys.path — we prepend it explicitly so `uv run pytest` works from
either the repo root or the be_ddc_helper subproject.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
