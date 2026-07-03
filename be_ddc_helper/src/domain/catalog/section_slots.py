# DDC slot key computation.
#
# Each section occupies one "row" in the DDC page grid.
# Row 1 is always the page-title slot ("1-1").
# Content sections start at row 2, so a section at position P (0-indexed)
# maps to row P+2.
#
# The slot key formula is:  {row}-1-1-{col}-1
# where col is 1-indexed up to the column count of the section type.
#
# Column counts are confirmed from HAR analysis (savePageExample.har):
#   position 0 → row 2 → "2-1-1-1-1"          (empty-one,          1 col)
#   position 1 → row 3 → "3-1-1-1-1","3-1-1-2-1" (2-col sections,  2 cols)
#   position 5 → row 7 → "7-1-1-1-1".."7-1-1-5-1" (empty-fifths,   5 cols)

SECTION_COLUMN_COUNT: dict[str, int] = {
    "empty-one": 1,
    "empty-fifty-fifty": 2,
    "empty-66-33": 2,
    "empty-33-66": 2,
    "empty-thirds": 3,
    "empty-fourths": 4,
    "empty-fifths": 5,
    "map-hours": 0,  # pre-wired — no widget injection needed
}


def get_section_slots(section_type: str, position: int) -> list[str]:
    """Return the ordered DDC slot keys for a section at the given 0-indexed position.

    Returns an empty list for pre-wired sections (column count = 0).
    """
    row = position + 2
    col_count = SECTION_COLUMN_COUNT.get(section_type, 0)
    return [f"{row}-1-1-{col}-1" for col in range(1, col_count + 1)]
