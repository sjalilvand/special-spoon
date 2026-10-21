"""فاز ۵۱ — پایداری پنل: قرارداد فهرست نمونه‌های فرایند + پاکت v2

رگرسیون باگ «صفحهٔ سفید مانیتورینگ فرایندها» (F.items.find is not a function):
- پاسخ قبلی GET /process-instances به‌شکل {"items": [...], "meta": {...}} بود؛
  چون نشانه‌های صفحه‌بندی (total/page/page_size) در سطح بالای dict نبودند،
  پاکت v2 (ADR-03) آن را نمی‌شکست و data به‌جای آرایه، یک شیء می‌شد → کرش فرانت.
- قرارداد درست فهرست‌های v2: {items, total, page, page_size} → پاکت items را به
  data می‌برد و بقیه را در meta.pagination می‌گذارد (مطابق بقیه endpointها).

پوشش:
- v1: شکل قراردادی {items, total, page, page_size} روی GET /process-instances
- v2: data باید آرایه باشد و total در meta.pagination باشد
- پایداری: فیلتر موضوع روی هر دو نسخه یکسان کار می‌کند
"""
import uuid

from conftest import PASSWORD, bearer, login

API = "/api/v1"
API2 = "/api/v2"

BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  id="Defs-{n}" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Proc-{n}" name="فرایند پایداری {n}" isExecutable="false">
    <bpmn:startEvent id="S{n}" name="شروع"/>
    <bpmn:task id="T{n}-1" name="گام اول"/>
    <bpmn:endEvent id="E{n}" name="پایان"/>
  </bpmn:process>
</bpmn:definitions>
"""


def _h(client, who):
    return bearer(login(client, who))


def _setup_instance(client, code_suffix: str):
    """فرایند + نسخه منتشرشده + یک نمونه در جریان برای موضوع یکتا."""
    code = f"RS-P51-{code_suffix}"
    r = client.post(f"{API}/processes", headers=_h(client, "t_admin"), json={
        "code": code, "title": f"فرایند پایداری {code_suffix}", "description": "تست فاز ۵۱",
        "bpmn_xml": BPMN.format(n=code_suffix), "changelog": "نسخه اول", "publish": True,
    })
    assert r.status_code == 201, r.text
    def_id = r.json()["id"]
    subject_id = str(uuid.uuid4())
    r2 = client.post(f"{API}/process-instances", headers=_h(client, "t_reception"), json={
        "definition_id": def_id, "subject_type": "manual",
        "subject_id": subject_id, "subject_label": "موضوع پایداری",
    })
    assert r2.status_code == 201, r2.text
    return def_id, subject_id


def test_v1_instances_list_contract_shape(client, env):
    """v1: فهرست نمونه‌ها باید شکل قراردادی {items,total,page,page_size} داشته باشد."""
    _, subject_id = _setup_instance(client, uuid.uuid4().hex[:6].upper())

    r = client.get(f"{API}/process-instances", headers=_h(client, "t_manager"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int) and body["total"] >= 1
    assert body["page"] == 1
    assert body["page_size"] >= 1
    # هیچ کلید meta تودرتو نباید باشد (شکل قدیمی ممنوع)
    assert "meta" not in body

    # فیلتر موضوع همان شکل را می‌دهد
    r2 = client.get(
        f"{API}/process-instances",
        params={"subject_type": "manual", "subject_id": subject_id},
        headers=_h(client, "t_manager"),
    )
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["total"] == 1 and len(b2["items"]) == 1


def test_v2_envelope_data_is_array(client, env):
    """v2: پاکت باید data را «آرایه» کند و total را در meta.pagination بگذارد.

    این دقیقاً همان نقطهٔ کرش فرانت‌اند قبل از فاز ۵۱ است.
    """
    _, subject_id = _setup_instance(client, uuid.uuid4().hex[:6].upper())

    r = client.get(
        f"{API2}/process-instances",
        params={"subject_type": "manual", "subject_id": subject_id},
        headers=_h(client, "t_manager"),
    )
    assert r.status_code == 200, r.text
    env_body = r.json()
    # پاکت استاندارد
    assert set(env_body.keys()) >= {"data", "meta", "errors"}
    assert env_body["errors"] is None
    # نکتهٔ حیاتی: data باید آرایه باشد — نه شیء {items}
    assert isinstance(env_body["data"], list)
    assert len(env_body["data"]) == 1
    assert env_body["data"][0]["subject_id"] == subject_id
    # صفحه‌بندی در meta
    pagination = env_body["meta"].get("pagination") or {}
    assert int(pagination.get("total", 0)) == 1
    assert int(pagination.get("page", 0)) == 1


def test_v2_processes_list_passthrough(client, env):
    """v2: پاسخ ساختاری {items} بدون نشانگر صفحه‌بندی دست‌نخورده می‌ماند
    (فرانت fetchProcesses از r.data.items می‌خواند — نباید به آرایه بشکند)."""
    code = f"RS-P51-C{uuid.uuid4().hex[:6].upper()}"
    r = client.post(f"{API}/processes", headers=_h(client, "t_admin"), json={
        "code": code, "title": "فرایند ساختاری", "bpmn_xml": BPMN.format(n="C1"),
    })
    assert r.status_code == 201, r.text

    r2 = client.get(f"{API2}/processes", headers=_h(client, "t_manager"))
    assert r2.status_code == 200
    data = r2.json()["data"]
    # ساختار {items: [...]} حفظ شده باشد
    assert isinstance(data, dict) and isinstance(data.get("items"), list)
    assert any(d["code"] == code for d in data["items"])
