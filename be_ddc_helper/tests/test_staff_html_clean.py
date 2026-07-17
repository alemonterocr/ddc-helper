"""Unit tests for staff-page noise stripping, chunking, and dedup."""

from src.application.staff_migration.html_clean import (
    chunk_html,
    dedup_staff,
    strip_noise,
)


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


# ── chunk_html ────────────────────────────────────────────────────────────────


def test_small_html_is_single_chunk():
    assert chunk_html("<div>small</div>") == ["<div>small</div>"]


def test_large_html_splits_with_overlap_and_full_coverage():
    html = "".join(f"<div>staff-{i}</div>" for i in range(4000))  # well over 24k chars
    chunks = chunk_html(html, max_chars=24000, overlap=2000)
    assert len(chunks) > 1
    # every chunk within budget (+ small nudge to next '>')
    assert all(len(c) <= 24000 + 500 for c in chunks)
    # first and last content present across the set
    assert any("staff-0<" in c or "staff-0" in c for c in chunks)
    assert any("staff-3999" in c for c in chunks)
    # consecutive chunks overlap (end of one reappears at start of next)
    assert chunks[0][-100:] in chunks[1] or chunks[1].startswith(chunks[0][-2000:][:50])


# ── dedup_staff ───────────────────────────────────────────────────────────────


def test_dedup_by_email_case_insensitive():
    members = [
        {"name": "Jane Doe", "department": "Sales", "email": "Jane@x.com"},
        {"name": "Jane D.", "department": "Sales", "email": "jane@x.com"},  # dup email
        {"name": "Bob Roe", "department": "Service", "email": "bob@x.com"},
    ]
    out = dedup_staff(members)
    assert [m["name"] for m in out] == ["Jane Doe", "Bob Roe"]


def test_dedup_falls_back_to_name_dept_when_no_email():
    members = [
        {"name": "Ana", "department": "Parts"},
        {"name": "ana", "department": "parts"},   # dup (case-insensitive)
        {"name": "Ana", "department": "Sales"},    # different dept → kept
    ]
    out = dedup_staff(members)
    assert len(out) == 2


def test_dedup_drops_keyless_rows():
    assert dedup_staff([{"department": "Sales"}, {}, "junk"]) == []
