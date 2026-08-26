"""
Application configuration using pydantic-settings.

Loads environment variables from .env file and validates them.
"""
from functools import lru_cache
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ===========================================
    # Application Settings
    # ===========================================
    APP_NAME: str = "Multi-Agent Coach API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ===========================================
    # JWT Configuration
    # ===========================================
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # ===========================================
    # Database Configuration
    # ===========================================
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "systemdb"

    # Seed admin user (created on first run)
    SEED_ADMIN_EMAIL: str = "admin@example.com"
    SEED_ADMIN_PASSWORD: str = "ChangeMe123!"
    SEED_ADMIN_NAME: str = "System Admin"

    # ===========================================
    # Session Configuration
    # ===========================================
    SESSION_EXPIRY_HOURS: int = 24

    # ===========================================
    # CORS Configuration
    # ===========================================
    FRONTEND_URL: str = "http://localhost:5174"
    ALLOWED_ORIGINS: str = "http://localhost:5174,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # ===========================================
    # LLM Configuration
    # ===========================================
    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-5-nano"

    # ===========================================
    # Internal Agent Services
    # ===========================================
    # Disabled by default to preserve the single-process development fallback.
    USE_RECOVERY_AGENT_SERVICE: bool = False
    RECOVERY_AGENT_URL: str = "http://localhost:8001"
    INTERNAL_SERVICE_TOKEN: str = ""

    # ===========================================
    # AWS Configuration (Optional for Production)
    # ===========================================
    AWS_REGION: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    S3_PREFIX: str = "chat-history"

    @property
    def is_aws_configured(self) -> bool:
        """Check if AWS credentials are configured."""
        return bool(
            self.AWS_REGION and self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY
        )

    # ===========================================
    # Redis Configuration (Optional for Production)
    # ===========================================
    REDIS_URL: Optional[str] = None

    @property
    def is_redis_configured(self) -> bool:
        """Check if Redis is configured."""
        return bool(self.REDIS_URL)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application settings
    """
    return Settings()
