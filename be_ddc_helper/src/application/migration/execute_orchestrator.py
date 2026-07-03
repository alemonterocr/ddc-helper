"""Orchestrates the /execute pipeline.

A single `MigrationExecutor.run()` drives the 6 steps that turn a section plan
into a populated DDC page:

    1. ensure_page          — check existence + (create or resolve alias)
    2. inject_sections      — only on freshly created pages
    3. place_widgets        — build SavePage groups, fire save_page_layout per section
    4. refresh_layout       — re-fetch to capture DDC-assigned windowIds
    5. resolve_media_folder — if any image widgets exist
    6. post_place_widgets   — inject content HTML / upload images

State that used to live in closure-over-handler (current_groups, slot_widget_ids,
wtype_counter, actual_alias, etc.) is now instance state on the executor.

DDC integration notes worth preserving here (not in docstrings of individual
methods because they apply across them):
- `result.get("ok")` reflects only WS transport success — the real success/error
  lives in `result["result"]["success"]` / `result["result"]["error"]`.
- Window IDs follow `"{pageAlias}:{widgetType}{n}"`. DDC echoes back whatever
  we send for non-`links` widgets; `links` widgets always use windowId `""`.
- Section injection is skipped when the page already exists (re-runs would
  duplicate sections).
"""

from src.adapters.inbound.http.execute_dtos import (
    ColumnWidgetDTO,
    ExecuteRequest,
    ExecuteResponse,
    SectionPlanItemDTO,
)
from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.application.migration.media_folder_service import resolve_media_folder
from src.application.migration.widget_builder import (
    PORTLET_BY_WIDGET_TYPE,
    build_widget_dto,
    make_page_title_widget,
)
from src.application.migration.widget_placement_service import post_place, pre_place
from src.domain.catalog.section_slots import get_section_slots
from src.domain.errors import BridgeNotConnectedError, BridgeTimeoutError


class _AbortRun(Exception):
    """Internal control-flow signal used to short-circuit `run()` from a step
    (e.g. page-create failure) without raising a real domain error.
    Carries the `error` string that will be returned to the caller.
    """
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MigrationExecutor:
    def __init__(self, body: ExecuteRequest, bridge: WsBridgeAdapter):
        self.body = body
        self.bridge = bridge
        self.site_id = body.dealer_id  # site_id == dealer_id in DDC
        self.warnings: list[str] = []

        # Mutated during ensure_page
        self.actual_alias: str = body.page_alias
        self.page_exists: bool = False

        # Built once, read across phases
        self.sorted_plan = sorted(body.section_plan, key=lambda x: x.position)
        self.url_slug = body.page_alias.removesuffix(".htm")
        self.sections_with_widgets = [s for s in self.sorted_plan if any(s.slots)]

        # SavePage state — seeded in place_widgets, mutated through place_widgets and refresh_layout
        self.current_groups: dict[str, list[dict]] = {}
        # slot_key → ordered list of generated windowIds (fallback for refresh_layout misses)
        self.slot_widget_ids: dict[str, list[str]] = {}

        # Set in resolve_media_folder step
        self.folder_id: str | None = None

    async def run(self) -> ExecuteResponse:
        try:
            await self._ensure_page()
            await self._inject_sections()
            await self._place_widgets()
            await self._refresh_layout()
            await self._resolve_media_folder()
            await self._post_place_widgets()

            await self._progress(f"✓ Done! Migration complete for '{self.actual_alias}'.")
            return ExecuteResponse(ok=True, page_alias=self.actual_alias, warnings=self.warnings)
        except _AbortRun as e:
            return ExecuteResponse(ok=False, page_alias=self.body.page_alias, error=e.reason)
        except BridgeNotConnectedError as e:
            return ExecuteResponse(ok=False, page_alias=self.body.page_alias, error=str(e))
        except BridgeTimeoutError as e:
            return ExecuteResponse(ok=False, page_alias=self.body.page_alias, error=str(e))

    # ── Step 1+2: ensure page ────────────────────────────────────────────────

    async def _ensure_page(self) -> None:
        """Detect whether the page exists, then either create it or resolve
        the real DDC alias of the existing one."""
        await self._progress(f"Checking if page '{self.body.page_alias}' exists…")
        self.page_exists = await self._check_page_exists()

        if self.page_exists:
            await self._resolve_existing_alias()
        else:
            await self._create_new_page()

    async def _check_page_exists(self) -> bool:
        check = await self.bridge.call_tool(self.body.dealer_id, "check_page_exists", {
            "site_id": self.site_id,
            "page_alias": self.body.page_alias,
        })
        return check.get("result", {}).get("exists", False)

    async def _resolve_existing_alias(self) -> None:
        await self._progress(
            f"Page '{self.body.page_alias}' already exists — resolving DDC alias…"
        )
        alias_lookup = await self.bridge.call_tool(
            self.body.dealer_id, "get_page_alias_by_path",
            {"site_id": self.site_id, "page_slug": self.body.page_alias},
        )
        resolved = alias_lookup.get("result", {}).get("alias")
        if not resolved:
            err = alias_lookup.get("result", {}).get("error") or "alias lookup returned no result"
            await self._progress(
                f"❌ Could not resolve DDC alias for '{self.body.page_alias}': {err}"
            )
            raise _AbortRun(f"Page exists but alias could not be resolved: {err}")
        self.actual_alias = resolved
        await self._progress(f"✓ Resolved existing page alias: '{self.actual_alias}'.")

    async def _create_new_page(self) -> None:
        slug = self.body.page_alias.removesuffix(".htm")
        await self._progress(
            f"Creating page '{self.body.page_title}' at path '/{slug}.htm'…"
        )
        create = await self.bridge.call_tool(self.body.dealer_id, "create_page", {
            "site_id": self.site_id,
            "path": slug,
            "title": self.body.page_title,
        })
        if not (create.get("ok") and create.get("result", {}).get("success")):
            result_obj = create.get("result") or {}
            error_msg = result_obj.get("error") or create.get("error") or "Unknown error"
            await self._progress(f"❌ Page creation failed: {error_msg}")
            raise _AbortRun(f"Failed to create page: {error_msg}")

        self.actual_alias = create.get("result", {}).get("pageAlias") or self.body.page_alias
        await self._progress(f"✓ Page created: '{self.actual_alias}'")

    # ── Step 3: inject sections ──────────────────────────────────────────────

    async def _inject_sections(self) -> None:
        """Step 3: inject sections into a freshly created page. Skipped for
        existing pages because re-injecting would duplicate sections."""
        if self.page_exists:
            await self._progress("Page already had sections — skipping section injection.")
            return
        total = len(self.sorted_plan)
        for i, item in enumerate(self.sorted_plan, start=1):
            await self._inject_one_section(item, i, total)

    async def _inject_one_section(
        self, item: SectionPlanItemDTO, index: int, total: int
    ) -> None:
        await self._progress(f"Injecting section '{item.section_type}' ({index}/{total})…")
        inject = await self.bridge.call_tool(self.body.dealer_id, "inject_section", {
            "site_id": self.site_id,
            "page_alias": self.actual_alias,
            "section_type": item.section_type,
        })
        if inject.get("ok") and inject.get("result", {}).get("success"):
            await self._progress(f"✓ Section '{item.section_type}' injected.")
            return
        result_obj = inject.get("result") or {}
        error_msg = result_obj.get("error") or inject.get("error") or "Unknown error"
        await self._progress(f"⚠ Section '{item.section_type}' failed: {error_msg}")
        self.warnings.append(
            f"Section '{item.section_type}' (pos {item.position}) failed: {error_msg}"
        )

    # ── Step 4: place widgets ────────────────────────────────────────────────

    async def _place_widgets(self) -> None:
        """Build SavePage groups from the plan slots, fire one save_page_layout
        per section with widgets, accumulating groups as DDC echoes them back."""
        if not self.sections_with_widgets:
            return
        await self._progress("Placing widgets into sections…")
        self._seed_page_title_group()
        wtype_counter = self._seed_wtype_counter()
        for item in self.sections_with_widgets:
            await self._place_section(item, wtype_counter)

    def _seed_page_title_group(self) -> None:
        """Seed SavePage groups from scratch: just the page-title slot that DDC
        pre-wires on every new page. We intentionally do NOT fetch the DOM here
        — the rendered HTML includes site-wide template slots (header, nav,
        footer) that DDC rejects with 422 if included in SavePage. The DOM fetch
        in refresh_layout (after SavePage) is used only to read back the
        assigned windowIds, not to build the groups sent to DDC.
        """
        self.current_groups = {"1-1": [make_page_title_widget(self.actual_alias)]}

    def _seed_wtype_counter(self) -> dict[str, int]:
        """Seed a per-type counter from any windowIds already in the layout so
        we don't collide with pre-existing widgets. Pattern: "{alias}:{type}{n}".
        DDC echoes back whatever windowId we send — it does NOT auto-assign —
        so we must generate real IDs here rather than passing "".
        """
        counter: dict[str, int] = {}
        for slot_widgets in self.current_groups.values():
            for w in slot_widgets:
                _bump_counter_from_window_id(counter, str((w or {}).get("windowId") or ""))
        return counter

    async def _place_section(
        self, item: SectionPlanItemDTO, wtype_counter: dict[str, int]
    ) -> None:
        ddc_slots = get_section_slots(item.section_type, item.position)
        if not ddc_slots:
            return  # pre-wired section slipped through, skip

        for slot_idx, slot_key in enumerate(ddc_slots):
            slot_widgets = item.slots[slot_idx] if slot_idx < len(item.slots) else []
            if not slot_widgets:
                continue
            entries, slot_ids = await self._build_slot_entries(item, slot_idx, slot_widgets, wtype_counter)
            if entries:
                self.slot_widget_ids[slot_key] = slot_ids
                self.current_groups[slot_key] = entries

        await self._save_section_layout(item)

    async def _build_slot_entries(
        self,
        item: SectionPlanItemDTO,
        slot_idx: int,
        slot_widgets: list[ColumnWidgetDTO],
        wtype_counter: dict[str, int],
    ) -> tuple[list[dict], list[str]]:
        entries: list[dict] = []
        slot_ids: list[str] = []
        for widget in slot_widgets:
            if widget.widget_type not in PORTLET_BY_WIDGET_TYPE:
                self.warnings.append(
                    f"Unknown widget_type '{widget.widget_type}' for "
                    f"'{item.section_type}' slot {slot_idx + 1} — skipped."
                )
                continue
            context = await pre_place(
                widget, self.bridge, self.body.dealer_id, self.site_id,
                self._progress, self.warnings,
            )
            wid = self._generate_window_id(widget, wtype_counter, slot_ids)
            entries.append(build_widget_dto(widget, wid, context, self.body.page_title))
        return entries, slot_ids

    def _generate_window_id(
        self,
        widget: ColumnWidgetDTO,
        wtype_counter: dict[str, int],
        slot_ids: list[str],
    ) -> str:
        """Links widgets always use windowId "" — DDC does not assign one.
        All other types get a client-generated ID so DDC echoes it back."""
        if widget.widget_type == "links":
            return ""
        wtype = widget.widget_type
        wtype_counter[wtype] = wtype_counter.get(wtype, 0) + 1
        wid = f"{self.actual_alias}:{wtype}{wtype_counter[wtype]}"
        slot_ids.append(wid)
        return wid

    async def _save_section_layout(self, item: SectionPlanItemDTO) -> None:
        section_label = f"{item.section_type} (pos {item.position})"
        await self._progress(f"Saving widgets for '{section_label}'…")

        save = await self.bridge.call_tool(self.body.dealer_id, "save_page_layout", {
            "site_id": self.site_id,
            "page_alias": self.actual_alias,      # DDC internal alias e.g. SITEBUILDER_AWARDS_1
            "page_title": self.body.page_title,
            "page_path": f"/{self.url_slug}.htm",  # URL path e.g. /awards.htm
            "groups": self.current_groups,
        })
        if save.get("ok") and save.get("result", {}).get("success"):
            updated_groups = save.get("result", {}).get("groups")
            if updated_groups:
                self.current_groups = updated_groups
            await self._progress(f"✓ Widgets placed in '{section_label}'.")
            return
        result_obj = save.get("result") or {}
        error_msg = result_obj.get("error") or save.get("error") or "Unknown error"
        await self._progress(f"⚠ Widget save failed for '{section_label}': {error_msg}")
        self.warnings.append(f"Widget save failed for '{section_label}': {error_msg}")

    # ── Step 4b: refresh layout ──────────────────────────────────────────────

    async def _refresh_layout(self) -> None:
        """Re-fetch the page layout to get DDC-assigned windowIds. SavePage's
        response groups may not carry the final windowIds (DDC assigns them
        server-side). A fresh GET is the only reliable source of truth before
        we attempt content/image injection."""
        if not self.sections_with_widgets:
            return
        await self._progress("Re-fetching page layout to resolve assigned windowIds…")
        fresh_layout = await self.bridge.call_tool(self.body.dealer_id, "get_page_layout", {
            "site_id": self.site_id,
            "page_alias": self.actual_alias,
            "page_slug": self.url_slug,
        })
        fresh_groups: dict[str, list[dict]] = (
            fresh_layout.get("result", {}).get("groups") or {}
        )
        if fresh_groups:
            self.current_groups = fresh_groups
            await self._progress(f"✓ Page layout refreshed ({len(fresh_groups)} slot(s) loaded).")
        else:
            await self._progress("⚠ Could not refresh layout — windowIds may be missing.")

    # ── Step 5: resolve media folder ─────────────────────────────────────────

    async def _resolve_media_folder(self) -> None:
        """Resolve (or create) the media library folder used as the target for
        all image widget uploads. Path:
            Media → Do Not Delete → Custom Migration → {page title}.
        """
        image_widgets = self._collect_image_widgets_with_url()
        await self._log_image_diagnostic(len(image_widgets), self._count_images_without_url())
        if not image_widgets:
            return
        await self._progress("Resolving media library folder…")
        self.folder_id = await resolve_media_folder(
            self.bridge, self.body.dealer_id, self.site_id,
            self.body.page_title, self._progress, self.warnings,
        )

    def _collect_image_widgets_with_url(self) -> list[ColumnWidgetDTO]:
        return [
            widget
            for item in self.sections_with_widgets
            for slot_widgets in item.slots
            for widget in slot_widgets
            if widget.widget_type == "image" and widget.source_url
        ]

    def _count_images_without_url(self) -> int:
        return sum(
            1
            for item in self.sections_with_widgets
            for slot_widgets in item.slots
            for widget in slot_widgets
            if widget.widget_type == "image" and not widget.source_url
        )

    async def _log_image_diagnostic(self, with_url: int, without_url: int) -> None:
        """Show image widget breakdown in the progress log so the user can
        tell whether the algo/LLM skipped source_url entirely."""
        if with_url:
            await self._progress(
                f"Found {with_url} image widget(s) to upload to media library."
            )
        elif without_url:
            await self._progress(
                f"⚠ {without_url} image widget(s) have no source_url — "
                f"image URLs may be missing. Skipping media upload."
            )
        else:
            await self._progress("No image widgets in this plan — skipping media upload.")

    # ── Step 6: post-place widgets ───────────────────────────────────────────

    async def _post_place_widgets(self) -> None:
        """Inject content HTML and upload/configure images per widget. Iterates
        item.slots[slot_idx][widget_idx] uniformly for all section types."""
        ddc_slots_cache: dict[str, list[str]] = {}  # section_type:position → ddc slot keys
        for item in self.sections_with_widgets:
            await self._process_section_post(item, ddc_slots_cache)

    async def _process_section_post(
        self,
        item: SectionPlanItemDTO,
        ddc_slots_cache: dict[str, list[str]],
    ) -> None:
        cache_key = f"{item.section_type}:{item.position}"
        ddc_slots = ddc_slots_cache.setdefault(
            cache_key, get_section_slots(item.section_type, item.position) or []
        )
        for slot_idx, slot_key in enumerate(ddc_slots):
            slot_widgets = item.slots[slot_idx] if slot_idx < len(item.slots) else []
            windows = self.current_groups.get(slot_key, [])
            for widget_idx, col in enumerate(slot_widgets):
                await self._process_widget_post(
                    item, col, slot_idx, slot_key, widget_idx, windows
                )

    async def _process_widget_post(
        self,
        item: SectionPlanItemDTO,
        col: ColumnWidgetDTO,
        slot_idx: int,
        slot_key: str,
        widget_idx: int,
        windows: list[dict],
    ) -> None:
        # These widget types have no post-placement step.
        if col.widget_type in ("links", "form", "contact_info", "hours"):
            return
        window_id = self._resolve_window_id(slot_key, widget_idx, windows)
        if not window_id:
            self.warnings.append(
                f"No windowId in slot '{slot_key}' widget {widget_idx + 1} "
                f"for '{item.section_type}' — skipping."
            )
            return
        await post_place(
            col, window_id,
            self.bridge, self.body.dealer_id, self.site_id, self.folder_id,
            item.section_type, slot_idx, widget_idx,
            self._progress, self.warnings,
        )

    def _resolve_window_id(
        self, slot_key: str, widget_idx: int, windows: list[dict]
    ) -> str:
        """Read the DDC-assigned windowId from the refreshed layout, falling
        back to the client-generated ID if the refreshed layout didn't include
        this widget's slot."""
        if widget_idx < len(windows):
            wid = str((windows[widget_idx] or {}).get("windowId") or "")
            if wid:
                return wid
        fallback = self.slot_widget_ids.get(slot_key, [])
        return fallback[widget_idx] if widget_idx < len(fallback) else ""

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _progress(self, msg: str) -> None:
        await self.bridge.send_progress(self.body.dealer_id, msg)


# ── Module-level pure helpers ────────────────────────────────────────────────


def _bump_counter_from_window_id(counter: dict[str, int], window_id: str) -> None:
    """Parse the "{alias}:{type}{n}" suffix of a windowId and bump the counter
    for that widget type so client-generated IDs never collide with existing
    ones. Silently no-ops on malformed IDs (no colon or non-integer index)."""
    if ":" not in window_id:
        return
    suffix = window_id.split(":", 1)[1]  # e.g. "content1"
    for wt in PORTLET_BY_WIDGET_TYPE:
        if suffix.startswith(wt):
            try:
                idx = int(suffix[len(wt):])
            except ValueError:
                return
            counter[wt] = max(counter.get(wt, 0), idx)
            return
