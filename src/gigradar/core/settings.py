"""Application settings and environment configuration."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GigRadar runtime settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini LLM configuration
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    llm_model_scorer: str = Field(default="gemini-2.5-flash", alias="LLM_MODEL_SCORER")
    llm_model_pitch: str = Field(default="gemini-2.5-flash", alias="LLM_MODEL_PITCH")
    llm_daily_call_budget: int = Field(default=200, alias="LLM_DAILY_CALL_BUDGET")
    llm_max_rpm: int = Field(default=10, alias="LLM_MAX_RPM")

    # Telegram Bot configuration
    telegram_bot_token: SecretStr | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_chat_id: int | None = Field(default=None, alias="TELEGRAM_ALLOWED_CHAT_ID")

    # Storage
    database_url: str = Field(
        default="sqlite+aiosqlite:///gigradar.db",
        alias="DATABASE_URL",
    )

    # Filtering & pipeline
    score_threshold: int = Field(default=65, alias="SCORE_THRESHOLD")
    auto_submit: bool = Field(default=False, alias="AUTO_SUBMIT")

    # Polling intervals
    poll_interval_seconds_mostaql: int = Field(default=120, alias="POLL_INTERVAL_SECONDS_MOSTAQL")
    poll_interval_seconds_khamsat: int = Field(default=180, alias="POLL_INTERVAL_SECONDS_KHAMSAT")
    poll_interval_seconds_freelancer: int = Field(
        default=120,
        alias="POLL_INTERVAL_SECONDS_FREELANCER",
    )

    # Freelancer.com specific
    freelancer_oauth_token: SecretStr | None = Field(
        default=None,
        alias="FREELANCER_OAUTH_TOKEN",
    )
    freelancer_monthly_bid_limit: int = Field(
        default=100,
        alias="FREELANCER_MONTHLY_BID_LIMIT",
    )

    # Logging and paths
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")
    config_dir: Path = Field(default=Path("config"), alias="CONFIG_DIR")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached application settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
