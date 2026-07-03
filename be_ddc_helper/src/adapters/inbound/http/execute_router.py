from fastapi import APIRouter, Depends

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.application.migration.execute_orchestrator import MigrationExecutor

from .dependencies import get_bridge
from .execute_dtos import ExecuteRequest, ExecuteResponse

# Re-export DTOs so external imports of
# `from src.adapters.inbound.http.execute_router import ExecuteRequest, ...`
# keep working after the split into execute_dtos.py.
from .execute_dtos import (  # noqa: F401
    ButtonDTO,
    ColumnWidgetDTO,
    SectionPlanItemDTO,
)

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
async def execute_migration(
    body: ExecuteRequest,
    bridge: WsBridgeAdapter = Depends(get_bridge),
) -> ExecuteResponse:
    return await MigrationExecutor(body, bridge).run()
