# آزمون Performance — k6 (فاز ۳۹)

سناریوهای بار روی **قرارداد v2** (پاکت ADR-03): ورود واقعی + خواندن
فهرست‌های پرتکرار + پروفایل کاربر. آستانه‌ها براساس SLO سند جامع:
`p95 < 800ms`، `نرخ خطا < 2%` (و برای دود سخت‌گیرتر: `p95 < 500ms`).

## اسکریپت‌ها

| فایل | نقش | سناریو |
|---|---|---|
| `smoke.js` | دود — صحت قرارداد + عملکرد پایه | ۱ کاربر × ۱۲ تکرار؛ بررسی پاکت `{data, meta}` و `meta.pagination` در پاسخ‌ها |
| `load.js` | بار — رشد پله‌ای | ramping-vus: ۱→۵→۱۰→۲۰ کاربر مجازی (۱۰ دقیقه‌نامه ۱۰۰ ثانیه‌ای) |

مسیرهای آزموده‌شده (همه v2): `POST /auth/login`، `GET /users`،
`GET /notifications` (پاسخ intact)، `GET /auth/me` (پاسخ intact)،
`GET /specialties`. مبدأ خواندن فهرست‌ها با کاربر مدیر آزمون است.

## اجرا

```bash
# پیش‌نیاز: بک‌اند در حال اجرا + کاربر آزمون (مثل create_admin.py)
k6 run -e BASE_URL=http://127.0.0.1:8000 \
       -e E2E_USER=e2eadmin -e E2E_PASS='<رمز>' \
       perf/smoke.js --summary-export=perf/results/smoke-summary.json

k6 run -e BASE_URL=http://127.0.0.1:8000 \
       -e E2E_USER=e2eadmin -e E2E_PASS='<رمز>' \
       perf/load.js --summary-export=perf/results/load-summary.json
```

k6 یا از باینری رسمی (`grafana/k6`) یا از ایمیج `grafana/k6` در Docker
اجرا شود؛ نسخه مرجع این سند: **k6 v0.57.0**.

## بیس‌لاین ثبت‌شده (فاز ۳۹ — ۲۰۲۶-۱۰-۱۹)

محیط: لپ‌تاپ توسعه — FastAPI/uvicorn تک‌فرایند + PostgreSQL 16 محلی
(pg_keeper)، شبکه لوکال، بدون گرم‌کردن حرفه‌ای. اعداد «مرجع مقایسه»
هستند نه سقف مطلق؛ بازتولید روی استقرار هدف باید در گزارش انتشار ثبت شود.

| سناریو | درخواست‌ها | نرخ | خطا | p50 | p95 | max | آستانه |
|---|---|---|---|---|---|---|---|
| smoke (۱ VU × ۱۲) | 61 | — | 0% | 7ms | 150ms | 173ms | p95<500ms ✅ |
| load (۱→۲۰ VU) | 6,265 | 62.4 req/s | 0% | 16ms | **45ms** | 144ms | p95<800ms ✅ |

- `checks` در هر دو اجرا **۱۰۰٪** — شامل راستی‌آزمایی پاکت v2
  (`data.access_token`، `meta.pagination.total`، حفظ `{items, unread}`
  اعلان‌ها و `{username,...}` پروفایل در `data`)؛ یعنی بار هم قرارداد
  ADR-03 را تأیید می‌کند.
- خلاصه‌های JSON: `perf/results/smoke-summary.json` و `load-summary.json`.
- نکته نقش‌ها: مسیرهای «پرونده/کارتابل» برای SYSTEM_ADMIN عمداً 403
  می‌دهند (بند ماتریس دسترسی) — در سناریوها به‌جای آن‌ها از مسیرهای
  مجاز مدیر استفاده شده است.
