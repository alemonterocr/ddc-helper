import json
from pathlib import Path

_CATALOG_FILE = Path(__file__).parent / "ddc_catalog.json"
_WIDGET_CATALOG_FILE = Path(__file__).parent / "widget_catalog.json"


def load_catalog() -> list[dict]:
    return json.loads(_CATALOG_FILE.read_text(encoding="utf-8"))


def load_widget_catalog() -> list[dict]:
    return json.loads(_WIDGET_CATALOG_FILE.read_text(encoding="utf-8"))
