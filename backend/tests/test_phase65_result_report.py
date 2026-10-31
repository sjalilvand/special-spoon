"""فاز ۶۵ - گزارش تحلیلی برای همهٔ ابزارها: فالبک سنتز از زیرمقیاس‌ها.

- ابزار بدون ردیف PsychScale اما دارای زیرمقیاس → result_payload سنتزشده
  (یک مقیاس به‌ازای هر زیرمقیاس + سطح عمومی درصدی) به‌جای None (نمای ساده)؛
- ابزار دارای مقیاس ثبت‌شده → همان مسیر فاز ۶۳ (سطح‌های اختصاصی seed) — سنتز اجرا نمی‌شود؛
- ابزار تک‌بعدی بدون subscale → None (نمای کلاسیک گیج کافی است)؛
- سطح عمومی: مرزهای ۳۴/۵۰/۶۷ درصد نسبت به بیشینهٔ همان بعد.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.psych_test import PsychScale
from app.services.psych_report import _generic_level

from conftest import bearer, login

API = "/api/v1"


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def supervisor_headers(client, env):
    return bearer(login(client, "t_super"))


@pytest.fixture()
def applicant_headers(client, env):
    return bearer(login(client, "t_appa"))


def _mk_two_subscale_test(client, manager, supervisor) -> dict:
    """ابزار منتشرشده با ۲ زیرمقیاس (هر یک ۲ سؤال × بیشینه ۳ = بیشینه ۶) — بدون مقیاس."""
    suffix = uuid.uuid4().hex[:8]
    r = client.post(f"{API}/psych-tests", headers=manager, json={
        "slug": f"p65-{suffix}",
        "title": f"ابزار ف۶۵ {suffix}",
        "description": "گزارش سنتزشده",
    })
    assert r.status_code == 201, r.text
    t = r.json()
    for si, sub in enumerate(("اضطراب", "افسردگی")):
        for i in range(2):
            r = client.post(f"{API}/psych-tests/{t['id']}/questions", headers=manager, json={
                "prompt": f"سؤال {sub} {i}",
                "options": [
                    {"label": "هیچ", "score": 0},
                    {"label": "کم", "score": 1},
                    {"label": "متوسط", "score": 2},
                    {"label": "زیاد", "score": 3},
                ],
                "subscale": sub,
                "sort_order": si * 2 + i,  # ترتیب قطعی — پاسخ‌ها اندیس‌محورند
            })
            assert r.status_code == 201, r.text
    r = client.post(f"{API}/psych-tests/{t['id']}/interpretations", headers=manager, json={
        "score_min": 0, "score_max": 12, "label": "سطح پایه", "guidance": "توصیه آزمایشی",
    })
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/psych-tests/{t['id']}/submit-review", headers=manager)
    assert r.status_code == 200, r.text
    r = client.post(f"{API}/psych-tests/{t['id']}/review", headers=supervisor,
                    json={"approve": True, "note": "تأیید علمی"})
    assert r.status_code == 200, r.text
    return r.json()


def test_phase65_synthesized_report_without_scales(client, env, manager_headers,
                                                   supervisor_headers, applicant_headers):
    t = _mk_two_subscale_test(client, manager_headers, supervisor_headers)
    # اضطراب: 3+2=5 از ۶ (۸۳٪ → شدید) | افسردگی: 1+0=1 از ۶ (۱۷٪ → عادی)
    r = client.post(f"{API}/public/psych-tests/{t['slug']}/attempts",
                    headers=applicant_headers, json={"answers": [3, 2, 1, 0]})
    assert r.status_code == 201, r.text
    a = r.json()["attempt"]
    rp = a["result_payload"]
    assert rp is not None and rp["version"] == 1
    scales = {s["key"]: s for s in rp["scales"]}
    assert set(scales) == {"اضطراب", "افسردگی"}
    anx = scales["اضطراب"]
    assert anx["score"] == 5 and anx["max"] == 6 and anx["percent"] == 83
    assert anx["level"]["label"] == "شدید" and anx["direction"] == "higher_worse"
    assert anx["level"]["text"]
    dep = scales["افسردگی"]
    assert dep["score"] == 1 and dep["percent"] == 17
    assert dep["level"]["label"] == "در محدوده عادی"
    # دو بعد < ۳ → مقیاس غالب ندارد
    assert rp["dominant"] is None
    assert rp["total"]["score"] == 6 and rp["total"]["max"] == 12
    assert rp["total"]["label"] == "سطح پایه"


def test_phase65_dominant_with_three_scales(client, env, manager_headers,
                                            supervisor_headers, applicant_headers):
    """۳ زیرمقیاس → مقیاس غالب (بالاترین درصد؛ اولین بیشینه با ترتیب sort_order)."""
    suffix = uuid.uuid4().hex[:8]
    r = client.post(f"{API}/psych-tests", headers=manager_headers, json={
        "slug": f"p65d-{suffix}", "title": f"سه‌بعدی {suffix}", "description": "غالب",
    })
    assert r.status_code == 201, r.text
    t = r.json()
    for si, sub in enumerate(("الف", "ب", "پ")):
        r = client.post(f"{API}/psych-tests/{t['id']}/questions", headers=manager_headers, json={
            "prompt": f"سؤال {sub}",
            "options": [{"label": "هیچ", "score": 0}, {"label": "زیاد", "score": 3}],
            "subscale": sub, "sort_order": si,
        })
        assert r.status_code == 201, r.text
    r = client.post(f"{API}/psych-tests/{t['id']}/interpretations", headers=manager_headers, json={
        "score_min": 0, "score_max": 9, "label": "کل",
    })
    assert r.status_code == 201, r.text
    client.post(f"{API}/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    r = client.post(f"{API}/psych-tests/{t['id']}/review", headers=supervisor_headers,
                    json={"approve": True, "note": "تأیید"})
    assert r.status_code == 200, r.text
    t = r.json()
    r = client.post(f"{API}/public/psych-tests/{t['slug']}/attempts",
                    headers=applicant_headers, json={"answers": [0, 0, 1]})
    assert r.status_code == 201, r.text
    rp = r.json()["attempt"]["result_payload"]
    assert rp["dominant"]["title"] == "پ" and rp["dominant"]["percent"] == 100


def test_phase65_seeded_scales_still_win(client, env, manager_headers,
                                         supervisor_headers, applicant_headers):
    """با وجود مقیاس ثبت‌شده، سنتز اجرا نمی‌شود و سطح‌های اختصاصی برمی‌گردد."""
    t = _mk_two_subscale_test(client, manager_headers, supervisor_headers)
    db = env["db"]
    for s in db.scalars(select(PsychScale).where(PsychScale.test_id == uuid.UUID(t["id"]))).all():
        db.delete(s)
    db.add(PsychScale(
        test_id=uuid.UUID(t["id"]), parent_id=None, key="anx", title="اضطراب",
        match_names=["اضطراب"],
        levels=[{"min": 0, "max": 4, "label": "کم", "text": "توضیح کم"},
                {"min": 5, "max": 6, "label": "زیاد", "text": "توضیح زیاد"}],
        color="#8a3342", direction="higher_worse", sort_order=0,
    ))
    db.commit()
    r = client.post(f"{API}/public/psych-tests/{t['slug']}/attempts",
                    headers=applicant_headers, json={"answers": [3, 3, 1, 0]})
    assert r.status_code == 201, r.text
    rp = r.json()["attempt"]["result_payload"]
    assert [s["key"] for s in rp["scales"]] == ["anx"]  # فقط مقیاس ثبت‌شده؛ سنتز اجرا نشد
    anx = rp["scales"][0]
    assert anx["score"] == 6 and anx["level"]["label"] == "زیاد" and anx["level"]["text"] == "توضیح زیاد"


def test_phase65_single_dimension_without_scales_stays_classic(client, env, manager_headers,
                                                               supervisor_headers, applicant_headers):
    """ابزار تک‌بعدی بدون subscale و بدون مقیاس → None (نمای کلاسیک گیج)."""
    suffix = uuid.uuid4().hex[:8]
    r = client.post(f"{API}/psych-tests", headers=manager_headers, json={
        "slug": f"p65s-{suffix}", "title": f"تک‌بعدی {suffix}", "description": "کلاسیک",
    })
    assert r.status_code == 201, r.text
    t = r.json()
    r = client.post(f"{API}/psych-tests/{t['id']}/questions", headers=manager_headers, json={
        "prompt": "سؤال بدون زیرمقیاس",
        "options": [{"label": "هیچ", "score": 0}, {"label": "زیاد", "score": 3}],
    })
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/psych-tests/{t['id']}/interpretations", headers=manager_headers, json={
        "score_min": 0, "score_max": 3, "label": "کل",
    })
    assert r.status_code == 201, r.text
    client.post(f"{API}/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    r = client.post(f"{API}/psych-tests/{t['id']}/review", headers=supervisor_headers,
                    json={"approve": True, "note": "تأیید"})
    assert r.status_code == 200, r.text
    t = r.json()
    r = client.post(f"{API}/public/psych-tests/{t['slug']}/attempts",
                    headers=applicant_headers, json={"answers": [1]})
    assert r.status_code == 201, r.text
    assert r.json()["attempt"]["result_payload"] is None


def test_phase65_generic_level_boundaries():
    assert _generic_level(0)["label"] == "در محدوده عادی"
    assert _generic_level(33)["label"] == "در محدوده عادی"
    assert _generic_level(34)["label"] == "خفیف"
    assert _generic_level(49)["label"] == "خفیف"
    assert _generic_level(50)["label"] == "متوسط"
    assert _generic_level(66)["label"] == "متوسط"
    assert _generic_level(67)["label"] == "شدید"
    assert _generic_level(100)["label"] == "شدید"
