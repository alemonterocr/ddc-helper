"""Loads the bundled EN→ES glossary CSV once and caches it.

Prefers the MexicanSpanish column when non-empty; falls back to Spanish.
Drops rows where the resolved ES is empty or looks invalid (e.g. "<<").

The "Directions" ambiguity (Ubicación vs Indicaciones) is intentionally not
encoded here — the prompt body carries the context-dependent rule directly,
since a flat dictionary can't pick between two valid ES options.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


_CSV_PATH = Path(__file__).parent / "glossary_es.csv"
_AMBIGUOUS_EN = {"directions"}  # handled inline in the prompt body


@dataclass(frozen=True)
class GlossaryEntry:
    en: str
    es: str


@lru_cache(maxsize=1)
def get_glossary() -> tuple[GlossaryEntry, ...]:
    entries: list[GlossaryEntry] = []
    with _CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            en = (row.get("English") or "").strip()
            mx = (row.get("MexicanSpanish") or "").strip()
            es = mx if mx else (row.get("Spanish") or "").strip()

            if not en or not es:
                continue
            if es in {"<<", "<"}:
                continue
            if en.lower() in _AMBIGUOUS_EN:
                continue

            entries.append(GlossaryEntry(en=en, es=es))

    return tuple(entries)


def format_glossary_table(entries: tuple[GlossaryEntry, ...]) -> str:
    """Render the glossary as a compact two-column block for the prompt."""
    return "\n".join(f"  {e.en} → {e.es}" for e in entries)
