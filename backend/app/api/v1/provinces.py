"""فاز ۶۴ - جدول پایهٔ استان‌ها (کد رسمی ۰۱..۳۱) برای انتخاب/نمایش استان.

فهرست عمومی برای هر کاربر واردشده؛ به‌عنوان مرجع کد استان در فرم‌ها و
فایل ورود مشاوران استفاده می‌شود.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.location import Province

router = APIRouter(prefix="/provinces", tags=["provinces"])


class ProvinceOut(BaseModel):
    code: str
    name: str
    capital: str | None
    area_code: str | None
    is_active: bool


@router.get("")
def list_provinces(db: Session = Depends(get_db), _user=Depends(get_current_user)) -> dict:
    items = db.scalars(select(Province).order_by(Province.code)).all()
    return {
        "items": [
            ProvinceOut(
                code=p.code, name=p.name, capital=p.capital,
                area_code=p.area_code, is_active=p.is_active,
            ).model_dump()
            for p in items
        ],
        "total": len(items),
    }
