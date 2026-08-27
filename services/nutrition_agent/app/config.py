"""Configuration for the Nutrition Agent service."""
import re

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed Nutrition Agent settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/systemdb"
    DATABASE_SCHEMA: str = "systemdb"
    INTERNAL_SERVICE_TOKEN: str = "local-dev-nutrition-token"
    APP_NAME: str = "Nutrition Agent"
    NUTRITION_LLM_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5-nano"
    USDA_FDC_API_KEY: str = "fqdZaUBgSbdb10QEp9QMbCqhAVke1VRzecNmRKkK"

    def validated_schema(self) -> str:
        """Return a safe PostgreSQL schema identifier."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.DATABASE_SCHEMA):
            raise ValueError("DATABASE_SCHEMA must be a PostgreSQL identifier")
        return self.DATABASE_SCHEMA


settings = Settings()
