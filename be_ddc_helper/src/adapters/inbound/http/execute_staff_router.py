"""POST /execute-staff — runs StaffExecutor end-to-end.

Steps (see StaffExecutor for details):
  1. ensure_page                 — create / resolve DDC page
  2. resolve_staff_folder        — Do Not Delete / {project_root} / Staff
  3. upload_photos               — per-staff via existing upload_media_image tool
  4. inject_staff_listing        — POST ws-staff-listing itemlist via new tool
"""

from fastapi import APIRouter, Depends

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.application.staff_migration.staff_executor import StaffExecutor

from .dependencies import get_bridge
from .staff_dtos import ExecuteStaffRequest, ExecuteStaffResponse

router = APIRouter()


@router.post("/execute-staff", response_model=ExecuteStaffResponse)
async def execute_staff(
    body: ExecuteStaffRequest,
    bridge: WsBridgeAdapter = Depends(get_bridge),
) -> ExecuteStaffResponse:
    return await StaffExecutor(body, bridge).run()
