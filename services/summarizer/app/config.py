from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Summarizer Agent"
    INTERNAL_SERVICE_TOKEN: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5-nano"


settings = Settings()
