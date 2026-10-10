"""Configuration for the Recovery Agent service."""

import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed Recovery Agent settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = Field(default="", validation_alias="RECOVERY_DATABASE_URL")
    DATABASE_SCHEMA: str = Field(
        default="recovery", validation_alias="RECOVERY_DATABASE_SCHEMA"
    )
    INTERNAL_SERVICE_TOKEN: str = "local-dev-recovery-token"
    APP_NAME: str = "Recovery Agent"
    RECOVERY_LLM_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5-nano"

    def validated_schema(self) -> str:
        """Return a safe PostgreSQL schema identifier."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.DATABASE_SCHEMA):
            raise ValueError("DATABASE_SCHEMA must be a PostgreSQL identifier")
        return self.DATABASE_SCHEMA


settings = Settings()
