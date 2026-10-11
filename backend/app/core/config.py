from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rosepsy"
    app_version: str = "0.2.0"
    api_prefix: str = "/api/v1"
    environment: str = "production"

    database_url: str = "postgresql+psycopg://rosepsy:change_me@localhost:5432/rosepsy"

    # احراز هویت - بند ۴.۲ سند
    auth_secret_key: str = "dev-only-insecure-key-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    activation_token_expire_hours: int = 24
    login_max_attempts: int = 5
    login_attempt_window_minutes: int = 15

    @property
    def cookie_secure(self) -> bool:
        # بند ۱۳.۲: در عملیات با HTTPS مقدار ENVIRONMENT=production باشد
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
