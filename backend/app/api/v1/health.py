from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
