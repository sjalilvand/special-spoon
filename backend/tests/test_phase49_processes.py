"""فاز ۴۹ — B41/B42: فرایندهای نسخه‌دار + مانیتورینگ وضعیت درخواست

پوشش:
- اعتبارسنجی XML BPMN (فاقد definitions → 422؛ معتبر → ساخت)
- ایجاد فرایند + نسخه ۱ منتشرشده؛ کد تکراری → 409؛ دسترسی نقش‌ها
- نسخه جدید: شماره‌گذاری خودکار، بایگانی نسخه منتشرشده قبلی
- انتشار/بایگانی نسخه
- شروع نمونه اجرا روی موضوع؛ جلوگیری از نمونه تکراری در جریان (409)
- ثبت گام (به‌روزرسانی گام فعال) و جلوگیری از ثبت گام پس از پایان (409)
- انتقال وضعیت (تکمیل/لغو/تعلیق/ادامه) با رخداد خودکار
- مانیتورینگ: فیلتر subject_type/subject_id در فهرست نمونه‌ها
- دسترسی: APPLICANT → 403
"""
import uuid

import pytest

from conftest import PASSWORD, bearer, login
from sqlalchemy import select

API = "/api/v1"


@pytest.fixture(autouse=True)
def _ensure_env(env):
    """کاربران آزمون (t_admin و ...) از فیکسچر session-scoped ساخته می‌شوند."""
    return env

BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  id="Defs-{n}" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Proc-{n}" name="فرایند آزمون {n}" isExecutable="false">
    <bpmn:startEvent id="S{n}" name="شروع"/>
    <bpmn:task id="T{n}-1" name="گام اول"/>
    <bpmn:task id="T{n}-2" name="گام دوم"/>
    <bpmn:endEvent id="E{n}" name="پایان"/>
  </bpmn:process>
</bpmn:definitions>
"""

BAD_XML = "<html><body>این BPMN نیست</body></html>"


def _h(client, who):
    return bearer(login(client, who))


def _create_process(client, code, n="1", publish=True):
    return client.post(f"{API}/processes", headers=_h(client, "t_admin"), json={
        "code": code, "title": f"فرایند آزمون {code}", "description": "تست",
        "bpmn_xml": BPMN.format(n=n), "changelog": "نسخه اول", "publish": publish,
    })


# ---------- تعریف فرایند و نسخه ----------

def test_create_process_rejects_bad_xml(client):
    r = client.post(f"{API}/processes", headers=_h(client, "t_admin"), json={
        "code": f"BAD-{uuid.uuid4().hex[:6]}", "title": "فرایند خراب",
        "bpmn_xml": BAD_XML,
    })
    assert r.status_code == 422


def test_create_process_and_version_one(client):
    code = f"RS-T-{uuid.uuid4().hex[:6].upper()}"
    r = _create_process(client, code, n="a")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["code"] == code
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert data["versions"][0]["status"] == "published"
    assert data["current_version"]["version_number"] == 1

    # کد تکراری
    r2 = _create_process(client, code, n="b")
    assert r2.status_code == 409

    # دسترسی: پذیرش اجازه مدیریت ندارد
    r3 = client.post(f"{API}/processes", headers=_h(client, "t_reception"), json={
        "code": f"RS-T-{uuid.uuid4().hex[:6].upper()}", "title": "فرایند",
        "bpmn_xml": BPMN.format(n="c"),
    })
    assert r3.status_code == 403


def test_new_version_archives_previous_published(client):
    code = f"RS-T-{uuid.uuid4().hex[:6].upper()}"
    r = _create_process(client, code, n="d")
    def_id = r.json()["id"]
    r2 = client.post(f"{API}/processes/{def_id}/versions", headers=_h(client, "t_manager"), json={
        "bpmn_xml": BPMN.format(n="d2"), "changelog": "بازنگری دوم", "publish": True,
    })
    assert r2.status_code == 201, r2.text
    v2 = r2.json()
    assert v2["version_number"] == 2 and v2["status"] == "published"

    # نسخه ۱ باید بایگانی شده باشد
    r3 = client.get(f"{API}/processes/{def_id}", headers=_h(client, "t_admin"))
    versions = r3.json()["versions"]
    by_no = {v["version_number"]: v["status"] for v in versions}
    assert by_no[1] == "archived" and by_no[2] == "published"
    assert r3.json()["current_version"]["id"] == v2["id"]

    # نسخه پیش‌نویس (انتشار خودکار نداریم)
    r4 = client.post(f"{API}/processes/{def_id}/versions", headers=_h(client, "t_manager"), json={
        "bpmn_xml": BPMN.format(n="d3"), "changelog": "پیش‌نویس", "publish": False,
    })
    assert r4.status_code == 201
    v3 = r4.json()
    assert v3["status"] == "draft"

    # انتشار دستی نسخه پیش‌نویس
    r5 = client.post(f"{API}/processes/versions/{v3['id']}/publish", headers=_h(client, "t_admin"))
    assert r5.status_code == 200 and r5.json()["status"] == "published"


def test_version_xml_endpoint(client):
    code = f"RS-T-{uuid.uuid4().hex[:6].upper()}"
    r = _create_process(client, code, n="e")
    vid = r.json()["current_version"]["id"]
    r2 = client.get(f"{API}/processes/versions/{vid}", headers=_h(client, "t_counsa"))
    assert r2.status_code == 200
    assert "<bpmn:definitions" in r2.json()["bpmn_xml"]


# ---------- نمونه اجرا + مانیتورینگ ----------

def test_instance_lifecycle_and_monitoring(client, env):
    code = f"RS-T-{uuid.uuid4().hex[:6].upper()}"
    r = _create_process(client, code, n="f")
    def_id = r.json()["id"]
    subject_id = str(uuid.uuid4())

    # شروع نمونه (پذیرش مجاز است)
    r2 = client.post(f"{API}/process-instances", headers=_h(client, "t_reception"), json={
        "definition_id": def_id, "subject_type": "consultation_request",
        "subject_id": subject_id, "subject_label": "مراجعه‌کننده آزمون",
        "subject_meta": {"topic": "اضطراب"},
    })
    assert r2.status_code == 201, r2.text
    inst = r2.json()
    assert inst["status"] == "running"
    assert any(e["element_name"] == "شروع فرایند" for e in inst["events"])

    # نمونه دوم برای همین موضوع + همین فرایند → 409
    r3 = client.post(f"{API}/process-instances", headers=_h(client, "t_reception"), json={
        "definition_id": def_id, "subject_type": "consultation_request",
        "subject_id": subject_id,
    })
    assert r3.status_code == 409

    # ثبت گام → گام فعال به‌روزرسانی می‌شود
    r4 = client.post(f"{API}/process-instances/{inst['id']}/events", headers=_h(client, "t_counsa"), json={
        "element_id": "Tf-1", "element_name": "گام اول", "element_type": "task",
        "status": "done", "note": "انجام شد",
    })
    assert r4.status_code == 201, r4.text
    assert r4.json()["current_element_name"] == "گام اول"
    assert len(r4.json()["events"]) == 2

    # مانیتورینگ: فیلتر موضوع
    r5 = client.get(
        f"{API}/process-instances",
        params={"subject_type": "consultation_request", "subject_id": subject_id},
        headers=_h(client, "t_manager"),
    )
    assert r5.status_code == 200
    items = r5.json()["items"]
    assert len(items) == 1 and items[0]["id"] == inst["id"]

    # تکمیل
    r6 = client.post(f"{API}/process-instances/{inst['id']}/transition", headers=_h(client, "t_reception"), json={
        "action": "complete", "note": "مسیر حضوری",
    })
    assert r6.status_code == 200
    assert r6.json()["status"] == "completed"
    assert any(e["element_name"] == "پایان فرایند" for e in r6.json()["events"])

    # ثبت گام پس از پایان → 409
    r7 = client.post(f"{API}/process-instances/{inst['id']}/events", headers=_h(client, "t_counsa"), json={
        "element_name": "گام بی‌اثر",
    })
    assert r7.status_code == 409


def test_suspend_resume_and_cancel(client, env):
    code = f"RS-T-{uuid.uuid4().hex[:6].upper()}"
    r = _create_process(client, code, n="g")
    def_id = r.json()["id"]
    subject_id = str(uuid.uuid4())

    r2 = client.post(f"{API}/process-instances", headers=_h(client, "t_manager"), json={
        "definition_id": def_id, "subject_type": "manual", "subject_id": subject_id,
        "subject_label": "دستی",
    })
    inst = r2.json()

    r3 = client.post(f"{API}/process-instances/{inst['id']}/transition", headers=_h(client, "t_manager"), json={"action": "suspend"})
    assert r3.status_code == 200 and r3.json()["status"] == "suspended"

    r4 = client.post(f"{API}/process-instances/{inst['id']}/transition", headers=_h(client, "t_manager"), json={"action": "resume"})
    assert r4.status_code == 200 and r4.json()["status"] == "running"

    r5 = client.post(f"{API}/process-instances/{inst['id']}/transition", headers=_h(client, "t_manager"), json={"action": "cancel"})
    assert r5.status_code == 200 and r5.json()["status"] == "cancelled"


def test_applicant_cannot_read_processes(client, env):
    r = client.get(f"{API}/processes", headers=_h(client, "t_appa"))
    assert r.status_code == 403
    r2 = client.get(f"{API}/process-instances", headers=_h(client, "t_appa"))
    assert r2.status_code == 403


def test_start_instance_requires_published_version(client, env):
    code = f"RS-T-{uuid.uuid4().hex[:6].upper()}"
    # فرایند فقط با نسخه پیش‌نویس
    r = client.post(f"{API}/processes", headers=_h(client, "t_admin"), json={
        "code": code, "title": "بدون انتشار", "bpmn_xml": BPMN.format(n="h"), "publish": False,
    })
    assert r.status_code == 201
    def_id = r.json()["id"]
    r2 = client.post(f"{API}/process-instances", headers=_h(client, "t_admin"), json={
        "definition_id": def_id, "subject_type": "manual", "subject_id": str(uuid.uuid4()),
    })
    assert r2.status_code == 422
