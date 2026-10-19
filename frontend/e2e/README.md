# آزمون E2E — گام اول (فاز ۳۷، دسته ۳/۴/۶ سند جامع)

دود ساده مسیرهای حیاتی با **Playwright + Chromium**: سلامت API، هدایت
احراز هویت، ورود موفق و بارگذاری اعلان‌ها. این پوشه **جزو build نیست**
(خارج از `tsconfig`/`vite`) و اجرای آن نیازمند سرویس‌های در حال اجراست.

## پیش‌نیازها (یک‌بار)

```bash
cd frontend
npm i -D @playwright/test          # با legacy-peer-deps موجود در .npmrc سازگار است
npx playwright install chromium    # اگر مرورگر نصب نباشد
```

## اجرا

پیش‌نیاز: بک‌اند روی 8000 و فرانت (dev یا preview) روی 5173 در حال اجرا باشند.

```bash
# ترمینال ۱ — بک‌اند
cd backend && uvicorn app.main:app --port 8000

# ترمینال ۲ — فرانت
cd frontend && npm run dev

# ترمینال ۳ — آزمون
cd frontend
E2E_USER=admin E2E_PASS=<رمز> npx playwright test
```

## متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:5173` | آدرس فرانت |
| `E2E_API_URL` | `http://localhost:8000` | آدرس بک‌اند (برای آزمون سلامت) |
| `E2E_USER` / `E2E_PASS` | — | کاربر آزمون؛ بدون آن‌ها فقط آزمون‌های بی‌احراز هویت اجرا می‌شوند |

## گام‌های بعدی پیشنهادی

- سناریوهای کلیدی کسب‌وکار: رزرو نوبت → پرداخت sandbox → سفارش؛
  دوره رایگان → ثبت‌نام؛ آزمون → گواهی (دسته E2E کامل سند)؛
- افزودن به CI با سرویس‌های compose (db + api + web + playwright)؛
- Contract با Schemathesis و Performance با k6 (آیتم‌های باقی‌مانده بدهی فنی).
