"""فاز ۸۹ — نشست یک‌ساعتهٔ فراخوان همکاری + تشکیل پرونده در حجم بالا.

پوشش:
- GET /farakhan/meta نشست یک‌ساعته صادر می‌کند (session_id + session_ttl_seconds=3600)
- ثبت بدون نشست / نشست بی‌اعتبار → 422 با پیام «مهلت یک‌ساعته…» (پیش از مصرف کپچا)
- ثبت با نشست سالم → اعتبارسنجی به مرحلهٔ کپچا می‌رسد (کپچای غلط → 422 کپچا)
- ماتریس نقش پرونده: SYSTEM_ADMIN می‌بیند/می‌سازد؛ RECEPTION گزینهٔ مشاور دارد؛
  COUNSELOR می‌تواند پرونده بسازد و در counselor-options «خودش» را می‌بیند
- applicant-options: فیلتر org_id (سازمان) + خطای uuid نامعتبر
"""

from __future__ import annotations

import uuid

from app.models.org_contract import Organization
from app.models.people import Applicant

from conftest import bearer, login


def _mk_plain_applicant(env, ext: str, code: str):
    """متقاضی بدون کاربر مرتبط — تا پرونده‌های آزمایشی، خلاصهٔ متقاضیِ فاز ۹ را نشکند"""
    db = env["db"]
    ap = Applicant(external_id=ext, employee_code=code, national_id=None,
                   first_name="پرونده", last_name="آزمونی", status="active",
                   record_source="manual")
    db.add(ap)
    db.commit()
    return ap


# ---------------------------------------------------------------- فراخوان: نشست یک‌ساعته
def test_farakhan_meta_issues_one_hour_session(client):
    r1 = client.get("/api/v1/farakhan/meta")
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["session_id"], "meta باید session_id صادر کند"
    assert body["session_ttl_seconds"] == 3600
    r2 = client.get("/api/v1/farakhan/meta")
    # هر بار نشست تازه (اولین ورود، مرجع شمارش معکوس مرورگر)
    assert r2.json()["session_id"] != body["session_id"]


def _payload(**over):
    base = {
        "first_name": "آزمون", "last_name": "فراخوانی", "national_code": "0123456789",
        "gender": "female", "birth_date": "1370/01/01",
        "education_degree": "bachelor", "education_field": "روان‌شناسی",
        "license_status": "none", "center_ownership": "rented",
        "province_name": "تهران", "county_name": "تهران",
        "phone": "02112345678",
        "individual_rooms": 1, "group_rooms": 0, "child_rooms": 0, "counselors_count": 1,
        "has_waiting_space": True, "accepts_company_pattern": False, "has_accessibility": False,
        "terms_accepted": True,
        "captcha_id": "whatever", "captcha_answer": "99",
        "session_id": "whatever",
    }
    base.update(over)
    return base


def _submit(client, payload):
    return client.post(
        "/api/v1/farakhan/submissions",
        data={"payload": __import__("json").dumps(payload, ensure_ascii=False)},
    )


def test_farakhan_submit_without_session_rejected(client):
    payload = _payload()
    payload.pop("session_id")
    r = _submit(client, payload)
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    # pydantic «Field required» با برچسب فیلد نقشه می‌شود
    assert any("نشست" in (k or "") or "required" in v for k, v in errors.items()), errors


def test_farakhan_submit_with_stale_session_rejected(client):
    r = _submit(client, _payload(session_id="stale-or-forged-session"))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    all_msg = " ".join(str(v) for v in errors.values())
    assert "مهلت یک‌ساعته" in all_msg, errors


def test_farakhan_submit_with_valid_session_reaches_captcha(client):
    meta = client.get("/api/v1/farakhan/meta").json()
    r = _submit(client, _payload(session_id=meta["session_id"]))
    # نشست سالم → اعتبارسنجی از نشست می‌گذرد و به کپچا می‌رسد (کپچای آزمایشی غلط است)
    assert r.status_code == 422, r.text
    all_msg = " ".join(str(v) for v in r.json()["detail"]["errors"].values())
    assert "کپچا" in all_msg, all_msg


# ---------------------------------------------------------------- پرونده: ماتریس نقش + جست‌وجو
def test_system_admin_can_list_and_create_cases(client, env):
    tok = login(client, "t_admin")
    r = client.get("/api/v1/cases", headers=bearer(tok))
    assert r.status_code == 200, r.text
    ap = _mk_plain_applicant(env, "T-EXT-89A", "8902")
    r = client.post("/api/v1/cases", headers=bearer(tok),
                    json={"applicant_id": str(ap.id), "priority": "normal"})
    assert r.status_code == 201, r.text


def test_reception_can_read_counselor_options(client):
    tok = login(client, "t_reception")
    r = client.get("/api/v1/cases/counselor-options", headers=bearer(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "self_counselor" in body
    assert body["self_counselor"] is None  # پذیرش مشاور نیست


def test_counselor_sees_self_and_can_create_case(client, env):
    tok = login(client, "t_counsa")
    r = client.get("/api/v1/cases/counselor-options", headers=bearer(tok))
    assert r.status_code == 200, r.text
    self_row = r.json()["self_counselor"]
    assert self_row is not None
    assert self_row["id"] == str(env["counselor_a"].id)
    assert "مشاورالف" in self_row["label"]

    ap = _mk_plain_applicant(env, "T-EXT-89B", "8903")
    r = client.post("/api/v1/cases", headers=bearer(tok),
                    json={"applicant_id": str(ap.id),
                          "counselor_id": self_row["id"], "priority": "normal"})
    assert r.status_code == 201, r.text
    assert r.json()["primary_counselor_name"] is not None


def test_applicant_options_org_filter(client, env):
    db = env["db"]
    org = Organization(name="سازمان آزمون ۸۹", slug="test-org-89")
    db.add(org)
    db.flush()
    ap = Applicant(external_id="T-EXT-89", employee_code="8901", national_id=None,
                   first_name="سمیه", last_name="سازمانی", status="active",
                   record_source="manual", organization_id=org.id)
    db.add(ap)
    db.commit()

    tok = login(client, "t_admin")
    r = client.get("/api/v1/cases/applicant-options", headers=bearer(tok),
                   params={"org_id": str(org.id)})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(x["id"] == str(ap.id) for x in items), items
    labels = [x["label"] for x in items]
    assert all("سازمانی" in l for l in labels)  # فقط همین سازمان

    r = client.get("/api/v1/cases/applicant-options", headers=bearer(tok),
                   params={"org_id": str(org.id), "search": "سمیه"})
    assert r.status_code == 200 and len(r.json()["items"]) == 1

    # counselor هم حق جست‌وجوی متقاضی دارد (برای تشکیل پرونده)
    tok_c = login(client, "t_counsb")
    r = client.get("/api/v1/cases/applicant-options", headers=bearer(tok_c),
                   params={"org_id": str(org.id)})
    assert r.status_code == 200, r.text

    r = client.get("/api/v1/cases/applicant-options", headers=bearer(tok),
                   params={"org_id": "not-a-uuid"})
    assert r.status_code == 422, r.text

    # uuid تصادفی بدون عضو → خالی
    r = client.get("/api/v1/cases/applicant-options", headers=bearer(tok),
                   params={"org_id": str(uuid.uuid4())})
    assert r.status_code == 200 and r.json()["items"] == []
