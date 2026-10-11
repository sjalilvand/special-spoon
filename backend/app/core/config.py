from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rosepsy"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    environment: str = "production"

    database_url: str = "postgresql+psycopg://rosepsy:change_me@localhost:5432/rosepsy"

    # احراز هویت - فاز ۲ (بند ۴.۲ سند): Access Token کوتاه‌عمر
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
