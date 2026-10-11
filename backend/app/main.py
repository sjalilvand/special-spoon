from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
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


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "status": "ok"}
