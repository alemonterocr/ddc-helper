from fastapi import Request

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.adapters.outbound.llm_factory import LLMFactory


def get_llm_factory(request: Request) -> LLMFactory:
    return request.app.state.llm_factory


def get_bridge(request: Request) -> WsBridgeAdapter:
    return request.app.state.bridge
