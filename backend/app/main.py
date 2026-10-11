from fastapi import FastAPI

from app.api.v1.applicants import router as applicants_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.assessments import router as assessments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.counselors import router as counselors_router
from app.api.v1.health import router as health_router
from app.api.v1.imports import router as imports_router
from app.api.v1.org import router as org_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.users import router as users_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

app.include_router(health_router, prefix=settings.api_prefix, tags=["health"])
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(org_router, prefix=settings.api_prefix)
app.include_router(counselors_router, prefix=settings.api_prefix)
app.include_router(applicants_router, prefix=settings.api_prefix)
app.include_router(imports_router, prefix=settings.api_prefix)
app.include_router(cases_router, prefix=settings.api_prefix)
app.include_router(assessments_router, prefix=settings.api_prefix)
app.include_router(appointments_router, prefix=settings.api_prefix)
app.include_router(sessions_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "status": "ok"}
