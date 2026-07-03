"""Pure widget-construction helpers for the execute flow.

Every function here is a data transform — no IO, no bridge, no async. The
execute orchestrator (and the inbound router for the validation check) imports
from this module; nothing here imports back into the inbound layer.

DDC widget shape reference: see `WIDGET-SPEC.md` in `src/domain/`.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.adapters.inbound.http.execute_dtos import ColumnWidgetDTO


# Seed groups map: row 1 is always the page-title portlet pre-wired by DDC on page creation.
PAGE_TITLE_PORTLET = "v9.widgets.content.page-title.v1"

# Portlet lookup by the widget_type string the LLM emits.
PORTLET_BY_WIDGET_TYPE: dict[str, str] = {
    "content": "v9.widgets.content.default.v1",
    "image":   "v9.widgets.image.default.v1",
    "links":   "v9.widgets.links.list.v1",
    "form":         "v9.widgets.contact.form.v1",
    "contact_info": "v9.widgets.contact.info.v1",
    "hours":        "ws-hours",          # legacy portlet name — no v9 equivalent
}

# DDC's JSON "type" field (maps to Java widgetType) — required when windowId is ""
# so DDC can auto-generate a windowId via SavePage.getWindowId().
DDC_TYPE_BY_WIDGET_TYPE: dict[str, str] = {
    "content":      "Content",
    "image":        "Image",
    "links":        "Links",
    "form":         "Contact",
    "contact_info": "Contact",
    "hours":        "Hours",
}

# hiddenDeviceDefaults required for new (non-page-title) widgets.
HIDDEN_DEVICE_DEFAULTS = {"tablet": "false", "desktop": "false", "mobile": "false"}


def derive_filename(url: str) -> str:
    """Extract a clean filename from a URL, defaulting to photo.jpg."""
    try:
        name = url.split("?")[0].split("/")[-1]
        if name and "." in name:
            return name
    except Exception:
        pass
    return "photo.jpg"


def make_page_title_widget(page_alias: str) -> dict:
    """Seed page-title widget DDC pre-wires on every new page.

    Page-title widgets already have a real windowId so DDC never needs to derive
    one — 'type' and 'hiddenDeviceDefaults' are intentionally omitted (match HAR).
    """
    return {
        "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
        "portlet": PAGE_TITLE_PORTLET,
        "windowId": f"{page_alias}:page-title1",
        "editable": True,
        "preferences": None,
        "overrides": None,
    }


def make_widget_entry(portlet: str, widget_type: str, window_id: str) -> dict:
    """New widget entry with a pre-generated windowId.

    DDC echoes back whatever windowId we send — it does NOT auto-assign from "".
    Callers must generate the ID using the pattern "{pageAlias}:{widgetType}{n}".
    'type' is still required so DDC's widgetType field is populated correctly.
    """
    ddc_type = DDC_TYPE_BY_WIDGET_TYPE.get(widget_type, "Content")
    return {
        "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
        "portlet": portlet,
        "windowId": window_id,
        "type": ddc_type,
        "editable": True,
        "preferences": None,
        "overrides": None,
        "hiddenDeviceDefaults": HIDDEN_DEVICE_DEFAULTS,
    }


def build_widget_dto(
    widget: "ColumnWidgetDTO",
    window_id: str,
    context: dict,
    page_title: str = "",
) -> dict:
    """Build the WidgetDTO dict to place in the SavePage groups map.

    Links and form widgets use overrides + windowId ""; all others use make_widget_entry.
    """
    if widget.widget_type == "hours":
        return {
            "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
            "portlet": PORTLET_BY_WIDGET_TYPE["hours"],
            "type": "Hours",
            "windowId": "",
            "editable": True,
            "preferences": None,
            "overrides": None,
            "hiddenDeviceDefaults": HIDDEN_DEVICE_DEFAULTS,
        }

    if widget.widget_type == "contact_info":
        return {
            "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
            "portlet": PORTLET_BY_WIDGET_TYPE["contact_info"],
            "type": "Contact",
            "windowId": "",
            "editable": True,
            "preferences": None,
            "overrides": None,
            "hiddenDeviceDefaults": HIDDEN_DEVICE_DEFAULTS,
        }

    if widget.widget_type == "form":
        source = f"{page_title} - Dealer.Com Website" if page_title else "Dealer.Com Website"
        return {
            "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
            "portlet": PORTLET_BY_WIDGET_TYPE["form"],
            "type": "Contact",
            "windowId": "",
            "editable": True,
            "preferences": None,
            "overrides": {"javaClass": "java.util.List", "list": [f"source:{source}"]},
            "hiddenDeviceDefaults": HIDDEN_DEVICE_DEFAULTS,
        }

    if widget.widget_type == "links":
        block_id = context["block_id"]
        overrides: list[str] = []
        for i, btn in enumerate(widget.buttons, start=1):
            overrides += [
                f"linkText{i}:$i18n.getLabel('{block_id}_LINKTEXT{i}')",
                f"linkStyle{i}:{btn.style}",
                f"linkHref{i}:{btn.href}",
                f"linkTarget{i}:{btn.target}",
                f"linkAttrs{i}:",
                f"linkClass{i}:{btn.link_class}",
            ]
        overrides.append(f"listSize:{len(widget.buttons)}")
        return {
            "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
            "portlet": PORTLET_BY_WIDGET_TYPE["links"],
            "type": "Links",
            "windowId": "",
            "editable": True,
            "preferences": None,
            "overrides": {"javaClass": "java.util.ArrayList", "list": overrides},
            "hiddenDeviceDefaults": HIDDEN_DEVICE_DEFAULTS,
        }

    portlet = PORTLET_BY_WIDGET_TYPE[widget.widget_type]
    return make_widget_entry(portlet, widget.widget_type, window_id)


# Silence an "unused import" warning when TYPE_CHECKING is False at runtime.
_ = Any
