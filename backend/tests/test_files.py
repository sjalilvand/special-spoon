"""فاز ۲۵ — B39 سند جامع: بارگذاری و دانلود امن فایل

پوشش:
- آپلود معتبر → scan_status=clean + sha256 ثبت می‌شود
- سقف حجم (413) و فایل خالی (422)
- فایل اجرایی/MIME خارج از فهرست → قرنطینه (quarantined)
- فایل قرنطینه بلیت دانلود نمی‌گیرد (403)
- کنترل دسترسی: مشاور غیرتخصیص‌یافته 404؛ بدون توکن 401
- بلیت دانلود: معتبر کار می‌کند، بدون بلیت 401، بلیت دستکاری‌شده 401،
  بلیت فایل دیگر 401، انقضا با تنظیم TTL کوتاه
- فهرست فایل‌های پرونده فقط برای مجاز
"""
import os
import time
import uuid
from datetime import date

from conftest import bearer, login

def _h(client, who):
    """توکن Bearer بر اساس نام کاربری - الگوی سایر تست‌های مخزن."""
    return bearer(login(client, who))


API = "/api/v1"

PDF_BYTES = b"%PDF-1.4\n%phase25-test-file\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _mk_case(client, env, suffix):
    from app.models.case import Case, CaseAssignment
    from app.models.people import Applicant
    db = env["db"]
    app_row = Applicant(external_id=f"T-EXT-FL-{suffix}", first_name="متقاضی",
                        last_name=f"فایل{suffix}", status="active", record_source="manual", user_id=None)
    db.add(app_row)
    db.flush()
    case = Case(case_number=f"RS-FL-{suffix}", applicant_id=app_row.id,
                acceptance_date=date.today(),
                primary_counselor_id=env["counselor_a"].id, status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="تست فایل"))
    db.commit()
    return case.id


def _upload(client, env, case_id, name="گزارش.pdf", content=PDF_BYTES, mime="application/pdf"):
    r = client.post(f"{API}/files/upload",
                    files={"file": (name, content, mime)},
                    data={"case_id": str(case_id), "context": "case_document"},
                    headers=_h(client, "t_reception"))
    return r


def test_upload_clean_with_checksum(client, env):
    case_id = _mk_case(client, env, "U1")
    r = _upload(client, env, case_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scan_status"] == "clean"
    assert len(body["sha256"]) == 64
    assert body["sensitivity"] == "confidential"


def test_upload_rejects_oversize_and_empty(client, env):
    case_id = _mk_case(client, env, "U2")
    # خالی
    r0 = _upload(client, env, case_id, name="خالی.pdf", content=b"")
    assert r0.status_code == 422
    # بیش از سقف: env override نمی‌شود چون settings کش شده؛ 11 مگابایت می‌سازیم
    big = b"x" * (10 * 1024 * 1024 + 1)
    r1 = _upload(client, env, case_id, name="بزرگ.pdf", content=big)
    assert r1.status_code == 413


def test_executable_goes_to_quarantine(client, env):
    case_id = _mk_case(client, env, "U3")
    r = _upload(client, env, case_id, name="نرم‌افزار.exe", content=b"MZ...",
                mime="application/x-msdownload")
    assert r.status_code == 201, r.text
    assert r.json()["scan_status"] == "quarantined"
    fid = r.json()["id"]
    # قرنطینه بلیت نمی‌گیرد
    rt = client.post(f"{API}/files/{fid}/download-ticket", headers=_h(client, "t_reception"))
    assert rt.status_code == 403


def test_access_control(client, env):
    case_id = _mk_case(client, env, "U4")
    r = _upload(client, env, case_id)
    fid = r.json()["id"]
    # بدون توکن
    assert client.get(f"{API}/files?case_id={case_id}").status_code == 401
    # مشاور غیرتخصیص‌یافته (مشاور B) → 404
    rb = client.get(f"{API}/files?case_id={case_id}", headers=_h(client, "t_counsb"))
    assert rb.status_code == 404
    # مشاور تخصیص‌یافته → می‌بیند
    ra = client.get(f"{API}/files?case_id={case_id}", headers=_h(client, "t_counsa"))
    assert ra.status_code == 200 and any(x["id"] == fid for x in ra.json()["items"])


def test_download_ticket_flow(client, env):
    case_id = _mk_case(client, env, "U5")
    fid = _upload(client, env, case_id).json()["id"]
    # بدون بلیت
    r0 = client.get(f"{API}/files/{fid}/download")
    assert r0.status_code == 401
    # بلیت معتبر
    rt = client.post(f"{API}/files/{fid}/download-ticket", headers=_h(client, "t_reception"))
    assert rt.status_code == 200, rt.text
    ticket = rt.json()["ticket"]
    rd = client.get(f"{API}/files/{fid}/download", params={"ticket": ticket})
    assert rd.status_code == 200
    assert rd.content.startswith(b"%PDF")
    # بلیت دستکاری‌شده
    r1 = client.get(f"{API}/files/{fid}/download", params={"ticket": ticket[:-2] + "aa"})
    assert r1.status_code == 401
    # بلیت فایل دیگر
    fid2 = _upload(client, env, case_id, name="دوم.pdf").json()["id"]
    r2 = client.get(f"{API}/files/{fid2}/download", params={"ticket": ticket})
    assert r2.status_code == 401


def test_ticket_expiry(client, env, monkeypatch=None):
    """بلیت منقضی پذیرفته نمی‌شود — TTL را موقتاً صفر می‌کنیم."""
    import app.core.config as cfg
    case_id = _mk_case(client, env, "U6")
    fid = _upload(client, env, case_id).json()["id"]
    settings = cfg.get_settings()
    original = settings.download_ticket_seconds
    object.__setattr__(settings, "download_ticket_seconds", -1)
    try:
        rt = client.post(f"{API}/files/{fid}/download-ticket", headers=_h(client, "t_reception"))
        assert rt.status_code == 200
        rd = client.get(f"{API}/files/{fid}/download", params={"ticket": rt.json()["ticket"]})
        assert rd.status_code == 401  # منقضی
    finally:
        object.__setattr__(settings, "download_ticket_seconds", original)


def test_rescan_admin_only(client, env):
    case_id = _mk_case(client, env, "U7")
    fid = _upload(client, env, case_id).json()["id"]
    r = client.post(f"{API}/files/{fid}/rescan", headers=_h(client, "t_reception"))
    assert r.status_code == 403
    r2 = client.post(f"{API}/files/{fid}/rescan", headers=_h(client, "t_admin"))
    assert r2.status_code == 200 and r2.json()["scan_status"] in ("clean", "quarantined")
