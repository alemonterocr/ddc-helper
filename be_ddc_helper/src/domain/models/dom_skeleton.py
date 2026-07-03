from __future__ import annotations

from pydantic import BaseModel


class DOMNode(BaseModel):
    tag: str
    cls: str = ""
    style: str = ""     # layout-relevant inline styles (display, width, flex, grid)
    bg: str = ""        # computed background-color, only when different from parent
    text: str = ""
    src: str = ""       # resolved absolute URL, present only on <img> elements
    href: str = ""      # resolved absolute URL, present only on <a> elements

    # ── Geometry (from getBoundingClientRect, rounded to int) ─────────────────
    x: int = 0
    y: int = 0
    w: int = 0          # width in px
    h: int = 0          # height in px

    # ── Extra computed-style signals ──────────────────────────────────────────
    bgImage: bool = False       # True when background-image is set (not 'none')
    bgImageSrc: str = ""        # resolved absolute URL of the background-image, query-string stripped
    fontSize: int = 0           # computed font-size in px

    children: list[DOMNode] = []


DOMNode.model_rebuild()


class DOMSkeleton(BaseModel):
    url: str
    title: str
    structure: DOMNode
    raw_html: str = ""
