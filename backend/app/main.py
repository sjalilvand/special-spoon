from fastapi import FastAPI

from app.api.v1.ai import router as ai_router
from app.api.v1.applicants import router as applicants_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.assessments import router as assessments_router
from app.api.v1.accounting import router as accounting_router
from app.api.v1.auth import router as auth_router
from app.api.v1.branches import router as branches_router
from app.api.v1.cases import router as cases_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.consents import router as consents_router
from app.api.v1.files import router as files_router
from app.api.v1.counselors import router as counselors_router
from app.api.v1.clinical import router as clinical_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.discounts import router as discounts_router
from app.api.v1.email_outbox import router as email_outbox_router
from app.api.v1.health import router as health_router
from app.api.v1.intake import router as intake_router
from app.api.v1.imports import router as imports_router
from app.api.v1.learning import router as learning_router
from app.api.v1.me import router as me_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.org import router as org_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.payments import router as payments_router
from app.api.v1.public import router as public_router
from app.api.v1.psych_tests import router as psych_tests_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.referrals import router as referrals_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.reports import router as reports_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.staff_site import router as staff_site_router
from app.api.v1.support import router as support_router
from app.api.v1.supervisor import router as supervisor_router
from app.api.v1.topics import router as topics_router
from app.api.v1.users import router as users_router
from app.api.v1.verification import router as verification_router
from app.api.v1.wallet import router as wallet_router
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
app.include_router(accounting_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(org_router, prefix=settings.api_prefix)
app.include_router(topics_router, prefix=settings.api_prefix)
app.include_router(organizations_router, prefix=settings.api_prefix)
app.include_router(counselors_router, prefix=settings.api_prefix)
app.include_router(applicants_router, prefix=settings.api_prefix)
app.include_router(imports_router, prefix=settings.api_prefix)
app.include_router(cases_router, prefix=settings.api_prefix)
app.include_router(assessments_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(consents_router, prefix=settings.api_prefix)
app.include_router(files_router, prefix=settings.api_prefix)
app.include_router(appointments_router, prefix=settings.api_prefix)
app.include_router(sessions_router, prefix=settings.api_prefix)
app.include_router(recommendations_router, prefix=settings.api_prefix)
app.include_router(me_router, prefix=settings.api_prefix)
app.include_router(supervisor_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)
app.include_router(clinical_router, prefix=settings.api_prefix)
app.include_router(intake_router, prefix=settings.api_prefix)
app.include_router(referrals_router, prefix=settings.api_prefix)
app.include_router(public_router, prefix=settings.api_prefix)
app.include_router(staff_site_router, prefix=settings.api_prefix)
app.include_router(compliance_router, prefix=settings.api_prefix)
app.include_router(email_outbox_router, prefix=settings.api_prefix)
app.include_router(catalog_router, prefix=settings.api_prefix)
app.include_router(verification_router, prefix=settings.api_prefix)
app.include_router(branches_router, prefix=settings.api_prefix)
app.include_router(payments_router, prefix=settings.api_prefix)
app.include_router(wallet_router, prefix=settings.api_prefix)
app.include_router(discounts_router, prefix=settings.api_prefix)
app.include_router(refunds_router, prefix=settings.api_prefix)
app.include_router(learning_router, prefix=settings.api_prefix)
app.include_router(support_router, prefix=settings.api_prefix)
app.include_router(psych_tests_router, prefix=settings.api_prefix)
app.include_router(ai_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "status": "ok"}
