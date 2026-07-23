"""Unit tests for staff-page noise stripping."""

from src.application.staff_migration.html_clean import strip_noise


def test_removes_script_style_svg_and_head_junk():
    html = (
        "<html><head><meta charset='utf-8'><link rel='stylesheet' href='x.css'>"
        "<style>.a{color:red}</style></head><body>"
        "<script>var x=1</script>"
        "<svg><path d='M0 0'/></svg>"
        "<div class='staff'><h3>Jane Doe</h3><p>Sales</p></div>"
        "</body></html>"
    )
    out = strip_noise(html)
    assert "var x=1" not in out
    assert ".a{color:red}" not in out
    assert "<svg" not in out and "<path" not in out
    assert "x.css" not in out
    # real content survives
    assert "Jane Doe" in out and "Sales" in out
    assert "class=\"staff\"" in out or "class='staff'" in out


def test_strips_inline_style_attributes_but_keeps_class_and_href():
    html = (
        '<div class="card" style="--tw-x:0;color:red;padding:40px">'
        '<a href="/staff/jane.htm">Jane</a></div>'
    )
    out = strip_noise(html)
    assert "style=" not in out
    assert "--tw-x" not in out
    assert 'href="/staff/jane.htm"' in out   # link target preserved
    assert "card" in out                      # class preserved (structural signal)
    assert "Jane" in out


def test_removes_html_comments():
    out = strip_noise("<div><!-- tracking pixel --><p>Bob</p></div>")
    assert "tracking pixel" not in out
    assert "Bob" in out


def test_reduces_size_on_noisy_input():
    noisy = (
        "<html><body>"
        + "<style>" + ("x" * 5000) + "</style>"
        + "<script>" + ("y" * 5000) + "</script>"
        + "<div class='staff'><h3>Ana</h3></div>"
        + "</body></html>"
    )
    out = strip_noise(noisy)
    assert len(out) < len(noisy) / 2   # noise gone
    assert "Ana" in out


def test_empty_and_malformed_are_safe():
    assert strip_noise("") == ""
    assert strip_noise("   ") == "   "
    # not valid HTML — should not raise, content preserved
    assert "hello" in strip_noise("hello <div unclosed")
