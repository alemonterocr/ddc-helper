from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.adapters.outbound.llm_factory import LLMFactory
from src.domain.errors import LLMAuthError
from src.domain.models import LLMProvider
from src.infrastructure.config import Settings

from .dependencies import get_llm_factory

router = APIRouter()


class ConfigureAPIKeyRequest(BaseModel):
    provider: LLMProvider
    api_key: str


class ConfigureAPIKeyResponse(BaseModel):
    valid: bool
    provider: LLMProvider
    error: str | None = None


@router.post("/config/api-key", response_model=ConfigureAPIKeyResponse)
async def configure_api_key(
    body: ConfigureAPIKeyRequest,
    factory: LLMFactory = Depends(get_llm_factory),
) -> ConfigureAPIKeyResponse:
    model = _resolve_model_name(body.provider)

    try:
        await factory.validate_and_register(
            provider=body.provider,
            api_key=body.api_key,
            model=model,
        )
        return ConfigureAPIKeyResponse(valid=True, provider=body.provider)
    except LLMAuthError as error:
        return ConfigureAPIKeyResponse(
            valid=False,
            provider=body.provider,
            error=str(error),
        )


def _resolve_model_name(provider: LLMProvider) -> str:
    settings = Settings()
    model_map = {
        LLMProvider.ANTHROPIC: settings.anthropic_model,
        LLMProvider.GEMINI: settings.gemini_model,
        LLMProvider.DEEPSEEK: settings.deepseek_model,
    }
    return model_map[provider]
