from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Nutrition Agent settings loaded from the service-local environment file."""

    model_config = SettingsConfigDict(
        env_file=SERVICE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Nutrition Agent"
    INTERNAL_SERVICE_TOKEN: str = ""
    DATABASE_URL: str = ""
    RUN_MIGRATIONS: bool = False
    USDA_FDC_API_KEY: str = ""
    NUTRITION_LLM_ENABLED: bool = True
    NUTRITION_LLM_DEBUG_LOG_REQUESTS: bool = False
    NUTRITION_LLM_DEBUG_LOG_RESPONSES: bool = False
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5-nano"
    NUTRITION_LLM_REASONING_EFFORT: str = "low"


settings = Settings()
