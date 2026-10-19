# اپ موبایل Rosepsy — B17 (فاز ۳۶)

کلاینت Flutter برای API سامانه Rosepsy (`/api/v1`). این پروژه **منبع Dart**
است و ساخت خروجی آن به Flutter SDK نیاز دارد (در مخزن CI بک‌اند/فرانت
اجرا می‌شود؛ build اپ در CI جداگانه موبایل).

## دامنه نسخه فعلی (MVP)

- ورود با نام کاربری/رمز (بند ۴.۲ سند) + بازیابی خودکار نشست
- پروفایل من (`GET /me/profile`) و نقش‌ها (`GET /auth/me`)
- نوبت‌های من (`GET /me/appointments`)
- اعلان‌ها (`GET /notifications` + خواندن/خواندن همه)
- سفارش‌های من (`GET /orders` — فیلتر مالک سمت سرور)
- خروج (`POST /auth/logout` + پاک‌سازی توکن محلی)

رزرو نوبت و پرداخت در اپ عمداً در نسخه اول نیست (جریان callback درگاه و
OTP در وب کامل است) و در نسخه بعدی اپ اضافه می‌شود.

## قواعد حریم خصوصی (سند جامع)

- هیچ داده بالینی روی دستگاه کش/ذخیره نمی‌شود؛ مدل‌ها فقط در حافظه نشست؛
- توکن دسترسی در `SharedPreferences` نگه داشته می‌شود؛ برای تولید،
  جابه‌جایی به `flutter_secure_storage` توصیه می‌شود (نکته امنیتی)؛
- پیام‌های خطای فارسی سرور عیناً نمایش داده می‌شوند؛ لاگ محلی وجود ندارد.

## ساخت و اجرا

```bash
cd mobile
flutter pub get
# شبیه‌ساز اندروید: آدرس میزبان 10.0.2.2 است (پیش‌فرض)
flutter run --dart-define=ROSEPSY_API_BASE=http://10.0.2.2:8080/api/v1
# تولید:
flutter build apk --release --dart-define=ROSEPSY_API_BASE=https://<دامنه>/api/v1
```

## ساختار

```
lib/
├── main.dart                    نقطه ورود + AuthGate
├── api/api_client.dart          کلاینت REST + مدیریت 401/خطا
├── models/models.dart           مدل‌های سبک نمایش
├── state/auth_controller.dart   نشست کاربر (Provider)
├── screens/                     ورود/خانه/پروفایل/نوبت/اعلان/سفارش
└── widgets/empty_state.dart     حالت خالی/خطای مشترک
```

## تحلیل ایستا

پس از نصب Flutter SDK: `flutter analyze` (تنظیمات lint در
`analysis_options.yaml` بر flutter_lints).
