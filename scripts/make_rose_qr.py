#!/usr/bin/env python3
"""فاز ۸۷ — بازتولید QR صفحهٔ دانلود اپ با دامنهٔ rosedoctor.ir.

خروجی: site/public/app/qr.svg و qr.png — آدرس فایل نصب APK روی رز دکتر.
اجرا (در ریشهٔ مخزن):  python scripts/make_rose_qr.py
(پیش‌نیاز: pip install qrcode)
"""
import os

import qrcode

APK_URL = os.environ.get("APK_URL", "http://rosedoctor.ir/app/rosedoctor-1.0.0.apk")
OUT_SVG = "site/public/app/qr.svg"
OUT_PNG = "site/public/app/qr.png"

qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
qr.add_data(APK_URL)
qr.make(fit=True)

# PNG (واقعی، برای تصویر)
img = qr.make_image(fill_color="#8e2b4a", back_color="white")
os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
img.save(OUT_PNG)

# SVG (همان محتوا به‌صورت وکتور)
try:
    import qrcode.image.svg as svgmod

    factory = svgmod.SvgPathImage
    qr2 = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2, image_factory=factory)
    qr2.add_data(APK_URL)
    qr2.make(fit=True)
    img2 = qr2.make_image()
    img2.save(OUT_SVG)
except Exception as e:  # noqa: BLE001
    print("SVG generation skipped:", e)

print("QR regenerated:", APK_URL, "->", OUT_PNG, OUT_SVG)
