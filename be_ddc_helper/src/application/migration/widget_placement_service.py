"""Widget pre/post-placement bridge calls for the execute flow.

Pre-placement runs once per widget before SavePage, to prepare any side data
DDC needs (currently: site labels for `links` widgets).

Post-placement runs once per widget after SavePage has assigned the final
windowId, to fill in widget content (HTML for `content`, CDN-hosted image for
`image`). `links` widgets have no post step — their text already lives in
site labels.
"""

import time
from typing import TYPE_CHECKING, Awaitable, Callable

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.application.migration.widget_builder import derive_filename

if TYPE_CHECKING:
    from src.adapters.inbound.http.execute_dtos import ColumnWidgetDTO


Progress = Callable[[str], Awaitable[None]]


async def pre_place(
    widget: "ColumnWidgetDTO",
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    progress: Progress,
    warnings: list[str],
) -> dict:
    """Run per-widget pre-placement logic before save_page_layout.

    Returns a context dict forwarded to widget_builder.build_widget_dto.
    Only links widgets do real work here — all others return an empty context.
    """
    if widget.widget_type == "links":
        block_id = f"SITEBUILDER_BUTTONBLOCK_{int(time.time() * 1000)}"
        labels = [
            {"key": f"{block_id}_LINKTEXT{i + 1}", "value": btn.text}
            for i, btn in enumerate(widget.buttons)
        ]
        result = await bridge.call_tool(dealer_id, "update_site_labels", {
            "site_id": site_id,
            "labels": labels,
        })
        if not (result.get("ok") and result.get("result", {}).get("success")):
            err = result.get("result", {}).get("error") or result.get("error", "unknown")
            warnings.append(f"UpdateSiteLabels failed for block '{block_id}': {err}")
        return {"block_id": block_id}

    return {}


async def post_place(
    widget: "ColumnWidgetDTO",
    window_id: str,
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    folder_id: str | None,
    section_type: str,
    slot_idx: int,
    widget_idx: int,
    progress: Progress,
    warnings: list[str],
) -> None:
    """Run per-widget post-placement logic after the layout is confirmed.

    content → save_content
    image   → upload to media library + set_window_preferences
    links   → no-op (text lives in site labels, not the widget)
    """
    if widget.widget_type == "content" and widget.html:
        await _inject_content(
            bridge, dealer_id, site_id, window_id, widget.html, progress, warnings
        )

    elif widget.widget_type == "image" and widget.source_url:
        if not folder_id:
            msg = (
                f"Image widget {widget_idx + 1} of '{section_type}' "
                f"slot {slot_idx + 1} skipped — media library folder could not be resolved."
            )
            await progress(f"⚠ {msg}")
            warnings.append(msg)
        else:
            await _upload_and_configure_image(
                bridge, dealer_id, site_id, window_id,
                widget.source_url, folder_id,
                progress, warnings,
            )
    # links: no post-placement step — text is stored in site labels


async def _inject_content(
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    window_id: str,
    html: str,
    progress: Progress,
    warnings: list[str],
) -> None:
    await progress(f"Injecting HTML into '{window_id}'…")
    result = await bridge.call_tool(dealer_id, "save_content", {
        "site_id": site_id,
        "window_id": window_id,
        "html": html,
    })
    if result.get("ok") and result.get("result", {}).get("success"):
        await progress(f"✓ Content injected into '{window_id}'.")
    else:
        err = result.get("result", {}).get("error") or result.get("error", "unknown")
        await progress(f"⚠ Content injection failed for '{window_id}': {err}")
        warnings.append(f"Content injection failed for '{window_id}': {err}")


async def _upload_and_configure_image(
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    window_id: str,
    source_url: str,
    folder_id: str,
    progress: Progress,
    warnings: list[str],
) -> None:
    filename = derive_filename(source_url)
    await progress(f"Uploading '{filename}' → media library (widget '{window_id}')…")

    upload = await bridge.call_tool(dealer_id, "upload_media_image", {
        "site_id": site_id,
        "image_url": source_url,
        "folder_id": folder_id,
        "filename": filename,
    })

    if not upload.get("ok"):
        err = upload.get("error", "unknown")
        await progress(f"⚠ Image upload failed for '{window_id}': {err}")
        warnings.append(f"Image upload failed for '{window_id}': {err}")
        return

    cdn_url: str = upload.get("result", {}).get("cdn_url", "")
    if not cdn_url:
        msg = f"Upload succeeded but no CDN URL returned for '{window_id}' — widget not configured."
        await progress(f"⚠ {msg}")
        warnings.append(msg)
        return

    await progress(f"Configuring image widget '{window_id}' with CDN URL…")
    prefs = await bridge.call_tool(dealer_id, "set_window_preferences", {
        "site_id": site_id,
        "window_id": window_id,
        "image_path": cdn_url,
    })

    # prefs.get("ok") only reflects the WS round-trip; the actual DDC result is in
    # result.success from the injected function.
    prefs_ok = prefs.get("ok") and prefs.get("result", {}).get("success")
    if prefs_ok:
        await progress(f"✓ Image configured for '{window_id}'.")
    else:
        err = prefs.get("result", {}).get("error") or prefs.get("error", "unknown")
        await progress(f"⚠ Image preference save failed for '{window_id}': {err}")
        warnings.append(f"SetWindowPreferences failed for '{window_id}': {err}")
