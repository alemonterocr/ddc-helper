from enum import StrEnum

from pydantic import BaseModel


class LLMProvider(StrEnum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"


class APIKeyConfig(BaseModel):
    provider: LLMProvider
    api_key: str
