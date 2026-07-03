"""Pydantic DTOs for the /execute endpoint.

Lives in the inbound HTTP layer (Pydantic + the request/response contract are
HTTP-shaped). Split out from `execute_router.py` so the application-layer
`MigrationExecutor` can import the request/response types without creating a
circular import back into the router.
"""

from pydantic import BaseModel, model_validator


class ButtonDTO(BaseModel):
    text: str
    href: str
    style: str = "primary"   # primary | secondary | outline
    target: str = "_self"    # _self | _top | _blank
    link_class: str = ""     # DDC-specific class marker (e.g. "BLANK") — defaults to empty


class ColumnWidgetDTO(BaseModel):
    widget_type: str                 # "content" | "image" | "links"
    html: str | None = None          # HTML for content widgets
    raw_html: str | None = None      # LLM sometimes outputs this — normalised below
    source_url: str | None = None    # original image URL for image widgets
    buttons: list[ButtonDTO] = []    # button configs for links widgets

    @model_validator(mode="after")
    def _normalise(self) -> "ColumnWidgetDTO":
        # Accept raw_html as a fallback for html (LLM sometimes invents the field name).
        if self.html is None and self.raw_html:
            self.html = self.raw_html
        return self


class SectionPlanItemDTO(BaseModel):
    section_type: str
    position: int
    intent: str
    # One inner list per DDC column slot; each inner list holds N stacked widgets.
    slots: list[list[ColumnWidgetDTO]] = []


class ExecuteRequest(BaseModel):
    dealer_id: str
    page_alias: str
    page_title: str
    section_plan: list[SectionPlanItemDTO]


class ExecuteResponse(BaseModel):
    ok: bool
    page_alias: str = ""
    warnings: list[str] = []
    error: str | None = None
