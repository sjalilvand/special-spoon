"""فاز ۴۳ - ADR-05 گام ۱: کلاینت Redis مشترک (زیرساخت شمارنده‌های سقف نرخ).

طرح گام ۱ سند ADR-05: «Redis برای شمارنده‌ها هم استفاده می‌شود — بدون
مؤلفه جدید» (همان Redis آیندهٔ Broker صف کار ADR-02). الگوی پروژه
(D02/D03/D07/B28/ADR-04) رعایت می‌شود:

- ``rate_limit_redis_url`` خالی → غیرفعال (پیش‌فرض توسعه/آزمون؛ هیچ مسیری
  بسته نمی‌شود و رفتار فعلی حفظ می‌ماند)؛
- نبود کتابخانه ``redis-py`` یا خطای اتصال → ``None`` با هشدار؛ فراخواننده
  fail-open است — بند ۶ سند ADR-05: «ترجیح دسترس‌پذیری بر سقف‌گیری دقیق،
  با ثبت هشدار»؛
- شکست اتصال کش نمی‌شود؛ پس از فاصلهٔ کوتاه دوباره تلاش می‌شود تا با
  بازگشت Redis، سقف‌گیری بدون ری‌استارت سرور برقرار شود؛
- کلاینت در سطح فرایند یک‌بار ساخته و بازمصرف می‌شود (استخر اتصال
  redis-py)؛ آدرس Redis هرگز به کلاینت/پاسخ API نمی‌رود.
"""
from __future__ import annotations

import logging
import time

from app.core.config import get_settings

logger = logging.getLogger("rosepsy.redis")

_client = None                     # redis.Redis — نمونه بازمصرف‌شونده
_client_url: str | None = None
_last_bind_failure: float = 0.0
_BIND_RETRY_SECONDS = 30.0         # فاصله تلاش دوباره برای برقراری اتصال


def get_redis():
    """کلاینت مشترک Redis؛ ``None`` یعنی سقف‌گیری فعلاً در دسترس نیست.

    فراخواننده (میان‌افزار سقف نرخ) در این حالت درخواست را بدون سقف عبور
    می‌دهد (fail-open) — قرارداد بند ۶ سند ADR-05.
    """
    global _client, _client_url, _last_bind_failure

    url = get_settings().rate_limit_redis_url
    if not url:
        return None
    if _client is not None and _client_url == url:
        return _client
    # شکست اخیر اتصال → تا پایان فاصله بازگشت، بدون تلاش مجدد None بده
    if time.monotonic() - _last_bind_failure < _BIND_RETRY_SECONDS:
        return None
    try:
        import redis  # redis-py — وابستگی سقف نرخ (گام ۱ طرح ADR-05)

        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            health_check_interval=30,
        )
        client.ping()
    except Exception as exc:  # نبود کتابخانه/سرویس → fail-open با هشدار
        _last_bind_failure = time.monotonic()
        logger.warning(
            "Redis برای سقف نرخ در دسترس نیست (%s)؛ سقف‌گیری موقتاً fail-open است",
            exc.__class__.__name__,
        )
        return None
    _client = client
    _client_url = url
    return client


def reset_client() -> None:
    """ریست وضعیت ماژول — فقط برای آزمون‌ها."""
    global _client, _client_url, _last_bind_failure
    _client = None
    _client_url = None
    _last_bind_failure = 0.0
