from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

app.include_router(health_router, prefix=settings.api_prefix, tags=["health"])


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "status": "ok"}
