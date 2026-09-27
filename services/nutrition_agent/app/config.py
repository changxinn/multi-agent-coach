from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root_env_file() -> Path | None:
    """Find a repository-level .env for direct local execution, if present."""
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


ROOT_ENV_FILE = _find_root_env_file()

class Settings(BaseSettings):
    """Nutrition Agent settings from environment variables and a local root .env."""

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Nutrition Agent"
    INTERNAL_SERVICE_TOKEN: str = ""
    DATABASE_URL: str = Field(
        default="",
        validation_alias="NUTRITION_DATABASE_URL",
    )
    RUN_MIGRATIONS: bool = True
    USDA_FDC_API_KEY: str = ""
    NUTRITION_LLM_ENABLED: bool = True
    NUTRITION_MEAL_PLAN_LLM_ENABLED: bool = True
    NUTRITION_MEAL_PLAN_LLM_MAX_COMPLETION_TOKENS: int = 4000
    NUTRITION_LLM_DEBUG_LOG_REQUESTS: bool = True
    NUTRITION_LLM_DEBUG_LOG_RESPONSES: bool = True
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-5-nano"
    NUTRITION_LLM_REASONING_EFFORT: str = (
        "low"  # reasoning effort should be none for gpt-6-luna, low for gpt-5-nano
    )


settings = Settings()
