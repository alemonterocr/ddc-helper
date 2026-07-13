"""Unit tests for page widget extraction (bs4)."""

from src.application.translate_pages.widget_extract import extract_widgets

_EN = """
<html><body>
  <div class="header">chrome</div>
  <div class="main">
    <div class="text-content-container editable content"
         id="SITEBUILDER_ALE_MONTERO_1:content1-editable"><p>Hello</p></div>
    <div class="content editable-raw-content"
         id="SITEBUILDER_ALE_MONTERO_1:content2-editable"><p>Raw <b>bold</b></p></div>
    <div class="not-editable" id="ignore-me">skip</div>
  </div>
</body></html>
"""

_ES = """
<html><body>
  <div class="main">
    <div class="text-content-container editable content"
         id="SITEBUILDER_ALE_MONTERO_1:content1-editable"><p>Hola</p></div>
  </div>
</body></html>
"""


def test_extracts_content_and_raw_widgets():
    widgets = extract_widgets(_EN, _ES)
    assert len(widgets) == 2
    by_id = {w["window_id"]: w for w in widgets}

    content = by_id["SITEBUILDER_ALE_MONTERO_1:content1-editable"]
    assert content["widget_type"] == "content"
    assert content["en_html"] == "<p>Hello</p>"
    assert content["es_html"] == "<p>Hola</p>"

    raw = by_id["SITEBUILDER_ALE_MONTERO_1:content2-editable"]
    assert raw["widget_type"] == "raw"
    assert raw["en_html"] == "<p>Raw <b>bold</b></p>"


def test_window_id_keeps_editable_suffix():
    widgets = extract_widgets(_EN, _ES)
    assert all(w["window_id"].endswith("-editable") for w in widgets)


def test_missing_es_widget_yields_empty_es_html():
    widgets = extract_widgets(_EN, _ES)
    raw = next(w for w in widgets if w["widget_type"] == "raw")
    # content2 is absent from the es render
    assert raw["es_html"] == ""


def test_non_editable_divs_ignored():
    widgets = extract_widgets(_EN, _ES)
    assert all(w["window_id"] != "ignore-me" for w in widgets)


def test_inner_html_round_trip_stable():
    html = (
        '<div class="main">'
        '<div class="text-content-container editable content" id="x:c1-editable">'
        '<p>Keep <a href="/foo">link</a> and [PRICE]</p></div></div>'
    )
    widgets = extract_widgets(html, html)
    assert widgets[0]["en_html"] == '<p>Keep <a href="/foo">link</a> and [PRICE]</p>'


def test_no_main_div_returns_empty():
    assert extract_widgets("<html><body>no main</body></html>", "<html></html>") == []
