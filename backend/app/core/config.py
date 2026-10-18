from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rosepsy"
    app_version: str = "0.25.0"
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

    # B39 سند جامع - فایل امن
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    download_ticket_seconds: int = 120
    # MIME های مجاز؛ فایل خارج از فهرست در قرنطینه می‌رود
    allowed_mime_types: str = (
        "application/pdf,image/png,image/jpeg,image/webp,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
        "text/plain,text/csv"
    )

    @property
    def allowed_mime_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_mime_types.split(",") if m.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cookie_secure(self) -> bool:
        # بند ۱۳.۲: در عملیات با HTTPS مقدار ENVIRONMENT=production باشد
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
