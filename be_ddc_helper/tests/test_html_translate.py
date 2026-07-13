"""Unit tests for text-node HTML translation and id-matched reconstruction."""

import pytest

from src.adapters.outbound.anthropic.anthropic_llm_adapter import _segments_in_order
from src.application.translate_pages.html_translate import translate_widget_html


async def _suffix(segments):
    """Fake translator: append ' ES' to each fragment (same length/order)."""
    return [f"{s} ES" for s in segments]


async def _upper(segments):
    return [s.upper() for s in segments]


@pytest.mark.asyncio
async def test_translates_text_but_preserves_markup():
    html = '<p class="x" style="color:red">Hello <a href="/foo">world</a></p>'
    out, count, untranslated = await translate_widget_html(html, _suffix)
    assert count == 2 and untranslated == 0
    assert 'class="x"' in out and 'style="color:red"' in out and 'href="/foo"' in out
    assert "Hello ES" in out and "world ES" in out


@pytest.mark.asyncio
async def test_preserves_surrounding_whitespace():
    out, _, _ = await translate_widget_html("<p>  Hello  </p>", _upper)
    assert out == "<p>  HELLO  </p>"


@pytest.mark.asyncio
async def test_skips_script_and_style_text():
    html = "<div><style>.a{color:red}</style><script>var x=1</script><p>Hi</p></div>"
    seen: list[str] = []

    async def capture(segments):
        seen.extend(segments)
        return [f"{s} ES" for s in segments]

    out, count, _ = await translate_widget_html(html, capture)
    assert seen == ["Hi"]  # style/script text never sent
    assert count == 1 and ".a{color:red}" in out and "var x=1" in out


@pytest.mark.asyncio
async def test_no_text_returns_input_unchanged():
    out, count, untranslated = await translate_widget_html('<img src="/a.jpg"/>', _suffix)
    assert count == 0 and untranslated == 0 and "/a.jpg" in out


@pytest.mark.asyncio
async def test_wrong_length_batch_keeps_english_without_misaligning():
    """A translator that returns the wrong count must not raise or shift
    positions — the whole batch stays English and is reported."""
    async def drop_one(segments):
        return segments[:-1]  # nondeterministic-style short return

    out, count, untranslated = await translate_widget_html("<p>a</p><p>b</p>", drop_one)
    assert count == 2 and untranslated == 2      # both kept English, none lost
    assert "a" in out and "b" in out             # original text intact, aligned


@pytest.mark.asyncio
async def test_translator_exception_keeps_english():
    async def boom(segments):
        raise RuntimeError("api down")

    out, count, untranslated = await translate_widget_html("<p>hi</p>", boom)
    assert count == 1 and untranslated == 1 and "hi" in out  # no crash


@pytest.mark.asyncio
async def test_batches_large_segment_counts():
    html = "".join(f"<p>t{i}</p>" for i in range(45))
    calls: list[int] = []

    async def batched(segments):
        calls.append(len(segments))
        return [f"{s} ES" for s in segments]

    out, count, _ = await translate_widget_html(html, batched)
    assert count == 45
    assert calls == [20, 20, 5]  # chunked at _BATCH_SIZE
    assert "t0 ES" in out and "t44 ES" in out


# ── id-matched reconstruction (the fix for count/order nondeterminism) ────────


def test_segments_in_order_matches_by_id_ignoring_order():
    items = [{"id": "1", "es": "uno"}, {"id": "0", "es": "cero"}]
    assert _segments_in_order(items, ["zero", "one"]) == ["cero", "uno"]


def test_segments_in_order_fills_dropped_id_with_original():
    # model dropped id "1" — keep its English, don't shift
    items = [{"id": "0", "es": "cero"}, {"id": "2", "es": "dos"}]
    assert _segments_in_order(items, ["zero", "one", "two"]) == ["cero", "one", "dos"]


def test_segments_in_order_empty_on_no_usable_items():
    assert _segments_in_order([], ["a", "b"]) == []
    assert _segments_in_order([{"nope": 1}], ["a", "b"]) == []
