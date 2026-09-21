from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Nutrition Agent"
    INTERNAL_SERVICE_TOKEN: str = ""
    DATABASE_URL: str = ""
    DATABASE_SCHEMA: str = "systemdb"
    USDA_FDC_API_KEY: str = ""


settings = Settings()
