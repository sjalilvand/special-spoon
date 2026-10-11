from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.case import Case, CaseStatus
from app.models.people import Applicant, Counselor

router = APIRouter(tags=["supervisor"])


@router.get("/worklists/supervised-cases")
def supervised_cases(db: Session = Depends(get_db), _actor=Depends(require_roles("TECHNICAL_SUPERVISOR"))) -> dict:
    """کارتابل مسئول فنی - پرونده‌های محدوده نظارت (بند ۹.۴)."""
    rows = db.execute(
        select(Case, Applicant, Counselor)
        .join(Applicant, Case.applicant_id == Applicant.id)
        .outerjoin(Counselor, Case.primary_counselor_id == Counselor.id)
        .where(Case.status.in_((CaseStatus.ACTIVE, CaseStatus.SUSPENDED)))
        .order_by(Case.created_at.desc())
        .limit(100)
    ).all()
    items = [{
        "id": str(c.id),
        "case_number": c.case_number,
        "applicant_name": f"{a.first_name} {a.last_name}",
        "counselor_name": (f"{cc.first_name} {cc.last_name}" if cc else None),
        "acceptance_date": c.acceptance_date.isoformat(),
        "status": c.status,
    } for c, a, cc in rows]
    return {"items": items}
