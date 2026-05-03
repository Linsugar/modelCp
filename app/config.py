from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Lottery LLM API"
    app_host: str = "0.0.0.0"
    app_port: int = 8549

    cors_allowed_origins: str = "*"
    log_timezone: str = "Asia/Shanghai"

    # 前端请求密钥。前端请求头传：X-API-Key: Tang
    api_access_key: str = "Tang"

    # 单模型配置。把你的真实模型 key 填在 llm_api_key。
    llm_base_url: str = "https://zenmux.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek/deepseek-v4-pro-free"
    llm_provider_name: str = "default"
    llm_timeout_seconds: float = 60

    # 多模型配置。配置后会覆盖上面的单模型配置。
    # 示例：
    # [
    #   {"name": "model-a", "base_url": "https://api.openai.com/v1", "api_key": "key-a", "model": "gpt-4o-mini"},
    #   {"name": "model-b", "base_url": "https://example.com/v1", "api_key": "key-b", "model": "qwen-plus"}
    # ]
    llm_providers: str = ""

    # 开奖数据配置。lottery_api_url 为空时会尝试本地文件和内置自动开奖源。
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
