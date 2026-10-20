"""Runtime configuration, read from SHOMER_* env vars (and .env for local dev)."""

from functools import cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHOMER_", env_file=".env", extra="ignore")

    # Primary LLM: any OpenAI-compatible endpoint (OpenRouter by default).
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "openai/gpt-oss-120b"
    # Fallback LLM, e.g. Ollama's OpenAI-compatible endpoint. Unset = no fallback.
    llm_fallback_base_url: str | None = None
    llm_fallback_model: str | None = None
    llm_timeout_seconds: float = 60.0

    # Agent loop guardrails.
    max_steps: int = Field(default=8, ge=1, le=30)
    max_tool_output_chars: int = Field(default=8_000, ge=500)
    max_concurrent_investigations: int = Field(default=2, ge=1)
    dedupe_window_seconds: int = Field(default=900, ge=0)

    prometheus_url: str = "http://prometheus-operated.monitoring.svc:9090"
    slack_webhook_url: SecretStr | None = None
    # Bearer token Alertmanager must send. Unset = no auth (local dev only).
    webhook_token: SecretStr | None = None

    log_level: str = "INFO"
    log_json: bool = True


@cache
def get_settings() -> Settings:
    return Settings()
