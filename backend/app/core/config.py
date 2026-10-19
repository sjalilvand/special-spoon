from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rosepsy"
    app_version: str = "0.37.0"
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

    # فاز ۳۷ - ADR-04: Object Storage پلاگین‌پذیر (تصمیم سند: MinIO/S3)
    # همان الگوی D02/D03/D07/B28:
    # storage_backend = "local" (پیش‌فرض: دایرکتوری volume، بدون کلید) | "s3"
    # آداپتور s3 فقط با endpoint + bucket + access_key + secret_key فعال می‌شود؛
    # نبود هر کدام یا خطای سرویس → fallback به local (fail-soft) با گزارش شفاف؛
    # کلیدها هرگز به کلاینت/لاگ/پاسخ API نمی‌روند.
    storage_backend: str = "local"
    s3_endpoint_url: str = ""   # نمونه تولید: http://minio:9000
    s3_bucket: str = "rosepsy-files"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_connect_timeout_seconds: float = 3.0

    # فاز ۲۶ - B09: نگهداشت موقت اسلات
    booking_hold_minutes: int = 10
    booking_hold_max_per_ip: int = 5

    # فاز ۲۶ - B02-lite: کد یک‌بارمصرف
    # در حالت توسعه کد در پاسخ API و لاگ نمایش داده می‌شود (آماده‌سازی D04)
    otp_dev_mode: bool = True
    otp_code_ttl_seconds: int = 180
    otp_max_attempts: int = 3
    otp_request_max: int = 3
    otp_request_window_seconds: int = 600
    otp_verify_token_seconds: int = 600
    booking_require_otp: bool = False  # سخت‌گیری کامل پس از تصمیم D04

    # فاز ۲۷ - B39-plus: آنتی‌ویروس واقعی ClamAV
    # clamav_host خالی = غیرفعال؛ در docker compose مقدار «clamav» است
    clamav_enabled: bool = True
    clamav_host: str = ""
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 10.0
    # حذف EXIF/GPS و فراداده تصاویر پیش از ذخیره
    strip_image_metadata: bool = True

    # فاز ۲۷ - B12+: خروجی اعلان به ایمیل (تصمیم D04 - SMTP)
    # smtp_enabled=False → صف ایمیل ساخته می‌شود ولی «غیرفعال» علامت می‌خورد
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "rosepsy@clinic.local"
    smtp_use_tls: bool = True   # STARTTLS
    smtp_use_ssl: bool = False  # SMTPS 465
    email_outbox_max_attempts: int = 5
    notifications_email_enabled: bool = True

    # B39 سند جامع - فایل امن (با آداپتور ADR-04: local پیش‌فرض، s3 برای تولید)
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    download_ticket_seconds: int = 120

    # فاز ۲۹ - B10/B11: سفارش و پرداخت (تصمیم D02: درگاه پلاگین‌پذیر)
    # sandbox = درگاه شبیه‌ساز توسعه/آزمون؛ zarinpal = درگاه پیشنهادی تولید
    payment_gateway: str = "sandbox"
    # آدرس عمومی سامانه برای ساخت callback درگاه‌های واقعی
    public_base_url: str = "http://localhost:5173"
    # زرین‌پال REST v4؛ merchant_id خالی = درگاه غیرفعال
    zarinpal_merchant_id: str = ""
    zarinpal_sandbox: bool = True
    # فاز ۳۲ - B40 + تصمیم D03: نقشه شعب با سرویس نقشه پلاگین‌پذیر
    # همان الگوی D02: پیش‌فرض OSM/Leaflet بدون کلید؛ نشنال/Map.ir برای تولید
    # map_provider = "osm" | "neshan" | "mapir"
    map_provider: str = "osm"
    # کلیدهای سرویس نقشه؛ خالی = درگاه غیرفعال (کلید هرگز به کلاینت نمی‌رود)
    neshan_api_key: str = ""
    mapir_api_key: str = ""

    # فاز ۳۵ - B25–B27 + تصمیم D07: دستیار هوشمند پلاگین‌پذیر
    # ai_provider = "rule" (پیش‌فرض: قاعده‌محور، بدون کلید، قطعی) | "llm"
    ai_provider: str = "rule"
    # کلید سرویس AI؛ خالی = fallback به rule (fail-soft)؛ کلید هرگز به کلاینت/لاگ نمی‌رود
    ai_api_key: str = ""

    # فاز ۳۶ - B28: یکپارچه‌سازی‌های بیرونی — سرویس پیامک پلاگین‌پذیر
    # همان الگوی D02/D03/D07:
    # sms_provider = "log" (پیش‌فرض: توسعه/آزمون، بدون کلید، قطعی) | "kavenegar" | "smsir"
    # sms_enabled=False → ردیف‌های صف به «disabled» علامت می‌خورند (شفافیت DPO)
    sms_enabled: bool = False
    sms_provider: str = "log"
    # کلید سرویس پیامک؛ خالی = fallback به log (fail-soft)؛ کلید هرگز به کلاینت/لاگ نمی‌رود
    sms_api_key: str = ""
    sms_sender: str = ""
    sms_max_attempts: int = 5
    # کپی اعلان‌های درون‌برنامه‌ای به پیامک (فقط گیرنده دارای موبایل)
    notifications_sms_enabled: bool = True

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
