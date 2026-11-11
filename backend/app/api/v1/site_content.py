"""فاز ۸۴ — ویرایشگر وردپرسی‌وار صفحات عمومی سایت: API محتوا.

نقش‌ها:
- GET  /site-content/public                    → سندهای «منتشرشده» برای اپ site
  (بدون احراز هویت؛ public_prefixes دروازهٔ ماتریس آن را همیشه باز نگه می‌دارد)؛
- بقیه فقط SYSTEM_ADMIN/ORG_MANAGER (ماتریس منو: کلید site-content-editor).

چرخهٔ محتوا (مثل قاعدهٔ فرم‌ساز فاز ۸۳):
- هیچ تغییری تا «انتشار» روی سایت اعمال نمی‌شود — سایت فقط published را می‌خواند؛
- PUT      ذخیرهٔ پیش‌نویس (سند کامل صفحه)؛
- POST publish          انتشار: کپی draft → published؛
- POST revert-draft     بازگردانی پیش‌نویس به آخرین نسخهٔ منتشرشده (نکشیدن تغییرات)؛
- POST reset            بازنشانی کامل: حذف ردیف → سایت به متن‌های پیش‌فرض کد برمی‌گردد.

منبع «متن‌های پیش‌فرض» برای ویرایشگر پنل: app/data/site_content_defaults.json که
از site/src/content/*.ts تولید می‌شود (deploy/gen_site_content_defaults.mjs) —
تک‌منبع حقیقت متن‌ها همان فایل‌های site است.

فاز ۸۵ — تصاویر عمومی سایت (بنر/تصویر کارت‌ها):
- POST /site-content/admin/images        آپلود تصویر (فقط ادمین؛ Pillow-verify +
  حذف فراداده + اسکن AV؛ png/jpeg/webp؛ سقف حجم آپلود سرور)
- GET  /site-content/images/{fname}      سرو عمومی تصویر آپلودشده (بدون احراز؛
  public_prefixes؛ نام فایل = sha24.png/jpg/webp — content-addressed، یعنی
  آپلود تکراری idempotent و کش‌پذیر با Cache-Control immutable)
تصاویر عمومیِ سایت نیستند محرمانه — هر آدرس آپلودشده از نظر طراحی برای عموم است.
"""
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.config import get_settings
from app.models.site_content import SITE_PAGE_KEYS, SITE_PAGE_TITLES, SitePageContent
from app.models.user import User
from app.services import av_scan
from app.services import file_storage as fs
from app.services import object_storage as objstore
from app.services.audit import record_audit
from app.services.image_sanitizer import strip_image_metadata

try:  # Pillow وابستگی رسمی requirements است؛ گارد فقط برای محیط‌های ناقص
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None  # type: ignore[assignment]

router = APIRouter(tags=["site-content"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")

# سقف حجم هر سند صفحه — محتوای متنی است؛ ۵۱۲KB بسیار بزرگ‌تر از نیاز واقعی
MAX_DOC_BYTES = 512 * 1024

# فاز ۸۵ — تصاویر عمومی: فقط png/jpeg/webp (هماهنگ با allowed_mime_types؛
# SVG پذیرفته نمی‌شود چون inline سرو می‌شود و بردار XSS دارد؛ GIF هم نیست)
IMAGE_MIMES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
# نام فایل قابل سرو: فقط الگوی تولیدی خودمان — «پیمایش مسیر» ناممکن است
IMAGE_NAME_RE = re.compile(r"^([0-9a-f]{24})\.(png|jpg|webp)$")
_EXT_MIME = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}

_DEFAULTS_CACHE: dict[str, Any] | None = None


def _load_defaults() -> dict[str, Any]:
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is None:
        # app/api/v1/site_content.py → parents[2] = app → app/data/…
        path = Path(__file__).resolve().parents[2] / "data" / "site_content_defaults.json"
        try:
            raw = json.loads(path.read_text("utf-8"))
            _DEFAULTS_CACHE = {
                k: raw[k] for k in SITE_PAGE_KEYS if isinstance(raw.get(k), dict)
            }
        except Exception:
            # فایل پیش‌فرض نبود؟ ویرایشگر پنل بدون defaults هم کار می‌کند
            # (ادمین از سند منتشرشده/پیش‌نویس ویرایش را شروع می‌کند)
            _DEFAULTS_CACHE = {}
    return _DEFAULTS_CACHE


def _ensure_key(page_key: str) -> None:
    if page_key not in SITE_PAGE_KEYS:
        raise HTTPException(status_code=404, detail="صفحهٔ موردنظر یافت نشد")


def _doc_bytes(content: dict) -> int:
    return len(json.dumps(content, ensure_ascii=False).encode("utf-8"))


def _display_name(db: Session, user_id: Any) -> str | None:
    if not user_id:
        return None
    u = db.get(User, user_id)
    return u.display_name if u else None


def _detail(db: Session, row: SitePageContent | None, page_key: str) -> dict:
    defaults = _load_defaults().get(page_key)
    if row is None:
        return {
            "page_key": page_key,
            "draft": None,
            "published": None,
            "defaults": defaults,
            "updated_at": None,
            "updated_by_name": None,
            "published_at": None,
            "published_by_name": None,
        }
    return {
        "page_key": page_key,
        "draft": row.draft_content,
        "published": row.published_content,
        "defaults": defaults,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by_name": _display_name(db, row.updated_by),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "published_by_name": _display_name(db, row.published_by),
    }


def _get_row(db: Session, page_key: str) -> SitePageContent | None:
    return db.get(SitePageContent, page_key)


@router.get("/site-content/public")
def public_site_content(db: Session = Depends(get_db)) -> dict:
    """سندهای منتشرشدهٔ صفحات عمومی — مصرف‌کننده: اپ site (بدون احراز هویت)."""
    out: dict[str, dict | None] = {k: None for k in SITE_PAGE_KEYS}
    for row in db.scalars(select(SitePageContent)).all():
        if row.page_key in out and row.published_content:
            out[row.page_key] = row.published_content
    return out


@router.get("/site-content/admin")
def admin_site_content(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """فهرست صفحات ویرایش‌پذیر + متن‌های پیش‌فرض (برای لانچر ویرایشگر پنل)."""
    rows = {r.page_key: r for r in db.scalars(select(SitePageContent)).all()}
    pages = []
    for k in SITE_PAGE_KEYS:
        row = rows.get(k)
        pages.append(
            {
                "page_key": k,
                "title": SITE_PAGE_TITLES.get(k, k),
                "has_draft": bool(row and row.draft_content),
                "has_published": bool(row and row.published_content),
                "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
                "updated_by_name": _display_name(db, row.updated_by) if row else None,
                "published_at": row.published_at.isoformat() if row and row.published_at else None,
            }
        )
    return {"pages": pages, "defaults": _load_defaults()}


@router.get("/site-content/admin/{page_key}")
def admin_page_detail(
    page_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    _ensure_key(page_key)
    return _detail(db, _get_row(db, page_key), page_key)


class SaveDraftIn(BaseModel):
    content: dict


@router.put("/site-content/admin/{page_key}")
def save_draft(
    page_key: str,
    payload: SaveDraftIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """ذخیرهٔ پیش‌نویس — هیچ اثری روی سایت ندارد تا «انتشار»."""
    _ensure_key(page_key)
    if _doc_bytes(payload.content) > MAX_DOC_BYTES:
        raise HTTPException(status_code=422, detail="حجم سند بیش از حد مجاز است")
    row = _get_row(db, page_key)
    if row is None:
        row = SitePageContent(page_key=page_key)
    row.draft_content = payload.content
    row.updated_by = user.id
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        action="site_content.draft_saved",
        actor_user_id=user.id,
        entity_type="site_page_content",
        entity_id=page_key,
        detail={"bytes": _doc_bytes(payload.content)},
    )
    return _detail(db, row, page_key)


@router.post("/site-content/admin/{page_key}/publish")
def publish_draft(
    page_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """انتشار پیش‌نویس — از این لحظه بازدیدکنندگان سند جدید را می‌بینند."""
    _ensure_key(page_key)
    row = _get_row(db, page_key)
    if row is None or not row.draft_content:
        raise HTTPException(status_code=404, detail="پیش‌نویسی برای انتشار وجود ندارد")
    row.published_content = row.draft_content
    row.published_at = datetime.now(timezone.utc)
    row.published_by = user.id
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        action="site_content.published",
        actor_user_id=user.id,
        entity_type="site_page_content",
        entity_id=page_key,
    )
    return _detail(db, row, page_key)


@router.post("/site-content/admin/{page_key}/revert-draft")
def revert_draft(
    page_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """بازگردانی پیش‌نویس به آخرین نسخهٔ منتشرشده (نکشیدن تغییرات ذخیره‌شده)."""
    _ensure_key(page_key)
    row = _get_row(db, page_key)
    if row is None:
        raise HTTPException(status_code=404, detail="پیش‌نویسی برای بازگردانی وجود ندارد")
    row.draft_content = dict(row.published_content) if row.published_content else None
    row.updated_by = user.id
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        action="site_content.draft_reverted",
        actor_user_id=user.id,
        entity_type="site_page_content",
        entity_id=page_key,
    )
    return _detail(db, row, page_key)


@router.post("/site-content/admin/{page_key}/reset")
def reset_page(
    page_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """بازنشانی کامل صفحه — حذف پیش‌نویس و نسخهٔ منتشرشده؛ سایت به متن‌های
    پیش‌فرض کد برمی‌گردد (fallback طبیعی اپ site)."""
    _ensure_key(page_key)
    row = _get_row(db, page_key)
    if row is not None:
        db.delete(row)
        db.commit()
    record_audit(
        db,
        action="site_content.reset",
        actor_user_id=user.id,
        entity_type="site_page_content",
        entity_id=page_key,
    )
    return _detail(db, None, page_key)


# ---------------------------------------------------------------------------
# فاز ۸۵ — تصاویر عمومی سایت (بنر/تصویر کارت‌ها)
# ---------------------------------------------------------------------------

def _verify_image(data: bytes, mime: str) -> None:
    """اعتبارسنجی محتوای واقعی تصویر با Pillow — جلوگیری از جعل mime.

    فایل HTML/اسکریپت با content_type جعلی image/png نباید ذخیره شود.
    """
    if PILImage is None:
        # محیط ناقص: حداقل امضای بایت را چک می‌کنیم (magic bytes)
        sig = {
            "image/png": data[:8] == b"\x89PNG\r\n\x1a\n",
            "image/jpeg": data[:2] == b"\xff\xd8",
            "image/webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        }.get(mime, False)
        if not sig:
            raise HTTPException(status_code=422, detail="محتوای فایل با نوع اعلام‌شده مطابقت ندارد")
        return
    try:
        img = PILImage.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(status_code=422, detail="فایل ارسالی تصویر معتبری نیست")
    expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}.get(mime)
    if expected and (img.format or "").upper() != expected:
        raise HTTPException(status_code=422, detail="محتوای فایل با نوع اعلام‌شده مطابقت ندارد")


@router.post("/site-content/admin/images", status_code=201)
def upload_site_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """آپلود تصویر عمومی سایت — خروجی: URL نسبی برای درج در سند محتوا.

    مسیر امنیتی: سقف حجم → نوع مجاز → Pillow-verify (ضد mime جعلی) →
    حذف فراداده (EXIF/GPS) → اسکن AV (قرنطینه = رد) → ذخیره با کلید
    قطعی sha24 → URL عمومی. آپلود دوبارهٔ همان تصویر همان URL را می‌دهد.
    """
    settings = get_settings()
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="فایل خالی است")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"حجم فایل بیش از سقف مجاز ({settings.max_upload_mb} مگابایت) است",
        )
    mime = (file.content_type or "").split(";")[0].strip().lower()
    ext = IMAGE_MIMES.get(mime)
    if ext is None:
        raise HTTPException(
            status_code=422,
            detail="فقط تصاویر PNG و JPG و WEBP پذیرفته می‌شود",
        )
    _verify_image(data, mime)

    # فاز ۲۷-مانند: حذف EXIF/GPS پیش از ذخیره (png/jpeg/webp)
    data, metadata_stripped = strip_image_metadata(data, mime)

    # اسکن بدافزار — قرنطینه هرگز عمومی نمی‌شود
    scan = av_scan.scan_bytes(f"site_image.{ext}", mime, data, settings.allowed_mime_list)
    if scan.status == "quarantined":
        raise HTTPException(status_code=422, detail="فایل از نظر امنیتی رد شد")

    digest = hashlib.sha256(data).hexdigest()[:24]
    key = f"site_content/{digest}.{ext}"
    provider, fallback = objstore.store_at_key(data, key, settings)

    fname = f"{digest}.{ext}"
    record_audit(
        db,
        action="site_content.image_uploaded",
        actor_user_id=user.id,
        entity_type="site_page_content",
        entity_id=fname,
        detail={
            "mime": mime,
            "size": len(data),
            "sha256": digest,
            "storage": provider,
            "storage_fallback": fallback,
            "metadata_stripped": metadata_stripped,
            "scanner": scan.scanner,
        },
    )
    db.commit()
    return {
        "url": f"/api/v1/site-content/images/{fname}",
        "mime": mime,
        "size_bytes": len(data),
        "sha256": digest,
        "storage": provider,
    }


@router.get("/site-content/images/{fname}")
def get_site_image(fname: str):
    """سرو عمومی تصویر آپلودشده — بدون احراز (public_prefixes).

    نام فایل با الگوی قطعی اعتبارسنجی می‌شود (ضد پیمایش مسیر)؛ کش‌پذیری
    با Cache-Control immutable چون نام = هش محتواست.
    """
    m = IMAGE_NAME_RE.match(fname)
    if not m:
        raise HTTPException(status_code=404, detail="تصویر یافت نشد")
    ext = m.group(2)
    settings = get_settings()
    key = f"site_content/{fname}"
    path = fs.storage_path(settings.upload_dir, key)
    headers = {"Cache-Control": "public, max-age=2592000, immutable"}
    if os.path.exists(path):
        return FileResponse(path, media_type=_EXT_MIME[ext], headers=headers)
    # بک‌اند S3 فعال ولی فایل محلی نیست → خواندن از S3
    if (settings.storage_backend or "").lower() == "s3":
        try:
            data = objstore.open_bytes(settings.upload_dir, "s3", key, settings)
            return Response(content=data, media_type=_EXT_MIME[ext], headers=headers)
        except FileNotFoundError:
            pass
        except Exception:
            raise HTTPException(status_code=502, detail="خواندن از سرویس ذخیره‌سازی ممکن نشد")
    raise HTTPException(status_code=404, detail="تصویر یافت نشد")
