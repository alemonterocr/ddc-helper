from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-pro"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000


def load_settings() -> Settings:
    return Settings()
