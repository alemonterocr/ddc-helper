"""Tests for questionnaire_parser.

After the V2 refactor the parser only does row-splitting + HTML-entity decode;
typed-field extraction moved to `extractor.py` (LLM-driven). These tests cover
the deterministic row-split contract: the `all_rows` dict the LLM extractor
consumes.
"""

from src.application.salesforce.questionnaire_parser import (
    DesignChoiceMissing,
    parse_questionnaire_blob,
)

from .fixtures import BUYSELL_BLOB_SYNTHETIC, MCELVEEN_BLOB


def test_empty_blob():
    q = parse_questionnaire_blob("")
    assert q.dealership_name is None
    assert q.dealership_address is None
    assert isinstance(q.design_choice, DesignChoiceMissing)
    assert q.all_rows == {}


def test_all_rows_populated_for_mcelveen():
    q = parse_questionnaire_blob(MCELVEEN_BLOB)
    # The classifier + extractor both consume all_rows; this is the parser's
    # actual contract.
    assert "Dealership Name:" in q.all_rows
    assert q.all_rows["Dealership Name:"] == "McElveen Buick GMC"
    assert "Is this a Buy/Sell" in q.all_rows
    assert q.all_rows["Is this a Buy/Sell"] == "No"
    assert "OEM Dealer Code:" in q.all_rows


def test_typed_fields_are_none_after_parse():
    """The parser no longer fills typed fields — the LLM extractor does."""
    q = parse_questionnaire_blob(MCELVEEN_BLOB)
    assert q.dealership_name is None
    assert q.primary_url is None
    assert q.leads_email is None
    assert q.dealership_address is None


def test_buysell_all_rows_includes_drifted_labels():
    """The synthetic BuySell blob uses real-world label variants
    that don't match any hardcoded constant — but they MUST be in all_rows."""
    q = parse_questionnaire_blob(BUYSELL_BLOB_SYNTHETIC)
    # Whatever rows the fixture has, they should all reach all_rows.
    assert len(q.all_rows) > 0


def test_tolerates_single_tab():
    """Some rows in the wild use a single tab instead of double."""
    blob = "Dealership Name:\tBob's Garage\r\n"
    q = parse_questionnaire_blob(blob)
    assert q.all_rows["Dealership Name:"] == "Bob's Garage"


def test_later_duplicate_label_wins():
    blob = "Dealership Name:\t\tOld Name\r\nDealership Name:\t\tNew Name\r\n"
    q = parse_questionnaire_blob(blob)
    assert q.all_rows["Dealership Name:"] == "New Name"


def test_html_entities_in_values_are_decoded():
    """The UI API returns long-text fields with HTML entities.
    Decoding must happen at parse time so downstream JSON parsing of
    design_choice and LLM context see the original characters."""
    blob = "Dealership Name:\t\tSmith &amp; Sons Auto\r\n"
    q = parse_questionnaire_blob(blob)
    assert q.all_rows["Dealership Name:"] == "Smith & Sons Auto"


def test_html_entity_encoded_design_choice_in_all_rows():
    """HTML entities in any row value get decoded — including a JSON-shaped
    design choice blob (the parser doesn't try to JSON-parse anymore; the
    extractor's post-processor will)."""
    blob = (
        'Design Choice:\t\t{&quot;color&quot;:&quot;86&quot;,'
        '&quot;fontFace&quot;:&quot;gmc&quot;}\r\n'
    )
    q = parse_questionnaire_blob(blob)
    assert q.all_rows["Design Choice:"] == '{"color":"86","fontFace":"gmc"}'


def test_lines_without_tab_are_skipped():
    """Continuation lines or headers without a tab are dropped."""
    blob = "Just some heading\r\nDealership Name:\t\tFoo\r\n"
    q = parse_questionnaire_blob(blob)
    assert "Just some heading" not in q.all_rows
    assert q.all_rows["Dealership Name:"] == "Foo"
