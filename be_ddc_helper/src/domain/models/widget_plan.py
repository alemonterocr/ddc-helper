from pydantic import BaseModel


class WidgetPlanItem(BaseModel):
    section_type: str  # matches a sectionName in the section plan
    column: int        # 1-indexed column within the section
    portlet: str       # e.g. "v9.widgets.content.default.v1"
    widget_type: str   # e.g. "Content", "Image"


class WidgetPlan(BaseModel):
    items: list[WidgetPlanItem]
