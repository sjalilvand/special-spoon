"""B39 سند جامع - بارگذاری و دانلود امن فایل.

POST /api/v1/files/upload                 آپلود multipart (سقف حجم/نوع + checksum + اسکن)
GET  /api/v1/files?case_id=...            فهرست فایل‌های پرونده (کنترل دسترسی هر بار)
GET  /api/v1/files/{id}                   فراداده فایل
POST /api/v1/files/{id}/download-ticket   بلیت دانلود کوتاه‌مدت با امضا
GET  /api/v1/files/{id}/download?ticket=  دانلود فقط با بلیت معتبر؛ قرنطینه‌شده دانلود نمی‌شود
POST /api/v1/files/{id}/rescan            اجرای دوباره اسکن (پس از اتصال آنتی‌ویروس واقعی)
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models.case import Case
from app.models.people import Counselor
from app.models.file import FileScan, StoredFile
from app.services import file_storage as fs
from app.services.audit import record_audit
from app.services.case_access import counselor_can_access

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_ROLES = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")


def _require_case_file_access(db: Session, actor, case: Case | None) -> None:
    """کنترل مجوز در هر بار دانلود/فهرست (بند B39: کنترل مجوز در هر بار دانلود)."""
    if case is None:
        return
    roles = {r.code for r in actor.roles}
    if roles & {"ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"}:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and counselor_can_access(db, c.id, case):
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


def _file_out(f: StoredFile) -> dict:
    return {
        "id": str(f.id),
        "case_id": str(f.case_id) if f.case_id else None,
        "context": f.context,
        "original_name": f.original_name,
        "mime": f.mime,
        "size_bytes": f.size_bytes,
        "sha256": f.sha256,
        "sensitivity": f.sensitivity,
        "scan_status": f.scan_status,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.post("/upload", status_code=201)
def upload_file(
    file: UploadFile = File(...),
    case_id: uuid.UUID | None = Form(default=None),
    context: str = Form(default="case_document"),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*UPLOAD_ROLES)),
) -> dict:
    settings = get_settings()
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="فایل خالی است")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"حجم فایل بیش از سقف مجاز ({settings.max_upload_mb} مگابایت) است",
        )

    case = None
    if case_id is not None:
        case = db.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="پرونده یافت نشد")
        _require_case_file_access(db, actor, case)

    mime = (file.content_type or "application/octet-stream").split(";")[0].strip()
    name = (file.filename or "بدون‌نام")[:255]

    storage_key, sha = fs.save_bytes(settings.upload_dir, data)
    status, detail = fs.run_stub_scan(name, mime, len(data), settings.allowed_mime_list)

    f = StoredFile(
        case_id=case.id if case else None,
        uploaded_by=actor.id,
        context=context if context in ("case_document", "consent", "intake", "report") else "case_document",
        original_name=name,
        mime=mime,
        size_bytes=len(data),
        sha256=sha,
        storage_key=storage_key,
        sensitivity="confidential",
        scan_status=status,
    )
    db.add(f)
    db.flush()
    db.add(FileScan(file_id=f.id, status=status, detail=detail, scanner="builtin-stub"))

    record_audit(
        db,
        action="file.upload",
        actor_user_id=actor.id,
        entity_type="file",
        entity_id=str(f.id),
        detail={"name": name, "size": len(data), "sha256": sha[:16], "scan_status": status,
                "case_id": str(case.id) if case else None},
    )
    db.commit()
    out = _file_out(f)
    out["scan_detail"] = detail
    return out


@router.get("")
def list_files(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    _require_case_file_access(db, actor, case)
    rows = db.scalars(
        select(StoredFile).where(StoredFile.case_id == case.id)
        .order_by(StoredFile.created_at.desc())
    ).all()
    return {"items": [_file_out(f) for f in rows]}


@router.get("/{file_id}")
def get_file_meta(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    f = db.get(StoredFile, file_id)
    if f is None or f.case_id is None:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    case = db.get(Case, f.case_id)
    _require_case_file_access(db, actor, case)
    return _file_out(f)


@router.post("/{file_id}/download-ticket")
def download_ticket(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    f = db.get(StoredFile, file_id)
    if f is None or f.case_id is None:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    case = db.get(Case, f.case_id)
    _require_case_file_access(db, actor, case)
    if f.scan_status == "quarantined":
        # بند B39: فایل قرنطینه دانلود نمی‌شود
        raise HTTPException(status_code=403, detail="فایل در قرنطینه است و قابل دانلود نیست")
    settings = get_settings()
    token, expires = fs.make_download_ticket(
        settings.auth_secret_key, str(f.id), str(actor.id), settings.download_ticket_seconds
    )
    record_audit(
        db,
        action="file.download_ticket",
        actor_user_id=actor.id,
        entity_type="file",
        entity_id=str(f.id),
    )
    db.commit()
    return {"ticket": token, "expires_at": expires}


@router.get("/{file_id}/download")
def download_file(
    file_id: uuid.UUID,
    ticket: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse:
    """دانلود با بلیت امضاشده کوتاه‌مدت؛ بدون بلیت/بلیت منقضی = 401."""
    settings = get_settings()
    if not ticket:
        raise HTTPException(status_code=401, detail="بلیت دانلود الزامی است")
    verified = fs.verify_download_ticket(settings.auth_secret_key, ticket)
    if verified is None:
        raise HTTPException(status_code=401, detail="بلیت دانلود نامعتبر یا منقضی است")
    tid, _uid = verified
    if str(file_id) != tid:
        raise HTTPException(status_code=401, detail="بلیت متعلق به این فایل نیست")
    f = db.get(StoredFile, file_id)
    if f is None or f.case_id is None:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    if f.scan_status == "quarantined":
        raise HTTPException(status_code=403, detail="فایل در قرنطینه است")
    path = fs.storage_path(settings.upload_dir, f.storage_key)
    try:
        return FileResponse(path, media_type=f.mime, filename=f.original_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="محتوای فایل در فضای ذخیره‌سازی یافت نشد")


@router.post("/{file_id}/rescan")
def rescan_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(require_roles("SYSTEM_ADMIN", "TECHNICAL_SUPERVISOR")),
) -> dict:
    """اجرای دوباره اسکن پایه - نقطه اتصال آنتی‌ویروس واقعی در انتشارهای بعد."""
    f = db.get(StoredFile, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    settings = get_settings()
    status, detail = fs.run_stub_scan(f.original_name, f.mime, f.size_bytes, settings.allowed_mime_list)
    f.scan_status = status
    db.add(FileScan(file_id=f.id, status=status, detail=detail, scanner="builtin-stub"))
    record_audit(
        db,
        action="file.rescan",
        actor_user_id=actor.id,
        entity_type="file",
        entity_id=str(f.id),
        detail={"status": status},
    )
    db.commit()
    out = _file_out(f)
    out["scan_detail"] = detail
    return out
