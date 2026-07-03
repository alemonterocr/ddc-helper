"""Tests for smart_title_case."""

from src.application.salesforce.title_case import smart_title_case


def test_uppercase_address_normalises():
    assert (
        smart_title_case("117 FARMINGTON ROAD, SUMMERVILLE, SC 29486")
        == "117 Farmington Road, Summerville, SC 29486"
    )


def test_state_code_preserved():
    assert smart_title_case("Charleston, sc 29486") == "Charleston, SC 29486"
    # Already-cased state codes stay capital.
    assert smart_title_case("Charleston, SC 29486") == "Charleston, SC 29486"


def test_override_preserved_at_any_length():
    assert smart_title_case("gm dealer in usa") == "GM Dealer In USA"


def test_empty_input():
    assert smart_title_case("") == ""


def test_mixed_punctuation_preserved():
    assert (
        smart_title_case("123 main st, anywhere, usa")
        == "123 Main St, Anywhere, USA"
    )


def test_apostrophes_handled():
    # "o'connor" should become "O'connor" - apostrophe is part of the token.
    # We don't try to handle every English casing rule; "good enough" wins.
    assert smart_title_case("o'connor blvd") == "O'connor Blvd"


def test_long_lowercase_preserved_words_not_uppercased():
    # 4+ char lowercase tokens should NOT be uppercased (only the override set or short caps).
    assert smart_title_case("road street avenue") == "Road Street Avenue"
