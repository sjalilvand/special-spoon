# Rosepsy — سامانه مشاوره روان‌شناختی سازمانی

پیاده‌سازی سند تحلیل نیازمندی‌ها (نسخه ۲.۰ — فرم مبنا RS-PS-04-01).
نسخه اولیه یک‌سازمانی: PostgreSQL + FastAPI + React/Vite + Docker Compose + Nginx.

## پیش‌نیازها

- Docker Desktop (شامل Docker Compose v2) — حتماً اجرا باشد
- Git

## راه‌اندازی عملیاتی

1) تنظیمات محیط (اسکریپت‌ها این کار را خودکار انجام می‌دهند؛ برای دستی):

    Copy-Item .env.example .env
    # مقادیر POSTGRES_PASSWORD و AUTH_SECRET_KEY را تصادفی کنید (در DATABASE_URL هم)

2) ساخت و اجرا:

    docker compose build
    docker compose up -d db
    docker compose run --rm migrate
    docker compose up -d

3) ایجاد مدیر اولیه (فرمان امن — بند ۴.۲ سند):

    docker compose run --rm api python create_admin.py

    نام کاربری و رمز تصادفی فقط یک بار چاپ می‌شود؛ آن را در جای امن ذخیره کنید.
    در اولین ورود، تغییر رمز الزامی است (must_change_password).

4) دسترسی:

    - وب:          http://localhost:8080
    - مستندات API:  http://localhost:8080/api/v1/docs

نکته: مقدار ENVIRONMENT=development فقط برای تست محلی روی HTTP است.
پیش از ورود داده واقعی: HTTPS فعال شود و ENVIRONMENT=production قرار گیرد
(Cookie مربوط به Refresh Token در production فقط Secure ارسال می‌شود).

## توسعه

    docker compose -f compose.dev.yml up -d --build db api
    docker compose -f compose.dev.yml run --rm api alembic upgrade head
    cd frontend
    npm install
    npm run dev

    وب توسعه: http://localhost:5173  (پروکسی /api به http://localhost:8000)

## پشتیبان‌گیری

    docker compose --profile ops run --rm backup

خروجی در پوشه backups/ ذخیره می‌شود.
طبق بند ۱۳.۱ سند، پشتیبان باید به مقصد جداگانه از سرور اصلی نیز منتقل شود.

## بازیابی (نمونه)

    docker cp backups\rosepsy_db_<TIMESTAMP>.dump rosepsy-db-1:/tmp/b.dump
    docker compose exec db pg_restore -U rosepsy -d rosepsy --clean --if-exists /tmp/b.dump

## وضعیت فازها (بند ۱۶ سند)

- [x] فاز ۱: اسکلت FastAPI، React، PostgreSQL و Docker
- [x] فاز ۲: ورود، نقش‌ها، مدیر اولیه و مدیریت حساب
- [ ] فاز ۳: مشاوران، متقاضیان و سه قالب اکسل
- [x] فاز ۴: تشکیل پرونده، رضایت و تخصیص
- [x] فاز ۵: فرم ثابت نسخه‌دار و ثبت ارزیابی
- [x] فاز ۶: نوبت، جلسه و کارتابل مشاور
- [x] فاز ۷: کارتابل مسئول فنی و پنل متقاضی
- [x] فاز ۸: داشبورد، چاپ، لاگ و پشتیبان کامل
- [x] فاز ۹: آزمون دسترسی، اکسل، هم‌زمانی و بازیابی

## فاز ۱۰ — وب‌سایت عمومی (v0.10.0)
- سایت عمومی در / (الهام از قالب کلینیک، تقویم شمسی، فرم درخواست مشاوره)
- پنل مدیریت در /panel
- APIهای عمومی: مشاوران فعال با عکس + ثبت درخواست مشاوره (محدودسازی نرخ + هانی‌پات)
- محتوای متن: site/src/content/texts.ts — تصاویر: site/public/assets

## فاز ۲۱ — رزرو آنلاین نوبت از سایت عمومی (v0.21.0)
- صفحه رزرو عمومی در /booking (انتخاب مشاور ← روز ← اسلات ← فرم، با کد پیگیری)
- موتور اسلات: شنبه تا چهارشنبه ۹-۱۷، پنجشنبه ۹-۱۳، جمعه تعطیل، اسلات ۶۰ دقیقه، بازه فردا تا ۳۰ روز
- API عمومی: GET /public/booking/slots و رزرو در POST /consultation-requests (ایندکس یکتای جزئی ضد دوباره‌رزرو)
- کارتابل پذیرش: نمایش «نوبت درخواستی» و پیش‌پر شدن نوبت اولیه هنگام تبدیل
- رفع باگ پنهان فاز ۱۰: photo_path در مدل Counselor (خطای ۵۰۰ در /public/counselors)

## فاز ۲۲ — فرم‌های چندگانه و نمایش فرایندها با BPMN (v0.22.0)
- رجیستری فرم‌های بالینی در backend/app/core/forms.py (افزودن فرم جدید = ماژول + یک سطر)
- فرم RS-PS-01-01 «پذیرش اولیه مراجعان تلفنی» با تعیین مسیر مراجع
- فرم RS-PS-08-01 «ارزیابی و مدیریت مورد حاد / پر خطر» با سطوح فوریت و قاعده ارجاع سطح ۳
- API: GET /forms و GET /forms/{form_code}؛ POST ارزیابی با form_code (پیش‌فرض RS-PS-04-01)
- صفحه «فرایندها (BPMN)» در /processes با bpmn-js و چهار نمودار BPMN 2.0
- مستندات: docs/multi-forms-and-bpmn.md — آزمون‌ها: backend/tests/test_multi_forms.py

## فاز ۲۳ — کارتابل هشدار سطح ۳ مسئول فنی (v0.23.0)
- API: GET /api/v1/worklists/level3 (نقش مسئول فنی) — فرم‌های RS-PS-08-01 نهایی‌شده با فوریت سطح ۳
- صف هشدار: قدیمی‌ترین اول، شمارش کل هشدارهای سطح ۳، جزئیات فوری (نوع خطر، اقدام فوری، ارجاع) از پاسخ‌های JSONB
- صفحه «هشدار سطح ۳» در /level3-alerts با بازخوانی خودکار هر ۳۰ ثانیه و استایل فوری
- بدون migration جدید — پرس‌وجوی JSONB روی answers؛ معماری نسخه‌داری فرم‌ها دست‌نخورده
- آزمون‌ها: backend/tests/test_level3_cartable.py — مستندات: docs/multi-forms-and-bpmn.md (بخش ۸)
