from pydantic import BaseModel


class ColumnWidget(BaseModel):
    """A single widget within one DDC slot.

    widget_type values:
      - "content"      — HTML chunk; uses `html`
      - "image"        — image; uses `source_url` (uploaded to media library)
      - "form"         — Contact form marker; no payload (DDC configures)
      - "contact_info" — dealer identity marker; no payload (DDC configures)
      - "hours"        — business hours marker; no payload (DDC configures)
      - "links"        — buttons; payload lives in the execute-side DTO
    """
    widget_type: str
    html: str | None = None         # HTML to inject into a content widget
    source_url: str | None = None   # Original image URL to upload (image only)
    buttons: list[dict] | None = None  # Button DTOs for `links` widgets only


class SectionPlanItem(BaseModel):
    section_type: str
    position: int
    intent: str
    # One inner list per DDC column slot; each inner list holds N stacked widgets.
    # e.g. empty-fifty-fifty → slots[0] = [content_widget], slots[1] = [image_widget]
    # e.g. empty-one         → slots[0] = [widget1, widget2, widget3]
    slots: list[list[ColumnWidget]] = []


class SectionPlan(BaseModel):
    items: list[SectionPlanItem]
