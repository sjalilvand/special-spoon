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
- [ ] فاز ۶: نوبت، جلسه و کارتابل مشاور
- [ ] فاز ۷: کارتابل مسئول فنی و پنل متقاضی
- [ ] فاز ۸: داشبورد، چاپ، لاگ و پشتیبان کامل
- [ ] فاز ۹: آزمون دسترسی، اکسل، هم‌زمانی و بازیابی
