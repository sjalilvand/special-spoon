"""فاز ۲۵ — B41 سند جامع: رضایت‌نامه نسخه‌دار و حاکمیت داده

پوشش:
- انتشار متن رضایت فقط با SYSTEM_ADMIN (نقش دیگر 403)
- نسخه‌گذاری خودکار per-kind و غیرقابل‌تغییر بودن متن (فقط نسخه جدید)
- ثبت رضایت با اتصال به نسخه متن (نسخه غیرفعال/ناموجود = 404)
- ابطال با حفظ سابقه: وضعیت revoked + revoked_at + دلیل؛ حذف فیزیکی ندارد
- ابطال دوباره = 409؛ وضعیت پرونده به‌روز می‌شود
- ابطال → اعلان به ناظر فنی + رخداد audit
"""
import uuid
from datetime import date

from conftest import bearer, login

def _h(client, who):
    """توکن Bearer بر اساس نام کاربری - الگوی سایر تست‌های مخزن."""
    return bearer(login(client, who))


API = "/api/v1"

BODY_V1 = "متن رضایت‌نامه درمان نسخه یک: پردازش داده‌های بالینی برای ارائه خدمات مشاوره بر اساس رضایت آگاهانه انجام می‌شود."
BODY_V2 = "متن رضایت‌نامه درمان نسخه دو: شرایط نگهداری داده و مدت نگهداری مطابق سیاست مصوب به‌روزرسانی شد."


def _mk_case(client, env, suffix):
    from app.models.case import Case
    from app.models.people import Applicant
    db = env["db"]
    app_row = Applicant(external_id=f"T-EXT-CNS-{suffix}", first_name="متقاضی",
                        last_name=f"رضایت{suffix}", status="active", record_source="manual", user_id=None)
    db.add(app_row)
    db.flush()
    case = Case(case_number=f"RS-CNS-{suffix}", applicant_id=app_row.id,
                acceptance_date=date.today(), status="active", version=1)
    db.add(case)
    db.commit()
    return case.id


def _grant(client, env, case_id, kind="treatment", consent_version_id=None):
    payload = {"status": "granted", "kind": kind, "note": "رضایت شفاهی حضوری"}
    if consent_version_id:
        payload["consent_version_id"] = consent_version_id
    r = client.post(f"{API}/cases/{case_id}/consents", json=payload, headers=_h(client, "t_reception"))
    assert r.status_code == 201, r.text
    return r


def test_publish_version_admin_only(client, env):
    # نقش غیرمجاز
    r = client.post(f"{API}/consent-versions", json={"kind": "treatment", "title": "رضایت درمان",
                                                     "body": BODY_V1},
                    headers=_h(client, "t_reception"))
    assert r.status_code == 403
    # مدیر سامانه مجاز
    r2 = client.post(f"{API}/consent-versions", json={"kind": "treatment", "title": "رضایت درمان",
                                                      "body": BODY_V1},
                     headers=_h(client, "t_admin"))
    assert r2.status_code == 201, r2.text
    assert r2.json()["version"] == 1


def test_version_immutability_increment(client, env):
    """انتشار دوباره همان kind → نسخه جدید؛ متن نسخه ۱ دست‌نخورده می‌ماند."""
    r1 = client.post(f"{API}/consent-versions", json={"kind": "data_share", "title": "اشتراک داده",
                                                      "body": BODY_V1},
                     headers=_h(client, "t_admin"))
    assert r1.status_code == 201
    v1_id = r1.json()["id"]
    r2 = client.post(f"{API}/consent-versions", json={"kind": "data_share", "title": "اشتراک داده",
                                                      "body": BODY_V2},
                     headers=_h(client, "t_admin"))
    assert r2.status_code == 201
    assert r2.json()["version"] == 2 and r2.json()["id"] != v1_id

    lst = client.get(f"{API}/consent-versions?kind=data_share", headers=_h(client, "t_admin")).json()
    v1 = [x for x in lst["items"] if x["id"] == v1_id]
    assert v1 and v1[0]["version"] == 1  # سابقه حفظ شده


def test_grant_with_version_link_and_invalid_version(client, env):
    case_id = _mk_case(client, env, "G1")
    cv = client.post(f"{API}/consent-versions", json={"kind": "treatment", "title": "رضایت درمان",
                                                      "body": BODY_V1},
                     headers=_h(client, "t_admin")).json()
    r = _grant(client, env, case_id, consent_version_id=cv["id"])
    items = r.json()["consents"]
    last = items[0]
    assert last["kind"] == "treatment"
    assert last["consent_version_id"] == cv["id"]

    # نسخه ناموجود
    r2 = client.post(f"{API}/cases/{case_id}/consents",
                     json={"status": "granted", "consent_version_id": str(uuid.uuid4())},
                     headers=_h(client, "t_reception"))
    assert r2.status_code == 404


def test_revoke_preserves_history(client, env):
    case_id = _mk_case(client, env, "G2")
    r = _grant(client, env, case_id)
    consent_id = r.json()["consents"][0]["id"]

    # ابطال دوباره بعد از ابطال = 409؛ اول ابطال معتبر
    rv = client.post(f"{API}/consents/{consent_id}/revoke",
                     json={"reason": "متقاضی رضایت را پس گرفت"}, headers=_h(client, "t_super"))
    assert rv.status_code == 200, rv.text
    body = rv.json()
    assert body["status"] == "revoked" and body["revoked_at"] is not None

    rv2 = client.post(f"{API}/consents/{consent_id}/revoke",
                      json={"reason": "دوباره"}, headers=_h(client, "t_super"))
    assert rv2.status_code == 409

    # سابقه در جزئیات پرونده حفظ شده (حذف فیزیکی نشده)
    detail = client.get(f"{API}/cases/{case_id}", headers=_h(client, "t_reception")).json()
    cons = [c for c in detail["consents"] if c["id"] == consent_id]
    assert cons and cons[0]["status"] == "revoked" and cons[0]["revoke_reason"] == "متقاضی رضایت را پس گرفت"
    # وضعیت پرونده به‌روز شده
    assert detail["consent_status"] == "revoked"


def test_revoke_notifies_supervisor_and_audit(client, env):
    case_id = _mk_case(client, env, "G3")
    r = _grant(client, env, case_id)
    consent_id = r.json()["consents"][0]["id"]
    client.post(f"{API}/consents/{consent_id}/revoke",
                json={"reason": "ابطال برای تست اعلان"}, headers=_h(client, "t_reception"))

    items = client.get(f"{API}/notifications", headers=_h(client, "t_super")).json()
    assert [x for x in items["items"] if x["event_code"] == "consent.revoked" and x["entity_id"] == str(case_id)]

    audit = client.get(f"{API}/audit-events?limit=50", headers=_h(client, "t_admin")).json()
    actions = [x["action"] for x in audit["items"]]
    assert "consent.revoked" in actions


def test_list_versions_requires_auth(client):
    r = client.get(f"{API}/consent-versions")
    assert r.status_code == 401
