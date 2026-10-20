"""فاز ۴۳ - ADR-05 گام ۲: پنجره لغزان Redis برای سقف نرخ سراسری.

الگوریتم (بخش گام ۱ طرح: «پیاده‌سازی کوتاه با redis-py» — بدون وابستگی
جدید در کد اجرا): پنجره لغزان بر پایه ZSET — هر hit یک عضو با نمرهٔ
میلی‌ثانیهٔ زمان؛ پیش از شمارش، اعضای قدیمی‌تر از پنجره پاک می‌شوند؛ عبور
از سقف یعنی ``ZCARD > limit``. همهٔ دستورهای ثبت hit در یک pipeline اتمی
اجر می‌شوند تا Redis به‌عنوان تک‌منبع حقیقت بین نمونه‌ها شمارش هم‌گرا
بدهد (شرط آستانهٔ بند ۴ سند: استقرار چندنمونه‌ای).

قرارداد خطا: هر خطای Redis به فراخواننده (میان‌افزار) برمی‌گردد تا
fail-open شود — بند ۶ سند ADR-05. در حالت عبور از سقف، ``retry_after``
(ثانیه تا خروج قدیمی‌ترین عضو از پنجره) پر می‌شود تا هدر استاندارد
``Retry-After`` ساخته شود.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RateDecision:
    """نتیجه یک hit روی سطل سقف نرخ."""

    limit: int
    remaining: int
    exceeded: bool
    retry_after: int | None = None  # فقط در حالت exceeded — ثانیه


def sliding_window_hit(
    rc,
    key: str,
    *,
    limit: int,
    window_seconds: int,
    now_ms: int | None = None,
) -> RateDecision:
    """یک hit روی سطل ``key`` ثبت می‌کند و تصمیم سقف را برمی‌گرداند.

    ``now_ms`` برای آزمون‌ها تزریق‌شدنی است (پنجره لغزان با ساعتِ
    دیوارکاری مستقل از فیک Redis آزمون می‌شود — زمان واقعی استفاده می‌شود
    مگر در آزمون).
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    window_ms = max(1, int(window_seconds)) * 1000
    cutoff = now_ms - window_ms
    # عضو یکتا (حتی در هم‌میل‌ثانیه) تا شمارش درست بماند
    member = f"{now_ms}:{uuid.uuid4().hex}"

    pipe = rc.pipeline(transaction=True)
    pipe.zremrangebyscore(key, "-inf", cutoff)
    pipe.zadd(key, {member: now_ms})
    pipe.zcard(key)
    pipe.pexpire(key, window_ms)  # GC کلیدهای بدون ترافیک (یادسپاری ≥ پنجره)
    results = pipe.execute()
    count = int(results[2])

    if count <= limit:
        return RateDecision(limit=limit, remaining=max(0, limit - count), exceeded=False)

    # قدیمی‌ترین عضو هنوز داخل پنجره است؛ تا خروج آن از پنجره باید صبر کرد
    oldest = rc.zrange(key, 0, 0, withscores=True)
    retry_after = window_seconds
    if oldest:
        oldest_score = int(float(oldest[0][1]))
        retry_after = max(1, math.ceil((oldest_score + window_ms - now_ms) / 1000))
    return RateDecision(limit=limit, remaining=0, exceeded=True, retry_after=retry_after)
