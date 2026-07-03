import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.inbound.http.analyze_router import router as analyze_router
from src.adapters.inbound.http.analyze_deterministic_router import router as analyze_deterministic_router
from src.adapters.inbound.http.config_router import router as config_router
from src.adapters.inbound.http.execute_router import router as execute_router
from src.adapters.inbound.http.health_router import router as health_router
from src.adapters.inbound.http.parse_nav_router import router as parse_nav_router
from src.adapters.inbound.http.parse_staff_router import router as parse_staff_router
from src.adapters.inbound.http.execute_staff_router import router as execute_staff_router
from src.adapters.inbound.http.salesforce_router import router as salesforce_router
from src.adapters.inbound.http.translations_router import router as translations_router
from src.adapters.inbound.websocket.connection_registry import ConnectionRegistry
from src.adapters.inbound.websocket.ws_handler import router as ws_router
from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter
from src.adapters.outbound.llm_factory import LLMFactory
from src.domain.models import LLMProvider
from src.infrastructure.config import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()

    # Shared singletons
    registry = ConnectionRegistry()
    bridge = WsBridgeAdapter(registry)
    factory = LLMFactory()

    # Auto-register any providers that have keys in .env
    factory.register_from_env(LLMProvider.ANTHROPIC, settings.anthropic_api_key, settings.anthropic_model)
    factory.register_from_env(LLMProvider.GEMINI, settings.gemini_api_key, settings.gemini_model)
    factory.register_from_env(LLMProvider.DEEPSEEK, settings.deepseek_api_key, settings.deepseek_model)

    app.state.registry = registry
    app.state.bridge = bridge
    app.state.llm_factory = factory

    yield


app = FastAPI(title="DDC Migration Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(config_router)
app.include_router(analyze_router)
app.include_router(analyze_deterministic_router)
app.include_router(execute_router)
app.include_router(parse_nav_router)
app.include_router(parse_staff_router)
app.include_router(execute_staff_router)
app.include_router(salesforce_router)
app.include_router(translations_router)
app.include_router(ws_router)
