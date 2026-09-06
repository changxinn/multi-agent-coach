"""Configuration for the Nutrition Agent service."""
import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed Nutrition Agent settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/systemdb"
    DATABASE_SCHEMA: str = "systemdb"
    NUTRITION_INTERNAL_SERVICE_TOKEN: str = ""
    APP_NAME: str = "Nutrition Agent"
    NUTRITION_LLM_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5-nano"
    USDA_FDC_API_KEY: str = ""
    FOOD_CACHE_FRESH_DAYS: int = Field(default=30, ge=1, le=365)
    FOOD_CACHE_MAX_STALE_DAYS: int = Field(default=180, ge=1, le=3650)
    USDA_REFRESH_SUPPRESSION_MINUTES: int = Field(default=15, ge=1, le=1440)
    USDA_CONNECT_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0, le=30)
    USDA_READ_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, le=60)
    USDA_REQUEST_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, le=120)
    USDA_MAX_RESULTS: int = Field(default=50, ge=1, le=50)
    USDA_REQUESTS_PER_MINUTE: int = Field(default=30, ge=1, le=1000)
    USDA_REQUESTS_PER_HOUR: int = Field(default=1000, ge=1, le=10000)
    USDA_REQUESTS_PER_DAY: int = Field(default=10000, ge=1, le=100000)

    def validated_schema(self) -> str:
        """Return a safe PostgreSQL schema identifier."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.DATABASE_SCHEMA):
            raise ValueError("DATABASE_SCHEMA must be a PostgreSQL identifier")
        return self.DATABASE_SCHEMA


settings = Settings()
