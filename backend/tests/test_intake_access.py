"""دسترسی و صحت پرسشنامه پذیرش - ماتریس خواندن/نوشتن"""
from conftest import bearer, login


def _mk_cr(client) -> str:
    tok = login(client, "t_reception")
    r = client.post("/api/v1/consultation-requests", headers=bearer(tok), json={
        "full_name": "مراجع پرسشنامه",
        "mobile": "09121130000",
        "topic": "مشاوره فردی",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_intake_read_write_matrix(env, client):
    cr_id = _mk_cr(client)

    tok_rec = login(client, "t_reception")
    assert client.get(
        f"/api/v1/consultation-requests/{cr_id}/intake", headers=bearer(tok_rec)
    ).status_code == 200

    # مدیر سیستم: خواندن بله، نوشتن بله (فاز ۴۹: دسترسی کامل ستاد)
    tok_admin = login(client, "t_admin")
    assert client.get(
        f"/api/v1/consultation-requests/{cr_id}/intake", headers=bearer(tok_admin)
    ).status_code == 200
    assert client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake",
        headers=bearer(tok_admin), json={"data": {}},
    ).status_code == 200

    # سرپرست فنی: خواندن بله، نوشتن خیر
    tok_sup = login(client, "t_super")
    assert client.get(
        f"/api/v1/consultation-requests/{cr_id}/intake", headers=bearer(tok_sup)
    ).status_code == 200
    assert client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake",
        headers=bearer(tok_sup), json={"data": {}},
    ).status_code == 403

    # پذیرش: ذخیره پیش‌نویس؛ نهایی‌سازی ناقص => 422
    tok_rec = login(client, "t_reception")
    payload = {"data": {"identity_full_name": "مراجع پرسشنامه"}}
    assert client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake",
        headers=bearer(tok_rec), json=payload,
    ).status_code == 200
    assert client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake/finalize", headers=bearer(tok_rec)
    ).status_code == 422

    # تکمیل الزامی‌ها و نهایی‌سازی موفق
    payload["data"].update({"initial_problem_summary": "شرح", "planning_goals": "اهداف"})
    assert client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake",
        headers=bearer(tok_rec), json=payload,
    ).status_code == 200
    r = client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake/finalize", headers=bearer(tok_rec)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "final"

    # قفل بودن پس از نهایی‌سازی
    assert client.post(
        f"/api/v1/consultation-requests/{cr_id}/intake",
        headers=bearer(tok_rec), json=payload,
    ).status_code == 409