"""Media-library folder resolution for the execute flow.

Resolves (or creates) the three-level folder path used for migration uploads:
    Media → Do Not Delete → Custom Migration → {page title}

The bridge-touching wrapper (`resolve_media_folder`) owns the WS calls; the
tree-search helpers are pure functions that operate on the raw folder tree
returned by the `get_media_folders` injected function.

The DDC media library returns inconsistent field names across responses
(`description`/`libraryName`/`folderName`/`label`, `value`/`id`/`folderId`,
`children`/`subFolders`/`subfolders`/`folders`). The helpers tolerate every
observed variant.
"""

import re
from typing import Awaitable, Callable

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter


Progress = Callable[[str], Awaitable[None]]


async def resolve_media_folder(
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    page_title: str,
    progress: Progress,
    warnings: list[str],
) -> str | None:
    """Find or create the three-level folder path:
       Media → Do Not Delete → Custom Migration → {page title}.
    Returns the leaf folder_id, or None on failure (non-fatal).
    """
    # Sanitize page title into a clean folder name (strip special chars, max 60 chars)
    folder_name = re.sub(r"[^\w\s\-]", "", page_title, flags=re.UNICODE).strip()[:60] or "migration"

    # Get folder tree
    folders_result = await bridge.call_tool(dealer_id, "get_media_folders", {
        "site_id": site_id,
    })

    # Check WS transport first, then the injected function's own result.
    # The transport ok is almost always True — the real failure lives in result.ok.
    if not folders_result.get("ok"):
        err = folders_result.get("error") or "WS bridge error"
        msg = f"❌ Media Library unreachable: {err} — is the Media Library tab open?"
        await progress(msg)
        warnings.append(msg)
        return None

    result_body = folders_result.get("result") or {}
    if not result_body.get("ok"):
        err = result_body.get("error") or "unknown error"
        if any(x in err for x in ["401", "403", "reload", "JWTAuth", "credential"]):
            msg = (
                "❌ Media Library session expired — "
                "reload the Media Library tab, log in again, then click Check Credentials."
            )
        else:
            msg = f"❌ Media Library error: {err}"
        await progress(msg)
        warnings.append(msg)
        return None

    tree: list = result_body.get("tree", [])

    # Find the "Media" root folder — DDC always creates it; use its ID as
    # the parent when creating "Do Not Delete" so we don't nest it elsewhere.
    await progress("Locating 'Media' root folder…")
    media_id = find_folder(tree, "media") or ""
    if media_id:
        await progress("✓ Found 'Media' root folder.")
    else:
        await progress("⚠ 'Media' root folder not found — will create at tree root.")

    # Resolve or create Do Not Delete under Media
    await progress("Checking for 'Do Not Delete' folder…")
    dnd_id = (
        find_folder_in_children(tree, media_id, "donotdelete")
        if media_id else find_folder(tree, "donotdelete")
    )
    if not dnd_id:
        await progress("Creating 'Do Not Delete' folder…")
        dnd_id = await create_folder(bridge, dealer_id, site_id, media_id, "Do Not Delete", warnings)
        if not dnd_id:
            reason = warnings[-1] if warnings else "unknown error"
            await progress(f"⚠ Failed to create 'Do Not Delete' folder — {reason}")
            return None
    else:
        await progress("✓ Found 'Do Not Delete' folder.")

    # Resolve or create Custom Migration
    await progress("Checking for 'Custom Migration' subfolder…")
    custom_id = find_folder_in_children(tree, dnd_id, "custommigration")
    if not custom_id:
        await progress("Creating 'Custom Migration' folder…")
        custom_id = await create_folder(bridge, dealer_id, site_id, dnd_id, "Custom Migration", warnings)
        if not custom_id:
            reason = warnings[-1] if warnings else "unknown error"
            await progress(f"⚠ Failed to create 'Custom Migration' folder — {reason}")
            return None
    else:
        await progress("✓ Found 'Custom Migration' folder.")

    # Resolve or create page folder using the human-readable page title
    norm_folder = folder_name.lower().replace(" ", "").replace("-", "")
    await progress(f"Checking for '{folder_name}' subfolder…")
    page_folder_id = find_folder_in_children(tree, custom_id, norm_folder)
    if not page_folder_id:
        await progress(f"Creating folder '{folder_name}'…")
        page_folder_id = await create_folder(bridge, dealer_id, site_id, custom_id, folder_name, warnings)
        if not page_folder_id:
            reason = warnings[-1] if warnings else "unknown error"
            await progress(f"⚠ Failed to create folder '{folder_name}' — {reason}")
    else:
        await progress(f"✓ Found existing folder '{folder_name}'.")

    return page_folder_id


def find_folder(tree: list, norm_name: str) -> str | None:
    """Depth-first search for a folder by normalised name (lowercase, no spaces/hyphens)."""
    for node in tree:
        if not isinstance(node, dict):
            continue
        desc = str(
            node.get("description") or node.get("libraryName") or
            node.get("folderName") or node.get("label") or node.get("name") or ""
        )
        if desc.lower().replace(" ", "").replace("-", "") == norm_name:
            return str(node.get("value") or node.get("id") or node.get("folderId") or "")
        children = (
            node.get("children") or node.get("subFolders") or
            node.get("subfolders") or node.get("folders") or []
        )
        found = find_folder(children, norm_name)
        if found:
            return found
    return None


def find_folder_in_children(tree: list, parent_id: str, norm_name: str) -> str | None:
    """Find a folder by parent_id first, then search its children."""
    parent = find_node_by_id(tree, parent_id)
    if not parent:
        return None
    children = (
        parent.get("children") or parent.get("subFolders") or
        parent.get("subfolders") or parent.get("folders") or []
    )
    return find_folder(children, norm_name)


def find_node_by_id(tree: list, folder_id: str) -> dict | None:
    for node in tree:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("value") or node.get("id") or node.get("folderId") or "")
        if node_id == folder_id:
            return node
        children = (
            node.get("children") or node.get("subFolders") or
            node.get("subfolders") or node.get("folders") or []
        )
        found = find_node_by_id(children, folder_id)
        if found:
            return found
    return None


async def create_folder(
    bridge: WsBridgeAdapter,
    dealer_id: str,
    site_id: str,
    parent_id: str,
    name: str,
    warnings: list[str],
) -> str | None:
    result = await bridge.call_tool(dealer_id, "create_media_folder", {
        "site_id": site_id,
        "parent_id": parent_id,
        "name": name,
    })
    # result["result"] is the raw return from createMediaFolderInjected:
    # { ok: bool, folder_id?: string, error?: string }
    res_body: dict = result.get("result") or {}
    folder_id = str(res_body.get("folder_id") or "") if res_body.get("ok") else None
    if not folder_id:
        err = res_body.get("error") or result.get("error") or "unknown — check media library tab is open and logged in"
        warnings.append(f"Failed to create folder '{name}': {err}")
    return folder_id or None
