from src.domain.translations.glossary_search import glossary_search


def test_empty_input_returns_empty_dict():
    assert glossary_search([]) == {}


def test_exact_match_is_case_insensitive():
    # "Car" is in the bundled glossary; verify multiple casings hit.
    result = glossary_search(["Car", "car", "CAR"])
    assert all(v for v in result.values()), result


def test_whitespace_tolerance():
    result = glossary_search(["  Car  "])
    assert result["  Car  "] is not None


def test_miss_returns_none():
    result = glossary_search(["zzzzznotaglossaryword"])
    assert result == {"zzzzznotaglossaryword": None}


def test_keys_preserve_original_casing():
    result = glossary_search(["Car"])
    assert "Car" in result


def test_mixed_hits_and_misses():
    result = glossary_search(["Car", "zzzzznotaglossaryword"])
    assert result["Car"] is not None
    assert result["zzzzznotaglossaryword"] is None
