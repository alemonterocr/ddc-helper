"""Staff-page execute pipeline.

Sequential async class — same reasoning as `MigrationExecutor` in
`application/migration/execute_orchestrator.py`. Not a LangGraph because the
flow is strictly sequential with shared mutable state, no branching, no
per-step retry semantics.

Unlike regular page migration, staff data is injected as widget data into the
existing ``ws-staff-listing`` widget (on ``/dealership/staff.htm``) — no new
page is created. This matches the cms-auto-builder pattern.

Steps:
  1. _resolve_staff_folder     — Do Not Delete → {project_root} → Staff
  2. _upload_photos            — per-staff; fills `photo` field; failures soft
  3. _create_departments       — register department labels + department-info-list
                                 entries in DDC; remaps staff department names → IDs
  4. _inject_staff_listing     — POSTs ws-staff-listing itemlist payload via
                                 the ``inject_staff_listing`` injected JS tool

The itemlist payload format mirrors what cms-auto-builder ships in production:
  { id: "ws-staff-listing", siteId, items: [...] }
where each item has the StaffMember fields plus DDC-mandated metadata
(status, deviceOverrides, entityComponentClassName).
"""

import secrets
from typing import Awaitable, Callable

from src.adapters.inbound.http.staff_dtos import (
    ExecuteStaffRequest,
    ExecuteStaffResponse,
    StaffMemberDTO,
)
from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.application.migration.widget_builder import derive_filename
from src.domain.errors import BridgeNotConnectedError, BridgeTimeoutError

from .staff_folder_service import resolve_staff_folder

Progress = Callable[[str], Awaitable[None]]


class _AbortRun(Exception):
    """Internal control-flow signal to short-circuit run() from a step."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class StaffExecutor:
    def __init__(self, body: ExecuteStaffRequest, bridge: WsBridgeAdapter):
        self.body = body
        self.bridge = bridge
        self.site_id = body.dealer_id
        self.warnings: list[str] = []

        # Working copy of staff — we mutate `photo` on each entry as uploads succeed.
        self.staff: list[StaffMemberDTO] = [s.model_copy() for s in body.staff]

        self.staff_folder_id: str | None = None

    async def run(self) -> ExecuteStaffResponse:
        try:
            await self._resolve_staff_folder()
            await self._upload_photos()
            await self._create_departments()
            await self._inject_staff_listing()

            await self._progress("Staff data injected into existing staff listing widget")
            return ExecuteStaffResponse(ok=True, warnings=self.warnings)
        except _AbortRun as e:
            return ExecuteStaffResponse(ok=False, warnings=self.warnings, error=e.reason)
        except BridgeNotConnectedError as e:
            return ExecuteStaffResponse(ok=False, warnings=self.warnings, error=str(e))
        except BridgeTimeoutError as e:
            return ExecuteStaffResponse(ok=False, warnings=self.warnings, error=str(e))

    # ── Steps ─────────────────────────────────────────────────────────────────

    async def _resolve_staff_folder(self) -> None:
        """Folder path varies by project type — see staff_folder_service."""
        with_photo = sum(1 for s in self.staff if s.has_photo and s.original_photo_url)
        if with_photo == 0:
            await self._progress("No photos to upload — skipping folder resolution")
            return

        await self._progress("Resolving Staff folder in media library…")
        self.staff_folder_id = await resolve_staff_folder(
            self.bridge,
            self.body.dealer_id,
            self.site_id,
            self.body.project_type,
            self._progress,
            self.warnings,
        )
        if not self.staff_folder_id:
            await self._progress("⚠ Staff folder could not be resolved — photos will be skipped")

    async def _upload_photos(self) -> None:
        if not self.staff_folder_id:
            return

        targets = [
            (i, s) for i, s in enumerate(self.staff)
            if s.has_photo and s.original_photo_url
        ]
        if not targets:
            return

        total = len(targets)
        await self._progress(f"Uploading {total} photo(s)…")

        for n, (idx, member) in enumerate(targets, start=1):
            url = member.original_photo_url or ""
            filename = derive_filename(url)
            display_name = member.name or filename
            await self._progress(f"Uploading '{display_name}' ({n}/{total})…")

            upload = await self.bridge.call_tool(self.body.dealer_id, "upload_media_image", {
                "site_id": self.site_id,
                "image_url": url,
                "folder_id": self.staff_folder_id,
                "filename": filename,
            })

            ok = upload.get("ok")
            cdn = (upload.get("result") or {}).get("cdn_url") if ok else None
            if ok and cdn:
                self.staff[idx].photo = cdn
            else:
                err = (upload.get("result") or {}).get("error") or upload.get("error") or "unknown"
                self.staff[idx].photo = ""  # render placeholder, don't break the row
                msg = f"Photo upload failed for '{display_name}': {err}"
                await self._progress(f"⚠ {msg}")
                self.warnings.append(msg)

    async def _create_departments(self) -> None:
        """Register department labels and department-info-list entries in DDC,
        then remap staff members' ``department`` field from human-readable names
        to DDC department IDs.

        Matches cms-auto-builder Agent 2 (Department Creator):
          1. Identify unique department names
          2. Generate IDs + label keys
          3. For each department (cumulative — both labels and itemlist replace
             the full set on every POST):
             a. POST update_site_labels with cumulative map
             b. POST inject_itemlist with cumulative items → department-info-list
          4. Replace staff[].department = ID
        """
        seen: set[str] = set()
        names: list[str] = []
        for s in self.staff:
            if s.department and s.department not in seen:
                seen.add(s.department)
                names.append(s.department)
        if not names:
            return

        used_labels: set[str] = set()
        entries: list[dict[str, str]] = []
        for name in names:
            dept_id = f"ID_{secrets.token_hex(3)}"
            base = name.upper().replace(" ", "_") + "_DEPARTMENT"
            label = base
            i = 2
            while label in used_labels:
                label = f"{base}_{i}"
                i += 1
            used_labels.add(label)
            entries.append({"name": name, "id": dept_id, "label": label})

        await self._progress(f"Registering {len(entries)} department(s)…")

        committed_labels: dict[str, str] = {}
        committed_items: list[dict[str, object]] = []

        for entry in entries:
            next_labels = {**committed_labels, entry["label"]: entry["name"]}
            next_item: dict[str, object] = {
                "id":                entry["id"],
                "label":             entry["label"],
                "deviceOverrides":   {},
                "entityComponentClassName": "com.dealer.cms.model.widgets.DepartmentInfo",
            }
            next_items = committed_items + [next_item]

            labels_result = await self.bridge.call_tool(self.body.dealer_id, "update_site_labels", {
                "site_id": self.site_id,
                "labels":  [{"key": k, "value": v} for k, v in next_labels.items()],
            })
            if not (labels_result.get("ok") and (labels_result.get("result") or {}).get("success")):
                err = (labels_result.get("result") or {}).get("error") or labels_result.get("error") or "unknown"
                msg = f"Department '{entry['name']}' — labels failed: {err}"
                await self._progress(f"⚠ {msg}")
                self.warnings.append(msg)
                continue

            itemlist_payload = {
                "id":     "department-info-list",
                "siteId": self.site_id,
                "items":  next_items,
            }
            itemlist_result = await self.bridge.call_tool(self.body.dealer_id, "inject_itemlist", {
                "site_id": self.site_id,
                "payload": itemlist_payload,
            })
            if not (itemlist_result.get("ok") and (itemlist_result.get("result") or {}).get("success")):
                err = (itemlist_result.get("result") or {}).get("error") or itemlist_result.get("error") or "unknown"
                msg = f"Department '{entry['name']}' — itemlist failed: {err}"
                await self._progress(f"⚠ {msg}")
                self.warnings.append(msg)
                continue

            committed_labels = next_labels
            committed_items = next_items
            await self._progress(f"✓ Department: {entry['name']} → {entry['id']}")

        name_to_id = {e["name"]: e["id"] for e in entries
                      if any(i["id"] == e["id"] for i in committed_items)}
        for member in self.staff:
            mapped = name_to_id.get(member.department)
            if mapped:
                member.department = mapped

    async def _inject_staff_listing(self) -> None:
        """POST the ws-staff-listing itemlist payload to DDC via the
        `inject_staff_listing` injected JS tool. The injected function (frontend
        side) builds the actual HTTPS request to:
            https://{host}/cc-website/as/{siteId}/{siteId}-admin/cms-configurator/api/itemlist?siteId={siteId}
        """
        items = [
            {
                "department":              s.department,
                "name":                    s.name,
                "title":                   s.title,
                "phone":                   s.phone,
                "email":                   s.email,
                "bio":                     s.bio or "",
                "photo":                   s.photo or "",
                "status":                  "Active",
                "deviceOverrides":         {},
                "entityComponentClassName": "com.dealer.cms.model.widgets.StaffListing",
            }
            for s in self.staff
        ]

        payload = {
            "id":     "ws-staff-listing",
            "siteId": self.site_id,
            "items":  items,
        }

        await self._progress(f"Injecting {len(items)} staff member(s) into DDC…")
        result = await self.bridge.call_tool(self.body.dealer_id, "inject_staff_listing", {
            "site_id": self.site_id,
            "payload": payload,
        })

        ok = result.get("ok") and (result.get("result") or {}).get("success")
        if not ok:
            err = (result.get("result") or {}).get("error") or result.get("error") or "unknown"
            raise _AbortRun(f"Failed to inject staff listing: {err}")

        await self._progress(f"✓ {len(items)} staff member(s) injected")

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _progress(self, msg: str) -> None:
        await self.bridge.send_progress(self.body.dealer_id, msg)
