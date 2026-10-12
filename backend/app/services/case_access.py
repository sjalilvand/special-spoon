from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseAssignment


def counselor_can_access(db: Session, counselor_id, case: Case) -> bool:
    """مشاور اصلی یا همکار فعال پرونده - بند همکاران پرونده (سند v1.00)"""
    if case.primary_counselor_id == counselor_id:
        return True
    a = db.scalar(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case.id,
            CaseAssignment.counselor_id == counselor_id,
            CaseAssignment.end_at.is_(None),
        )
    )
    return a is not None
