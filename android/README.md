# اپلیکیشن اندروید رز دکتر (فاز ۶۸ — به‌روز فاز ۹۴)

پوستهٔ «کاملاً آنلاین» سایت رز دکتر: یک WebView بومی بدون هیچ وابستگی خارجی
(AndroidX ندارد) که همهٔ صفحات سایت — نقشهٔ کلینیک‌ها، نوبت‌دهی، چت و پنل —
را از خود سرور می‌خواند. هیچ داده‌ای داخل اپ ذخیره نمی‌شود.

## مشخصات

| مورد | مقدار |
|---|---|
| applicationId | `ir.rosedoctor.app` (فاز ۹۴ — پیش از این `ir.rosepsy.app` بود) |
| نام نمایشی اپ | رز دکتر |
| نسخه | 1.0.0 (versionCode 1) |
| حداقل اندروید | ۷ (API 24) |
| target SDK | 34 |
| حجم APK | ~۳۳ کیلوبایت |
| آدرس شروع | فاز ۹۴ — ابتدا `http://rosedoctor.ir/` (**آدرس رسمی روی پورت ۸۰**) و در صورت خطا `http://rosedoctor.ir:8080` سپس `http://130.185.73.157:8080` و در آخر `https://rosedoctor.ir/` (`usesCleartextTraffic=true`) |

> یادداشت فاز ۹۴: با تغییر applicationId، اندروید این اپ را «برنامهٔ جدید» می‌شناسد؛
> نصبِ قبلی با پکیج `ir.rosepsy.app` به‌روزرسانی نمی‌شود و باید دستی حذف شود.
> نام فایل APK همچنان `rosedoctor-1.0.0.apk` ثابت مانده تا لینک `/app/rosedoctor-1.0.0.apk`
> و QR سایت معتبر بمانند.

## امکانات اپ

- نوار پیشرفت بارگذاری + صفحهٔ خطای فارسی با دکمهٔ «تلاش دوباره»
- دکمهٔ برگشت اندروید با تاریخچهٔ SPA سایت هماهنگ است
- لینک‌های `tel:` / `mailto:` / `sms:` به اپ‌های سیستم سپرده می‌شوند
- آپلود فایل (انتخابگر فایل) و دانلود فایل‌ها با DownloadManager سیستم
- کوکی‌ها و DOM storage فعال (ورود به پنل داخل اپ کار می‌کند)
- آیکون adaptive (رز سفید روی گرادیان رز) در همهٔ چگالی‌ها

## ساخت مجدد (روی هر ماشین با JDK 17 + Android SDK)

```bash
cd android
export JAVA_HOME=<path-to-jdk17>
export ANDROID_HOME=<path-to-android-sdk>
./gradlew assembleRelease --no-daemon
# خروجی: app/build/outputs/apk/release/app-release.apk
```

سپس APK را در `site/public/app/rosedoctor-1.0.0.apk` کپی کنید (نام فایل ثابت است
تا لینک دکمهٔ `AppDownload.tsx` و QR سایت معتبر بمانند)، build سایت را بگیرید
و آپگرید سرور را اجرا کنید.

> یادداشت فاز ۹۴: APK با همین سورس (پکیج جدید `ir.rosedoctor.app` و آدرس شروع
> دامنه‌محور) بازسازی و دوباره با `android/rosepsy.keystore` امضا شده است.

## امضا

- `rosepsy.keystore` + `keystore.properties` در همین پوشه commit شده‌اند تا
  به‌روزرسانی‌های بعدی بتوانند روی نصب قبلی سوار شوند (self-distribution).
  **هرگز keystore را عوض نکنید**؛ وگرنه کاربران باید اپ را حذف/نصب کنند.
- تمدید/تغییر: `keytool -genkeypair -keystore rosepsy.keystore -alias rosepsy ...`

## QR صفحهٔ اصلی

تولید مجدد QR پس از تغییر آدرس APK:

```bash
pip install qrcode
python scripts/make_rose_qr.py   # → site/public/app/qr.svg و qr.png
```
