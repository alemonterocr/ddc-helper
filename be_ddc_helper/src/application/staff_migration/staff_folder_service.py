"""Resolve the staff media-library folder for a given project type.

Layout in DDC's media library:
  Media → Do Not Delete → {project_root} → Staff
where project_root depends on what kind of project we're inside.

We re-use the existing tree-search helpers from `media_folder_service` —
this module only contributes the project-type → root-name mapping and the
final "Staff" leaf.

Buysell projects don't migrate pages, so they don't appear here. If a
future caller passes an unknown project_type, we treat it as a hard error
rather than silently picking a default — staff data is destination-sensitive.
"""

from typing import Awaitable, Callable, Literal

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter

from ..migration.media_folder_service import (
    create_folder,
    find_folder,
    find_folder_in_children,
)

Progress = Callable[[str], Awaitable[None]]

ProjectType = Literal["cm", "gm-prebuild"]

PROJECT_ROOT_NAMES: dict[ProjectType, str] = {
    "cm":          "Custom Migration",
    "gm-prebuild": "Prebuild",
}


async def resolve_staff_folder(
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    project_type: str,
    progress: Progress,
    warnings: list[str],
) -> str | None:
    """Find or create the path: Media → Do Not Delete → {project root} → Staff.
    Returns the leaf folder_id, or None on failure (non-fatal — caller can skip
    photo uploads if folder resolution fails).
    """
    if project_type not in PROJECT_ROOT_NAMES:
        msg = f"⚠ Unsupported project_type '{project_type}' for staff folder"
        await progress(msg)
        warnings.append(msg)
        return None

    root_name = PROJECT_ROOT_NAMES[project_type]  # type: ignore[index]

    # Get folder tree
    folders_result = await bridge.call_tool(dealer_id, "get_media_folders", {
        "site_id": site_id,
    })

    if not folders_result.get("ok"):
        err = folders_result.get("error") or "WS bridge error"
        msg = f"❌ Media Library unreachable: {err} — is the Media Library tab open?"
        await progress(msg)
        warnings.append(msg)
        return None

    result_body = folders_result.get("result") or {}
    if not result_body.get("ok"):
        err = result_body.get("error") or "unknown error"
        await progress(f"❌ Media Library error: {err}")
        warnings.append(f"Media Library error: {err}")
        return None

    tree: list = result_body.get("tree", [])

    # 1. Media root
    await progress("Locating 'Media' root folder…")
    media_id = find_folder(tree, "media") or ""

    # 2. Do Not Delete
    await progress("Checking for 'Do Not Delete' folder…")
    dnd_id = (
        find_folder_in_children(tree, media_id, "donotdelete")
        if media_id else find_folder(tree, "donotdelete")
    )
    if not dnd_id:
        await progress("Creating 'Do Not Delete' folder…")
        dnd_id = await create_folder(
            bridge, dealer_id, site_id, media_id, "Do Not Delete", warnings,
        )
        if not dnd_id:
            return None

    # 3. Project root (Custom Migration / Prebuild)
    norm_root = root_name.lower().replace(" ", "").replace("-", "")
    await progress(f"Checking for '{root_name}' folder…")
    root_id = find_folder_in_children(tree, dnd_id, norm_root)
    if not root_id:
        await progress(f"Creating '{root_name}' folder…")
        root_id = await create_folder(
            bridge, dealer_id, site_id, dnd_id, root_name, warnings,
        )
        if not root_id:
            return None

    # 4. Staff leaf
    await progress("Checking for 'Staff' folder…")
    staff_id = find_folder_in_children(tree, root_id, "staff")
    if not staff_id:
        await progress("Creating 'Staff' folder…")
        staff_id = await create_folder(
            bridge, dealer_id, site_id, root_id, "Staff", warnings,
        )

    return staff_id or None
