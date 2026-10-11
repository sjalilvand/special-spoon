# Rosepsy — سامانه مشاوره روان‌شناختی سازمانی

پیاده‌سازی سند تحلیل نیازمندی‌ها (نسخه ۲.۰ — فرم مبنا RS-PS-04-01).
نسخه اولیه یک‌سازمانی: PostgreSQL + FastAPI + React/Vite + Docker Compose + Nginx.

## پیش‌نیازها

- Docker Desktop (شامل Docker Compose v2)
- Git

## راه‌اندازی عملیاتی

1) تنظیمات محیط:

    Copy-Item .env.example .env

    سپس در فایل .env مقدار POSTGRES_PASSWORD و همان مقدار داخل DATABASE_URL را تغییر دهید.

2) ساخت و اجرا:

    docker compose build
    docker compose up -d db
    docker compose run --rm migrate
    docker compose up -d

3) دسترسی:

    - وب:          http://localhost:8080
    - مستندات API:  http://localhost:8080/api/v1/docs

نکته امنیتی (بند ۴.۲ سند): ایجاد «مدیر اولیه» در فاز ۲ از طریق فرمان امن اضافه می‌شود؛
هیچ رمز ثابتی در کد یا Docker وجود ندارد.

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
- [ ] فاز ۲: ورود، نقش‌ها، مدیر اولیه و مدیریت حساب
- [ ] فاز ۳: مشاوران، متقاضیان و سه قالب اکسل
- [ ] فاز ۴: تشکیل پرونده، رضایت و تخصیص
- [ ] فاز ۵: فرم ثابت نسخه‌دار و ثبت ارزیابی
- [ ] فاز ۶: نوبت، جلسه و کارتابل مشاور
- [ ] فاز ۷: کارتابل مسئول فنی و پنل متقاضی
- [ ] فاز ۸: داشبورد، چاپ، لاگ و پشتیبان کامل
- [ ] فاز ۹: آزمون دسترسی، اکسل، هم‌زمانی و بازیابی
