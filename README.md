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

## فاز ۲۴ — بازبینی مطابق سند جامع v0.2 و فرم‌های پیوست (v0.24.0)
- اعتبارسنجی نسخه‌آگاه فرم‌ها (B14): قواعد قالب/سقف طول بر اساس تعریف نسخه ذخیره‌شده
- ماژول مشترک form_common.py: سقف طول، قالب موبایل/تلفن/کد ملی (رقم کنترل)، سن، گزینه‌های مجاز
- نرمال‌سازی پاسخ‌ها در create/patch: ارقام فارسی → لاتین، کانونی‌سازی تلفن/کد ملی
- فرم‌ها: RS-PS-01-01 v2، RS-PS-08-01 v2 (تاریخ فرم)، RS-PS-04-01 v4 (اطلاعات فردی و اجتماعی + گزینه‌های MSE پیوست + اصلاح برچسب‌ها)
- BPMN مورد حاد: افزودن گام کارتابل هشدار سطح ۳ با حلقه برگشت
- ماتریس تطبیق کامل سند: docs/requirements-compliance.md — آزمون‌ها: test_form_rules_v24.py

## فاز ۲۵ — مرکز اعلان، رضایت نسخه‌دار و فایل امن براساس سند جامع v0.2 (v0.25.0)
- **B12/B38 مرکز اعلان:** جدول notifications + سرویس emit ایمن (SAVEPOINT)؛ اعلان خودکار روی نهایی‌سازی/تأیید/برگشت فرم، هشدار سطح ۳ (critical) و ابطال رضایت
- API اعلان: GET /notifications (+unread-count) و POST /{id}/read و /read-all؛ ایزولاسیون کامل کاربر (اعلان دیگران = 404)
- زنگ اعلان در نوار بالا با شمارنده و polling هر ۶۰ ثانیه + صفحه «اعلان‌ها» با فیلتر خوانده‌نشده
- **B41 رضایت نسخه‌دار:** جدول consent_versions (متن غیرقابل‌تغییر، نسخه‌گذاری خودکار per-kind) + ابطال با حفظ سابقه (revoked_at/by/reason) + به‌روزرسانی وضعیت پرونده
- API رضایت: GET/POST /consent-versions (انتشار فقط مدیر سامانه) و POST /consents/{id}/revoke
- **B39 فایل امن:** آپلود multipart با سقف حجم ۱۰MB + SHA-256 + اسکن پایه (stub) + قرنطینه فایل اجرایی/غیرمجاز + دانلود فقط با بلیت امضاشده HMAC کوتاه‌مدت (۱۲۰ ثانیه)
- بخش «فایل‌های پرونده» در جزئیات پرونده + دکمه ابطال رضایت با دلیل الزامی
- **دسته ۵ آزمون سند:** tests/test_access_matrix.py — ماتریس نقش×مسیر (401 بدون توکن، 403/404 نقش غیرمجاز، 200 نقش مجاز)
- Migration: 0014_phase25_governance — مستندات: docs/roadmap-v02.md (نقشه راه باقی‌مانده) و docs/requirements-compliance.md

## فاز ۲۶ — نگهداشت موقت نوبت، کد یک‌بارمصرف و تاریخ شمسی سراسری + داشبورد مدیر (v0.26.0)
- **B09 نگهداشت موقت اسلات (booking hold):** جدول `slot_claims` + ایندکس یکتای جزئی (فقط یک hold فعال برای هر مشاور/اسلات)؛ POST/GET/DELETE `/public/booking-holds` با توکن hash شده و انقضای ۱۰ دقیقه
- آزادسازی خودکار hold منقضی به‌صورت تنبل (بدون کارگر پس‌زمینه)؛ اسلات‌های نگه‌داشته‌شده از فهرست آزاد حذف و در منع تعارض حساب می‌شوند
- تبدیل hold به رزرو: ثبت `consultation-requests` با `hold_token` → hold تأیید و به درخواست پیوند می‌خورد؛ سقف نگهداشت همزمان per-IP و نرخ ۱۲/ساعت
- **B02-lite کد یک‌بارمصرف (OTP):** جدول `otp_challenges` + سرویس امن (کد فقط hash با pepper، انقضا ۱۸۰ ثانیه، سقف ۳ تلاش، مصرف یک‌باره، باطل شدن کد قبلی با صدور جدید)؛ POST `/auth/otp/request` و `/auth/otp/verify`
- حالت توسعه: `OTP_DEV_MODE=true` کد در پاسخ API و لاگ نمایش داده می‌شود (آماده‌سازی درگاه پیامک D04)؛ اتصال به رزرو با `otp_token` یک‌بارمصرف و کنترل تطابق موبایل
- **UI سند ۰۸ - تاریخ شمسی سراسری:** تبدیل دقیق میلادی↔شمسی در بک‌اند (`gregorian_to_jalali` + `format_jalali` + تست رفت‌وبرگشت دو دهه) و همه تاریخ‌های ۲۱ صفحه/مؤلفه فرانت با `Intl fa-IR-u-ca-persian` شمسی نمایش داده می‌شوند
- **B24 داشبورد مدیر:** GET `/reports/admin-dashboard` (مدیر سازمان/سامانه) — KPI شفاف (پرونده، میانگین زمان بررسی، نرخ عدم حضور، رزرو آنلاین، نگهداشت فعال)، روند روزانه پرونده/رزرو، عملکرد مشاوران؛ صفحه `/admin-dashboard` با نمودار ستونی SVG بدون وابستگی جدید
- صفحه رزرو سایت: شمارش معکوس نگهداشت، تأیید موبایل با OTP، آزادسازی خودکار در انقضا/بازگشت
- Migration: 0015_phase26_holds_otp — آزمون‌ها: test_booking_holds.py (۸)، test_otp.py (۱۲)، test_admin_dashboard.py (۵)، test_jalali_dates.py (۴)
