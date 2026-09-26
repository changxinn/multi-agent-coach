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
    NUTRITION_MEAL_PLAN_LLM_ENABLED: bool = True
    NUTRITION_MEAL_PLAN_LLM_MAX_COMPLETION_TOKENS: int = 4000
    NUTRITION_LLM_DEBUG_LOG_REQUESTS: bool = True
    NUTRITION_LLM_DEBUG_LOG_RESPONSES: bool = True
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    LLM_MODEL: str = "gpt-5-nano"
    NUTRITION_LLM_REASONING_EFFORT: str = (
        "low"  # reasoning effort should be none for gpt-6-luna, low for gpt-5-nano
    )


settings = Settings()
