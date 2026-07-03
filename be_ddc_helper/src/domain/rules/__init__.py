from pathlib import Path

_RULES_FILE = Path(__file__).parent / "planning_rules.md"


def load_rules() -> str:
    return _RULES_FILE.read_text(encoding="utf-8")
