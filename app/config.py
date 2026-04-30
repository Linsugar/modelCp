from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Lottery LLM API"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_allowed_origins: str = "*"

    api_access_key: str = ""

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_provider_name: str = "default"
    llm_providers: str = ""
    llm_timeout_seconds: float = 60

    lottery_api_url: str = ""
    lottery_api_key: str = ""
    lottery_data_file: str = "data/lottery_results.json"
    lottery_auto_fetch: bool = True
    lottery_latest_if_date_missing: bool = True

    max_history_messages: int = 12

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
