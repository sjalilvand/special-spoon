"""فاز ۳۷ - ADR-04 سند جامع: Object Storage پلاگین‌پذیر + گام اول E2E.

- ADR-04 (همان الگوی D02/D03/D07/B28):
  · پیش‌فرض local بدون کلید — store/open حذف می‌شود و sha256 درست است؛
  · s3 بدون کلید/endpoint → fallback به local (fail-soft) با گزارش شفاف؛
  · s3 با آداپتور موک‌شده → پروایدر واقعی «s3» ثبت می‌شود؛
  · خطای سرویس S3 در آپلود → ذخیره محلی با همان کلید + فایل گم نمی‌شود؛
  · دانلود/اسکن مجدد همیشه از پروایدرِ ردیف فایل می‌خواند (نه config جاری)؛
  · /integrations/config شامل storage بدون هیچ کلیدی (تزریق کلید آشکار نمی‌شود)؛
  · ستون files.storage با migration 0025 موجود است (پیش‌فرض local).
- گام اول E2E: اسکلت Playwright در frontend/e2e/ است و به pytest ربطی ندارد؛
  اجرای آن روی سیستم توسعه طبق README همان پوشه انجام می‌شود.
"""
import hashlib
import uuid as uuid_mod
from datetime import date

import pytest

import app.services.object_storage as objstore
from conftest import bearer, login
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.case import Case
from app.models.file import StoredFile

API = "/api/v1"
PDF_BYTES = b"%PDF-1.4\n%phase37-storage-test\ntrailer\n<<>>\n%%EOF"

_SETTINGS_KEYS = (
    "storage_backend", "s3_endpoint_url", "s3_bucket",
    "s3_access_key", "s3_secret_key", "upload_dir",
)


@pytest.fixture()
def st():
    """تنظیمات با بازیابی حالت پس از هر آزمون (مونو‌تون بودن singleton حفظ شود)."""
    s = get_settings()
    orig = {k: getattr(s, k) for k in _SETTINGS_KEYS}
    yield s
    for k, v in orig.items():
        setattr(s, k, v)


@pytest.fixture()
def admin_headers(client, env):
    return bearer(login(client, "t_admin"))


@pytest.fixture()
def reception_headers(client, env):
    return bearer(login(client, "t_reception"))


def _mk_case(env, suffix) -> uuid_mod.UUID:
    from app.models.case import Case, CaseAssignment
    from app.models.people import Applicant
    db = env["db"]
    a = Applicant(external_id=f"T-EXT-S37-{suffix}", first_name="متقاضی",
                  last_name=f"ذخیره{suffix}", status="active", record_source="manual", user_id=None)
    db.add(a)
    db.flush()
    case = Case(case_number=f"RS-S37-{suffix}", applicant_id=a.id, acceptance_date=date.today(),
                primary_counselor_id=env["counselor_a"].id, status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="فاز ۳۷"))
    db.commit()
    return case.id


# ================================================================ وضعیت آداپتور
def test_adr04_default_local_status(st):
    st.storage_backend = "local"
    st.s3_access_key = ""
    out = objstore.storage_status(st)
    assert out["configured_backend"] == "local"
    assert out["active_backend"] == "local"
    assert out["fallback_applied"] is False
    assert isinstance(out["boto3_available"], bool)


def test_adr04_s3_without_keys_falls_back_softly(st):
    st.storage_backend = "s3"
    st.s3_endpoint_url = ""
    st.s3_access_key = ""
    active, fb = objstore.active_backend(st)
    assert (active, fb) == ("local", True)
    out = objstore.storage_status(st)
    assert out["active_backend"] == "local" and out["fallback_applied"] is True


def test_adr04_invalid_backend_name_coerces_to_local(st):
    st.storage_backend = "gdrive"
    assert objstore.configured_backend(st) == "local"
    assert objstore.active_backend(st) == ("local", False)


def test_adr04_s3_ready_requires_all_fields_and_boto3(st, monkeypatch):
    st.storage_backend = "s3"
    st.s3_endpoint_url = "http://minio:9000"
    st.s3_access_key = "k"
    st.s3_secret_key = "s"
    st.s3_bucket = "rosepsy-files"
    assert objstore.s3_ready(st) is True
    st.s3_secret_key = ""
    assert objstore.s3_ready(st) is False
    monkeypatch.setattr(objstore, "boto3_available", lambda: False)
    st.s3_secret_key = "s"
    assert objstore.s3_ready(st) is False


# ================================================================ store / open
def test_adr04_store_local_default(st, tmp_path):
    st.storage_backend = "local"
    st.upload_dir = str(tmp_path)
    provider, key, sha, fb = objstore.store(PDF_BYTES, st)
    assert provider == "local" and fb is False
    assert len(key.split("/")) == 3 and len(key.split("/")[-1]) == 32
    assert sha == hashlib.sha256(PDF_BYTES).hexdigest()
    assert objstore.local_exists(st.upload_dir, key)
    assert objstore.open_bytes(st.upload_dir, "local", key, st) == PDF_BYTES


def test_adr04_store_via_s3_adapter(st, tmp_path, monkeypatch):
    st.upload_dir = str(tmp_path)
    st.storage_backend = "s3"
    st.s3_endpoint_url = "http://minio:9000"
    st.s3_bucket = "rosepsy-files"
    st.s3_access_key = "k"
    st.s3_secret_key = "s"
    calls = []
    monkeypatch.setattr(objstore, "_s3_put", lambda s, key, data: calls.append((key, data)))
    provider, key, sha, fb = objstore.store(PDF_BYTES, st)
    assert provider == "s3" and fb is False and len(calls) == 1
    assert calls[0][1] == PDF_BYTES
    assert not objstore.local_exists(st.upload_dir, key)  # محلی ربطی ندارد


def test_adr04_store_s3_error_falls_back_to_local(st, tmp_path, monkeypatch):
    st.upload_dir = str(tmp_path)
    st.storage_backend = "s3"
    st.s3_endpoint_url = "http://minio:9000"
    st.s3_bucket = "rosepsy-files"
    st.s3_access_key = "k"
    st.s3_secret_key = "s"

    def boom(s, key, data):
        raise ConnectionError("minio unreachable")

    monkeypatch.setattr(objstore, "_s3_put", boom)
    provider, key, sha, fb = objstore.store(PDF_BYTES, st)
    assert provider == "local" and fb is True
    assert objstore.local_exists(st.upload_dir, key)  # فایل گم نمی‌شود
    assert sha == hashlib.sha256(PDF_BYTES).hexdigest()


def test_adr04_open_bytes_reads_from_row_provider(st, tmp_path, monkeypatch):
    st.upload_dir = str(tmp_path)
    st.storage_backend = "s3"
    st.s3_endpoint_url = "http://minio:9000"
    st.s3_bucket = "b"
    st.s3_access_key = "k"
    st.s3_secret_key = "s"
    monkeypatch.setattr(objstore, "_s3_get", lambda s, key: b"S3-CONTENT")
    # حتی اگر config جاری s3 باشد، پروایدر local از دیسک می‌خواند
    key = f"2026/10/{uuid_mod.uuid4().hex}"
    objstore.fs.save_bytes_at_key(st.upload_dir, key, b"LOCAL-CONTENT")
    assert objstore.open_bytes(st.upload_dir, "local", key, st) == b"LOCAL-CONTENT"
    assert objstore.open_bytes(st.upload_dir, "s3", key, st) == b"S3-CONTENT"


# ================================================================ API - آپلود/دانلود
def test_adr04_upload_default_local_and_download_roundtrip(client, env, st, tmp_path, reception_headers):
    st.upload_dir = str(tmp_path)
    case_id = _mk_case(env, "A")
    r = client.post(f"{API}/files/upload",
                    files={"file": ("گزارش.pdf", PDF_BYTES, "application/pdf")},
                    data={"case_id": str(case_id)},
                    headers=reception_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["storage"] == "local"
    assert body["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()

    t = client.post(f"{API}/files/{body['id']}/download-ticket", headers=reception_headers)
    assert t.status_code == 200
    d = client.get(f"{API}/files/{body['id']}/download", params={"ticket": t.json()["ticket"]})
    assert d.status_code == 200 and d.content == PDF_BYTES


def test_adr04_upload_with_s3_config_uses_adapter(client, env, st, tmp_path, monkeypatch, reception_headers):
    st.upload_dir = str(tmp_path)
    st.storage_backend = "s3"
    st.s3_endpoint_url = "http://minio:9000"
    st.s3_bucket = "rosepsy-files"
    st.s3_access_key = "k"
    st.s3_secret_key = "s"
    puts = []
    monkeypatch.setattr(objstore, "_s3_put", lambda s, key, data: puts.append(key))
    monkeypatch.setattr(objstore, "_s3_get", lambda s, key: PDF_BYTES)
    case_id = _mk_case(env, "B")
    r = client.post(f"{API}/files/upload",
                    files={"file": ("گزارش.pdf", PDF_BYTES, "application/pdf")},
                    data={"case_id": str(case_id)},
                    headers=reception_headers)
    assert r.status_code == 201, r.text
    assert r.json()["storage"] == "s3" and len(puts) == 1
    t = client.post(f"{API}/files/{r.json()['id']}/download-ticket", headers=reception_headers)
    d = client.get(f"{API}/files/{r.json()['id']}/download", params={"ticket": t.json()["ticket"]})
    assert d.status_code == 200 and d.content == PDF_BYTES  # از آداپتور s3 خوانده شد


def test_adr04_s3_outage_on_upload_falls_back_with_detail(client, env, st, tmp_path, monkeypatch, reception_headers):
    st.upload_dir = str(tmp_path)
    st.storage_backend = "s3"
    st.s3_endpoint_url = "http://minio:9000"
    st.s3_bucket = "rosepsy-files"
    st.s3_access_key = "k"
    st.s3_secret_key = "s"

    def boom(s, key, data):
        raise ConnectionError("minio down")

    monkeypatch.setattr(objstore, "_s3_put", boom)
    case_id = _mk_case(env, "C")
    r = client.post(f"{API}/files/upload",
                    files={"file": ("گزارش.pdf", PDF_BYTES, "application/pdf")},
                    data={"case_id": str(case_id)},
                    headers=reception_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["storage"] == "local"
    assert "بازگشت" in (body.get("scan_detail") or "")
    # دانلود از همان ردیف local کار می‌کند
    t = client.post(f"{API}/files/{body['id']}/download-ticket", headers=reception_headers)
    d = client.get(f"{API}/files/{body['id']}/download", params={"ticket": t.json()["ticket"]})
    assert d.status_code == 200 and d.content == PDF_BYTES


def test_adr04_rescan_reads_from_row_provider(client, env, st, tmp_path, monkeypatch, admin_headers):
    st.upload_dir = str(tmp_path)
    db = SessionLocal()
    try:
        case_id = _mk_case(env, "D")
        key = f"2026/10/{uuid_mod.uuid4().hex}"
        objstore.fs.save_bytes_at_key(st.upload_dir, key, PDF_BYTES)
        f = StoredFile(case_id=case_id, context="case_document", original_name="قدیمی.pdf",
                       mime="application/pdf", size_bytes=len(PDF_BYTES),
                       sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
                       storage_key=key, storage="local", sensitivity="confidential",
                       scan_status="clean")
        db.add(f)
        db.commit()
        fid = str(f.id)
    finally:
        db.close()
    r = client.post(f"{API}/files/{fid}/rescan", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["storage"] == "local" and r.json()["scan_status"] == "clean"


def test_adr04_row_provider_s3_download_via_mock(client, env, st, tmp_path, monkeypatch, reception_headers):
    """ردیف s3: دانلود از آداپتور s3 انجام می‌شود حتی اگر config جاری local باشد."""
    st.upload_dir = str(tmp_path)
    db = SessionLocal()
    try:
        case_id = _mk_case(env, "E")
        f = StoredFile(case_id=case_id, context="case_document", original_name="ابری.pdf",
                       mime="application/pdf", size_bytes=len(PDF_BYTES),
                       sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
                       storage_key="2026/10/cloud-key", storage="s3",
                       sensitivity="confidential", scan_status="clean")
        db.add(f)
        db.commit()
        fid = str(f.id)
    finally:
        db.close()
    monkeypatch.setattr(objstore, "_s3_get", lambda s, key: PDF_BYTES if key.endswith("cloud-key") else b"x")
    st.storage_backend = "local"  # config جاری local است؛ ردیف می‌گوید s3
    t = client.post(f"{API}/files/{fid}/download-ticket", headers=reception_headers)
    assert t.status_code == 200
    d = client.get(f"{API}/files/{fid}/download", params={"ticket": t.json()["ticket"]})
    assert d.status_code == 200 and d.content == PDF_BYTES


# ================================================================ شفافیت config
def test_adr04_integrations_config_contains_storage_without_secrets(client, env, st, admin_headers):
    st.s3_access_key = "TOP-SECRET-ACCESS"
    st.s3_secret_key = "TOP-SECRET-SECRET"
    r = client.get(f"{API}/integrations/config", headers=admin_headers)
    assert r.status_code == 200, r.text
    raw = r.text
    data = r.json()["integrations"]
    assert "storage" in data
    stg = data["storage"]
    assert stg["decision"] == "ADR-04"
    assert stg["configured_backend"] == "local"
    assert "TOP-SECRET-ACCESS" not in raw and "TOP-SECRET-SECRET" not in raw
    assert "access_key" not in raw and "secret_key" not in raw


def test_adr04_integrations_config_forbidden_for_applicant(client, env):
    r = client.get(f"{API}/integrations/config", headers=bearer(login(client, "t_appa")))
    assert r.status_code == 403


# ================================================================ مهاجرت DB
def test_adr04_files_storage_column_default_local(env):
    db = SessionLocal()
    try:
        from sqlalchemy import text
        val = db.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name='files' AND column_name='storage'"
        )).scalar()
        assert val is not None and "local" in str(val)
        chk = db.execute(text(
            "SELECT COUNT(*) FROM information_schema.check_constraints WHERE constraint_name='ck_files_storage'"
        )).scalar()
        assert int(chk) >= 1
    finally:
        db.close()
