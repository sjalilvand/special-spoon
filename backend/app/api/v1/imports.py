import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.import_job import ImportJob, ImportRow
from app.models.user import User
from app.schemas.imports import CommitRequest
from app.services import excel_import as xi
from app.services.audit import record_audit

router = APIRouter(prefix="/imports", tags=["imports"])


def _gate(actor: User, import_type: str) -> None:
    allowed = xi.IMPORT_TYPE_ROLES.get(import_type)
    if allowed is None:
        raise HTTPException(status_code=404, detail="نوع ورود نامعتبر است")
    if not {r.code for r in actor.roles} & allowed:
        raise HTTPException(status_code=403, detail="دسترسی به این نوع ورود مجاز نیست")


@router.get("/templates/{import_type}")
def download_template(import_type: str, actor: User = Depends(get_current_user)):
    _gate(actor, import_type)
    data = xi.build_template(import_type)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="rosepsy-{import_type}-template.xlsx"'},
    )


@router.post("/{import_type}/preview")
async def preview_import(import_type: str, file: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    _gate(actor, import_type)
    data = await file.read()
    if len(data) > xi.MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="حجم فایل بیش از ۵ مگابایت است")
    if not data.startswith(b"PK"):
        raise HTTPException(status_code=422, detail="فایل باید xlsx باشد")
    parsed, file_error = xi.parse_file(data, import_type)
    if file_error:
        raise HTTPException(status_code=422, detail=file_error)
    if not parsed:
        raise HTTPException(status_code=422, detail="ردیف داده‌ای در فایل یافت نشد")

    job = ImportJob(
        import_type=import_type,
        importer_user_id=actor.id,
        original_filename=(file.filename or "")[:255],
        file_size=len(data),
        total_rows=len(parsed),
    )
    db.add(job)
    db.flush()

    seen: dict = {}
    summary = {"total": 0, "valid": 0, "error": 0, "duplicate": 0}
    for row in parsed:
        values = row["values"]
        if row["has_formula"]:
            status, error = "error", "سلول فرمول در فایل مجاز نیست"
            clean = values
            result = {"errors": True, "existing_id": None, "will_update": []}
        elif row["type_error"]:
            status, error = "error", row["type_error"]
            clean = values
            result = {"errors": True, "existing_id": None, "will_update": []}
        else:
            result = xi.validate_row(db, import_type, values, seen)
            clean = result["clean"]
            if result["errors"]:
                status, error = "error", "؛ ".join(result["errors"])
            elif result["existing_id"]:
                status, error = "duplicate", None
            else:
                status, error = "valid", None
        summary["total"] += 1
        summary[status] += 1
        db.add(ImportRow(
            job_id=job.id,
            row_number=row["row_number"],
            status=status,
            error_text=error,
            payload=clean,
            existing_id=uuid.UUID(result["existing_id"]) if result.get("existing_id") else None,
            will_update=result.get("will_update") or [],
        ))
    job.valid_rows = summary["valid"]
    job.error_rows = summary["error"]
    job.duplicate_rows = summary["duplicate"]
    db.commit()

    errors = db.scalars(select(ImportRow).where(ImportRow.job_id == job.id, ImportRow.status == "error").order_by(ImportRow.row_number).limit(100)).all()
    dups = db.scalars(select(ImportRow).where(ImportRow.job_id == job.id, ImportRow.status == "duplicate").order_by(ImportRow.row_number).limit(100)).all()
    return {
        "job_id": str(job.id),
        "summary": summary,
        "errors": [{"row_number": r.row_number, "error": r.error_text} for r in errors],
        "duplicates": [{"row_number": r.row_number, "existing_id": str(r.existing_id) if r.existing_id else None, "will_update": r.will_update or []} for r in dups],
    }


@router.post("/{job_id}/commit")
def commit_import(job_id: uuid.UUID, body: CommitRequest, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="عملیات ورود یافت نشد")
    _gate(actor, job.import_type)
    is_admin = "SYSTEM_ADMIN" in {r.code for r in actor.roles}
    if job.importer_user_id != actor.id and not is_admin:
        raise HTTPException(status_code=403, detail="فقط واردکننده عملیات می‌تواند آن را ثبت کند")
    if job.status != "preview":
        raise HTTPException(status_code=409, detail="این عملیات قبلاً ثبت شده است")

    rows = db.scalars(select(ImportRow).where(ImportRow.job_id == job.id).order_by(ImportRow.row_number)).all()
    actor_roles = {r.code for r in actor.roles}
    for row in rows:
        try:
            result = xi.validate_row(db, job.import_type, row.payload or {}, {})
            if result["errors"]:
                row.status = "error"
                row.error_text = "؛ ".join(result["errors"])
            elif result["existing_id"] is None:
                xi.create_records(db, job.import_type, result["clean"], actor_roles)
                row.status = "created"
                row.error_text = None
            else:
                row.existing_id = uuid.UUID(result["existing_id"])
                row.will_update = result["will_update"] or []
                if body.duplicate_strategy == "update" and result["will_update"]:
                    xi.apply_updates(db, job.import_type, result["existing_id"], result["clean"])
                    row.status = "updated"
                else:
                    row.status = "skipped"
            db.commit()  # هر ردیف در تراکنش مستقل - بند ۸.۵ سند
        except ValueError as ve:
            db.rollback()
            fresh = db.get(ImportRow, row.id)
            fresh.status = "error"
            fresh.error_text = str(ve)
            db.commit()
        except Exception:
            db.rollback()
            fresh = db.get(ImportRow, row.id)
            fresh.status = "error"
            fresh.error_text = "خطای ثبت رکورد (احتمال نقض یکتایی)"
            db.commit()

    counts = dict(db.execute(select(ImportRow.status, func.count()).where(ImportRow.job_id == job.id).group_by(ImportRow.status)).all())
    job.created_rows = counts.get("created", 0)
    job.updated_rows = counts.get("updated", 0)
    job.skipped_rows = counts.get("skipped", 0)
    job.error_rows = counts.get("error", 0)
    job.status = "committed"
    job.committed_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db, action="import.committed", actor_user_id=actor.id,
        entity_type="import_job", entity_id=str(job.id),
        detail={"type": job.import_type, "created": job.created_rows, "updated": job.updated_rows,
                "skipped": job.skipped_rows, "errors": job.error_rows},
    )
    return {
        "job_id": str(job.id), "import_type": job.import_type, "status": job.status,
        "total": job.total_rows, "created": job.created_rows, "updated": job.updated_rows,
        "skipped": job.skipped_rows, "errors": job.error_rows,
    }


@router.get("")
def list_jobs(db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    if not {r.code for r in actor.roles} & {"SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"}:
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
    jobs = db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(20)).all()
    return {
        "items": [{
            "id": str(j.id), "import_type": j.import_type, "status": j.status,
            "original_filename": j.original_filename, "total_rows": j.total_rows,
            "created_rows": j.created_rows, "updated_rows": j.updated_rows,
            "skipped_rows": j.skipped_rows, "error_rows": j.error_rows,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        } for j in jobs],
    }


@router.get("/{job_id}/errors")
def job_errors(job_id: uuid.UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="عملیات ورود یافت نشد")
    _gate(actor, job.import_type)
    rows = db.scalars(select(ImportRow).where(ImportRow.job_id == job_id, ImportRow.status == "error").order_by(ImportRow.row_number).limit(500)).all()
    return {"items": [{"row_number": r.row_number, "error": r.error_text} for r in rows]}
