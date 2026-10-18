"""B39-plus فاز ۲۷ - حذف فراداده تصاویر پیش از ذخیره (بند «فایل و امنیت» سند).

- EXIF تصویر می‌تواند GPS، مدل دستگاه، زمان و اطلاعات نویسنده را افشا کند؛
  برای پرونده بالینی این افشا غیرقابل‌پذیرش است.
- پیاده‌سازی با Pillow (re-encode بدون بلوک‌های متادیتا):
  JPEG → حذف EXIF/ICC/COM، PNG → حذف tEXt/iTXt/eXIf، WEBP → حذف EXIF/XMP.
- جهت EXIF پیش از حذف داخل پیکسل‌ها «پخته» می‌شود تا تصویر نچرخد (exif_transpose).
- تصاویر متحرک (Animated WEBP/APNG) دست‌نخورده می‌مانند تا محتوا تخریب نشود.
- در نبود Pillow، بدون خطا عبور کامل داده (تفکیک در گزارش DPO).
"""

import io

from app.core.config import get_settings

try:  # Pillow اختیاری است؛ نبود آن نباید آپلود را بشکند
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None

STRIPPABLE_MIMES = ("image/jpeg", "image/png", "image/webp")

_SAVE_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def strip_image_metadata(data: bytes, mime: str) -> tuple[bytes, bool]:
    """خروجی: (بایت‌های پاک‌سازی‌شده، آیا فراداده‌ای حذف شد)."""
    if Image is None or mime not in STRIPPABLE_MIMES or not data:
        return data, False
    if not get_settings().strip_image_metadata:
        return data, False
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        if getattr(img, "is_animated", False):
            # تصویر متحرک: حفظ کامل محتوا
            return data, False
        # فراداده موجود؟ (EXIF/ICC/تکه‌های متنی)
        had_meta = bool(getattr(img, "info", None)) or bool(img.getexif())
        # جهت EXIF باید پیش از حذف فراداده به پیکسل منتقل شود
        img = ImageOps.exif_transpose(img)
        buf = io.BytesIO()
        fmt = _SAVE_FORMAT[mime]
        if fmt == "JPEG":
            img.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
        else:  # PNG / WEBP: بازذخیره بدون بلوک‌های فراداده
            img.save(buf, format=fmt)
        return buf.getvalue(), had_meta
    except Exception:
        # هر خطایی → محتوای اصلی دست‌نخورده می‌ماند (اسکن جداگانه انجام می‌شود)
        return data, False
