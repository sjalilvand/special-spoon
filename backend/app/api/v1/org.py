from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.people import OrganizationUnit, ServiceLocation

router = APIRouter(prefix="/org", tags=["org"])


@router.get("/units")
def list_units(db: Session = Depends(get_db), _actor=Depends(get_current_user)) -> dict:
    items = db.scalars(
        select(OrganizationUnit).where(OrganizationUnit.is_active.is_(True)).order_by(OrganizationUnit.title)
    ).all()
    return {"items": [{"id": str(u.id), "code": u.code, "title": u.title} for u in items]}


@router.get("/locations")
def list_locations(db: Session = Depends(get_db), _actor=Depends(get_current_user)) -> dict:
    items = db.scalars(
        select(ServiceLocation).where(ServiceLocation.is_active.is_(True)).order_by(ServiceLocation.title)
    ).all()
    return {"items": [{"id": str(l.id), "code": l.code, "title": l.title} for l in items]}
