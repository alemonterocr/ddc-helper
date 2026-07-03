import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from src.domain.deterministic_migrate import migrate

router = APIRouter()
logger = logging.getLogger(__name__)


class DeterministicAnalyzeRequest(BaseModel):
    dom_skeleton: dict


class DeterministicAnalyzeResponse(BaseModel):
    plan: list[dict]


@router.post("/analyze-deterministic", response_model=DeterministicAnalyzeResponse)
def analyze_deterministic(body: DeterministicAnalyzeRequest) -> DeterministicAnalyzeResponse:
    plan = migrate(body.dom_skeleton)
    logger.info("Deterministic algo output:\n%s", json.dumps(plan, indent=2))
    return DeterministicAnalyzeResponse(plan=plan)
