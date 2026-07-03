"""Image-split node — LLM-driven widget-level structural review.

After `build_node` runs `editorial_chunk`, some content widgets carry
residual `<img>` tags that the deterministic chunker did not promote to
standalone image widgets (because the wrapping pattern wasn't recognized).
This node collects those residual cases, asks the LLM per-image whether
each should be promoted, and applies splits to the widget list.

Architectural pattern: same shape as `chrome_review` — deterministic flags
candidates, single batched LLM call resolves them with a binary verdict.
The LLM is never asked to pick from N options; only yes/no on each candidate.
On any LLM failure, the call defaults to all-False (no widget changes), so
this node is safe to enable: it can only improve or no-op, never regress.
"""

import re
from typing import Awaitable, Callable

from src.domain.models import MigrationState
from src.ports.outbound import LLMPort

Progress = Callable[[str], Awaitable[None]]

# One tuple per content-widget candidate carrying at least one <img>.
Candidate = tuple[int, int, int, str]

_IMG_RE = re.compile(r"<img\b[^>]*?>", re.IGNORECASE)
_SRC_RE = re.compile(r"""src=['"]([^'"]+)['"]""", re.IGNORECASE)

# Tags whose orphan halves we tidy after slicing.
_ORPHAN_OPEN_RE = re.compile(r"<(p|div|figure|span|a|li)\b[^>]*>\s*$", re.IGNORECASE)
_ORPHAN_CLOSE_RE = re.compile(r"^\s*</(p|div|figure|span|a|li)>", re.IGNORECASE)
_EMPTY_WRAPPER_RE = re.compile(r"<(p|div|figure|span|a|li)\b[^>]*>\s*</\1>", re.IGNORECASE)


# ── Node factory ─────────────────────────────────────────────────────────────


def build_image_split_node(
    llm: LLMPort | None,
    progress: Progress | None = None,
    enabled: bool = True,
):
    async def _progress(msg: str) -> None:
        if progress is not None:
            await progress(msg)

    async def image_split(state: MigrationState) -> dict:
        det_plan = state["det_plan"]
        if not enabled or llm is None:
            return {"det_plan": det_plan}

        candidates = _collect_candidates(det_plan)
        if not candidates:
            return {"det_plan": det_plan}

        await _progress("AI is checking for embedded images")
        verdicts = await _classify(llm, candidates)
        if verdicts is None:
            await _progress("⚠ Image split failed — keeping widgets unchanged")
            return {"det_plan": det_plan}

        _apply_splits(det_plan, candidates, verdicts)
        return {"det_plan": det_plan}

    return image_split


# ── Pass 1: candidate collection ─────────────────────────────────────────────


def _collect_candidates(det_plan: list[dict]) -> list[Candidate]:
    """Content widgets whose HTML still contains at least one <img>."""
    out: list[Candidate] = []
    for s_idx, section in enumerate(det_plan):
        for sl_idx, slot in enumerate(section.get("slots", [])):
            for w_idx, widget in enumerate(slot):
                if widget.get("type") != "content":
                    continue
                html = widget.get("html") or ""
                if _IMG_RE.search(html):
                    out.append((s_idx, sl_idx, w_idx, html))
    return out


# ── LLM invocation ───────────────────────────────────────────────────────────


async def _classify(
    llm: LLMPort, candidates: list[Candidate]
) -> list[list[bool]] | None:
    """Run the batched LLM call. Returns per-candidate per-image verdicts, or
    None if the port call raised (caller renders a warning and no-ops).
    """
    items = [{"id": str(i), "html": html} for i, (_, _, _, html) in enumerate(candidates)]
    try:
        return await llm.classify_image_splits(items)
    except Exception:
        return None


# ── Pass 2: apply splits to slots ────────────────────────────────────────────


def _apply_splits(
    det_plan: list[dict],
    candidates: list[Candidate],
    verdicts: list[list[bool]],
) -> None:
    """Mutate det_plan in place. Widgets in the same slot are processed in
    reverse widget-index order so insertions don't shift earlier indices."""
    by_slot = _group_by_slot(candidates, verdicts)
    for (s_idx, sl_idx), entries in by_slot.items():
        entries.sort(key=lambda e: e[0], reverse=True)
        slot = det_plan[s_idx]["slots"][sl_idx]
        for w_idx, html, vlist in entries:
            new_widgets = _split_widget(html, vlist)
            if len(new_widgets) > 1:
                slot[w_idx:w_idx + 1] = new_widgets


def _group_by_slot(
    candidates: list[Candidate], verdicts: list[list[bool]]
) -> dict[tuple[int, int], list[tuple[int, str, list[bool]]]]:
    """{(section_idx, slot_idx): [(widget_idx, html, per_image_verdicts), ...]}"""
    out: dict[tuple[int, int], list[tuple[int, str, list[bool]]]] = {}
    for i, (s_idx, sl_idx, w_idx, html) in enumerate(candidates):
        vlist = verdicts[i] if i < len(verdicts) else []
        out.setdefault((s_idx, sl_idx), []).append((w_idx, html, vlist))
    return out


# ── HTML slicing ─────────────────────────────────────────────────────────────


def _split_widget(html: str, verdicts: list[bool]) -> list[dict]:
    """Slice a content widget's HTML into multiple algo-shape widgets based
    on per-<img> promotion verdicts.

    Returns the widget list in algo internal format:
      {type: 'content', html: ..., preview: ...}
      {type: 'image',   url: ...}

    If no img is promoted, returns the original widget unchanged (single
    entry). Empty content slices are dropped. Orphan tag halves (e.g. a
    trailing `<p>` left dangling after extracting the only `<img>` it
    contained) are cleaned up before emitting.
    """
    matches = list(_IMG_RE.finditer(html))
    if not matches or not any(verdicts):
        return [_content_widget(html)]

    widgets = _emit_slices(html, matches, verdicts)
    return widgets or [_content_widget(html)]


def _emit_slices(
    html: str, matches: list[re.Match], verdicts: list[bool]
) -> list[dict]:
    widgets: list[dict] = []
    cursor = 0
    for i, m in enumerate(matches):
        promote = verdicts[i] if i < len(verdicts) else False
        if not promote:
            continue

        before = _clean_slice(html[cursor:m.start()])
        if before:
            widgets.append(_content_widget(before))

        image = _image_widget_from_match(m)
        if image is not None:
            widgets.append(image)

        cursor = m.end()

    tail = _clean_slice(html[cursor:])
    if tail:
        widgets.append(_content_widget(tail))
    return widgets


def _content_widget(html: str) -> dict:
    return {"type": "content", "html": html, "preview": _preview(html)}


def _image_widget_from_match(m: re.Match) -> dict | None:
    src_match = _SRC_RE.search(m.group(0))
    src = src_match.group(1) if src_match else ""
    return {"type": "image", "url": src} if src else None


def _clean_slice(fragment: str) -> str:
    """Tidy a sliced HTML fragment: drop leading orphan close tags, trailing
    unclosed open tags, and any empty wrappers left by the slice."""
    s = fragment.strip()
    s = _strip_leading_orphan_close(s)
    s = _strip_trailing_open(s)
    return _collapse_empty_wrappers(s)


def _strip_leading_orphan_close(s: str) -> str:
    while True:
        m = _ORPHAN_CLOSE_RE.match(s)
        if not m:
            return s
        s = s[m.end():].lstrip()


def _strip_trailing_open(s: str) -> str:
    while True:
        m = _ORPHAN_OPEN_RE.search(s)
        if not m:
            return s
        s = s[:m.start()].rstrip()


def _collapse_empty_wrappers(s: str) -> str:
    prev = None
    while prev != s:
        prev = s
        s = _EMPTY_WRAPPER_RE.sub("", s).strip()
    return s


def _preview(html: str, max_len: int = 70) -> str:
    """Cheap text preview — strip tags, trim, cap length."""
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:max_len]
