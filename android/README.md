# اپلیکیشن اندروید رزپسی (فاز ۶۸)

پوستهٔ «کاملاً آنلاین» سایت رزپسی: یک WebView بومی بدون هیچ وابستگی خارجی
(AndroidX ندارد) که همهٔ صفحات سایت — نقشهٔ کلینیک‌ها، نوبت‌دهی، چت و پنل —
را از خود سرور می‌خواند. هیچ داده‌ای داخل اپ ذخیره نمی‌شود.

## مشخصات

| مورد | مقدار |
|---|---|
| applicationId | `ir.rosepsy.app` |
| نسخه | 1.0.0 (versionCode 1) |
| حداقل اندروید | ۷ (API 24) |
| target SDK | 34 |
| حجم APK | ~۳۴ کیلوبایت |
| آدرس شروع | ابتدا `http://130.185.73.157.sslip.io:8080` (فاز ۷۸: تنها پورت باز فایروال هاستینگ) و در صورت خطا سقوط خودکار به `https://` و بعد `http://` (پورت‌های 80/443 فعلاً در فایروال شرکت هاستینگ بسته‌اند؛ `usesCleartextTraffic=true`)؛ وقتی 443 باز شد ترتیب را در `MainActivity.java` برگردانید |

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

سپس APK را در `site/public/app/rosepsy-<نسخه>.apk` کپی کنید (و اگر نام/نسخه
عوض شد، لینک دکمهٔ `AppDownload.tsx` و QR در `scripts/make_rose_qr.py` را
هم‌گام کنید)، build سایت را بگیرید و آپگرید سرور را اجرا کنید.

> یادداشت فاز ۷۸: APK موجود در `site/public/app/rosepsy-1.0.0.apk` بدون تغییر
> نام/نسخه (1.0.0 / versionCode 1) با همین سورس بازسازی و دوباره با
> `android/rosepsy.keystore` امضا شده تا روی نصب‌های قبلی سوار شود.
> (بازسازی بدون Android SDK با apktool + zipalign + apksigner انجام شد؛
> نام فایل ثابت مانده تا لینک `/app/rosepsy-1.0.0.apk` و QR سایت معتبر بمانند.)

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
