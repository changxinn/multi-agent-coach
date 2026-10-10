from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docker-compose.yml").is_file():
            return parent
    return Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_repository_root() / ".env", extra="ignore"
    )

    APP_NAME: str = "Training Agent"
    INTERNAL_SERVICE_TOKEN: str = ""
    DATABASE_URL: str = Field(default="", validation_alias="TRAINING_DATABASE_URL")
    RUN_MIGRATIONS: bool = True
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5-nano"


settings = Settings()
