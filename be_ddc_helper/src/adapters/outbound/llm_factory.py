from src.adapters.outbound.anthropic.anthropic_llm_adapter import AnthropicLLMAdapter
from src.adapters.outbound.deepseek.deepseek_llm_adapter import DeepSeekLLMAdapter
from src.adapters.outbound.gemini.gemini_llm_adapter import GeminiLLMAdapter
from src.domain.errors import LLMAuthError, ProviderNotConfiguredError
from src.domain.models import LLMProvider
from src.ports.outbound import LLMPort


class LLMFactory:
    def __init__(self) -> None:
        self._adapters: dict[LLMProvider, LLMPort] = {}

    def get(self, provider: LLMProvider) -> LLMPort:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise ProviderNotConfiguredError(
                f"No API key configured for provider '{provider}'. "
                "Call POST /config/api-key first."
            )
        return adapter

    def is_configured(self, provider: LLMProvider) -> bool:
        return provider in self._adapters

    async def validate_and_register(self, provider: LLMProvider, api_key: str, model: str) -> None:
        adapter = _build_adapter(provider, api_key, model)
        await adapter.validate()
        self._adapters[provider] = adapter

    def register_from_env(self, provider: LLMProvider, api_key: str, model: str) -> None:
        if api_key:
            self._adapters[provider] = _build_adapter(provider, api_key, model)


def _build_adapter(provider: LLMProvider, api_key: str, model: str) -> LLMPort:
    if provider == LLMProvider.ANTHROPIC:
        return AnthropicLLMAdapter(api_key=api_key, model=model)
    if provider == LLMProvider.GEMINI:
        return GeminiLLMAdapter(api_key=api_key, model=model)
    if provider == LLMProvider.DEEPSEEK:
        return DeepSeekLLMAdapter(api_key=api_key, model=model)
    raise ValueError(f"Unknown provider: {provider}")
