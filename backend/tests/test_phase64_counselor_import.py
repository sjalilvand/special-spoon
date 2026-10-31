"""فاز ۶۴ - ورود گروهی مشاوران از اکسل شرکت رز + جدول پایهٔ استان‌ها + ورود دو عاملی پیامکی."""
import io

import openpyxl
from fastapi.testclient import TestClient

from conftest import bearer, login

API = "/api/v1"

HEADERS = [
    "استان", "نام و نام خانوادگی", "مدرک تحصیلی", "پروانه اشتغال", "رتبه حرفه ای",
    "شماره قرارداد", "کد استانها", "کد تفضیلی شخص", "شماره شباء بانکی",
    "کد ملی", "شماره تماس",
]


def _nid(checksum_base: str) -> str:
    """کد ملی معتبر از ۹ رقم پایه + رقم کنترل محاسبه‌شده."""
    s = sum(int(checksum_base[i]) * (10 - i) for i in range(9)) % 11
    return checksum_base + str(s if s < 2 else 11 - s)


def _xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "مشخصات مشاوره ها"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _admin(client: TestClient) -> dict:
    return bearer(login(client, "t_admin"))


# ---------------- provinces ----------------

def test_provinces_seeded_31_with_official_codes(client, env):
    r = client.get(f"{API}/provinces", headers=_admin(client))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert r.json()["total"] == 31
    codes = [i["code"] for i in items]
    assert codes == [f"{i:02d}" for i in range(1, 32)]
    by_code = {i["code"]: i["name"] for i in items}
    assert by_code["08"] == "تهران"
    assert by_code["05"] == "البرز"
    assert by_code["31"] == "یزد"
    assert items[0]["capital"] == "تبریز"


def test_provinces_requires_auth(client):
    assert client.get(f"{API}/provinces").status_code == 401


# ---------------- template ----------------

def test_import_template_downloads_and_matches_reference_layout(client, env):
    r = client.get(f"{API}/counselors/import-template", headers=_admin(client))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxml")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    ws = wb.worksheets[0]
    assert ws.title == "مشخصات مشاوره ها"
    first_row = [c.value for c in ws[1]]
    assert first_row == HEADERS
    assert "راهنما" in wb.sheetnames
    # شیت راهنما باید جدول کد استان‌ها را داشته باشد (۳۱ و یزد)
    guide_values = {
        str(c)
        for row in wb["راهنما"].iter_rows(values_only=True)
        for c in row if c is not None
    }
    assert "31" in guide_values and "یزد" in guide_values


def test_import_template_requires_manager(client, env):
    tok = login(client, "t_reception")
    assert client.get(f"{API}/counselors/import-template", headers=bearer(tok)).status_code == 403


# ---------------- import ----------------

def _valid_row(nid_base: str, mobile: str, name: str = "مریم موسوی", code: str = "08", prov_name: str = "تهران") -> list:
    """nid_base باید ۹ رقم باشد؛ رقم کنترل دهم خودکار محاسبه می‌شود."""
    return [prov_name, name, "کارشناسی ارشد روان‌شناسی بالینی", "12345", "یک",
            f"RZ-{nid_base}", code, "D-1001", "IR000000000000000000000001",
            _nid(nid_base), mobile]


def test_import_creates_counselors_and_active_accounts(client, env):
    n1, n2 = _nid("007612345"), _nid("006549871")
    m1, m2 = "09121110001", "09121110002"
    data = _xlsx([_valid_row("007612345", m1), _valid_row("006549871", m2, name="سارا احمدی", code="19", prov_name="قم")])
    r = client.post(f"{API}/counselors/import", files={"file": ("mosavers.xlsx", data)},
                    headers=_admin(client))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["total"] == 2 and out["created"] == 2 and out["updated"] == 0 and out["failed"] == 0

    db = env["db"]
    from app.models.people import Counselor
    from app.models.user import User, UserStatus
    db.expire_all()
    c1 = db.query(Counselor).filter(Counselor.national_id == n1).one()
    assert c1.first_name == "مریم" and c1.last_name == "موسوی"
    assert c1.province_code == "08" and c1.professional_rank == "یک"
    assert c1.contract_number == "RZ-007612345" and c1.sheba_number == "IR000000000000000000000001"
    assert c1.detailed_code == "D-1001" and c1.work_mobile == m1
    u1 = db.get(User, c1.user_id)
    assert u1 is not None and u1.username == n1 and u1.status == UserStatus.ACTIVE
    assert u1.mobile == m1 and not u1.must_change_password
    assert {r.code for r in u1.roles} == {"COUNSELOR"}
    c2 = db.query(Counselor).filter(Counselor.national_id == n2).one()
    assert c2.province_code == "19"  # قم

    # ورود با کد ملی و رمز موبایل - همان الزام کاربر
    r = client.post(f"{API}/auth/login", json={"username": n1, "password": m1})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_import_is_upsert_on_second_run(client, env):
    n1 = _nid("007612399")
    data = _xlsx([_valid_row("007612399", "09121110021")])
    r1 = client.post(f"{API}/counselors/import", files={"file": ("a.xlsx", data)}, headers=_admin(client))
    assert r1.json()["created"] == 1
    # تغییر نام و استان در اجرای دوم
    row = _valid_row("007612399", "09121110021", name="مریم موسوی‌فر", code="05", prov_name="البرز")
    r2 = client.post(f"{API}/counselors/import", files={"file": ("b.xlsx", _xlsx([row]))}, headers=_admin(client))
    out = r2.json()
    assert out["created"] == 0 and out["updated"] == 1 and out["failed"] == 0
    db = env["db"]
    from app.models.people import Counselor
    db.expire_all()
    c = db.query(Counselor).filter(Counselor.national_id == n1).one()
    assert c.province_code == "05" and c.last_name == "موسوی‌فر"
    # حساب تکراری ساخته نشده
    from app.models.user import User
    assert db.query(User).filter(User.username == n1).count() == 1


def test_import_row_errors_are_reported_without_stopping_valid_rows(client, env):
    good = _valid_row("007612341", "09121110031")
    bad_nid = _valid_row("007612342", "09121110032")
    bad_nid[9] = "9999999999"  # رقم کنترل غلط
    bad_prov = _valid_row("007612343", "09121110033")
    bad_prov[6] = "99"  # کد استان ناموجود
    dup = _valid_row("007612341", "09121110034")  # کد ملی تکراری در فایل
    bad_sheba = _valid_row("007612344", "09121110035")
    bad_sheba[8] = "IR123"  # شبا ناقص
    bad_phone = _valid_row("007612347", "2112345")  # موبایل نیست
    r = client.post(
        f"{API}/counselors/import",
        files={"file": ("c.xlsx", _xlsx([good, bad_nid, bad_prov, dup, bad_sheba, bad_phone]))},
        headers=_admin(client),
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["total"] == 6 and out["created"] == 1 and out["failed"] == 5
    msgs = {e["row"]: e["message"] for e in out["errors"]}
    assert any("کد ملی" in m for m in msgs.values())
    assert any("استان" in m for m in msgs.values())
    assert any("تکراری" in m for m in msgs.values())
    assert any("شبا" in m for m in msgs.values())
    assert any("موبایل" in m for m in msgs.values())


def test_import_accepts_province_name_without_code_and_persian_digits(client, env):
    n = "0055123406"  # کد ملی معتبر (رقم کنترل محاسبه‌شده)
    # کد ملی و موبایل با ارقام فارسی، استان خالی → خطای ردیف
    row = [None, "حسین کریمی", None, None, None, None, None, None, None, "۰۰۵۵۱۲۳۴۰۶", "۰۹۱۲۱۱۱۱۰۴۱"]
    data = _xlsx([row])
    r = client.post(f"{API}/counselors/import", files={"file": ("d.xlsx", data)}, headers=_admin(client))
    assert r.status_code == 200, r.text
    out = r.json()
    # استان خالی است → خطای «کد استان یا نام استان»
    assert out["failed"] == 1
    row2 = ["اصفهان", "حسین کریمی", None, None, None, None, None, None, None, "۰۰۵۵۱۲۳۴۰۶", "۰۹۱۲۱۱۱۱۰۴۱"]
    r2 = client.post(f"{API}/counselors/import", files={"file": ("e.xlsx", _xlsx([row2]))}, headers=_admin(client))
    out2 = r2.json()
    assert out2["created"] == 1, out2
    db = env["db"]
    from app.models.people import Counselor
    db.expire_all()
    c = db.query(Counselor).filter(Counselor.national_id == n).one()
    assert c.province_code == "04" and c.work_mobile == "09121111041"


def test_import_rejects_wrong_headers_and_non_xlsx(client, env):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ستون غلط", "یکی دیگر"])
    bio = io.BytesIO()
    wb.save(bio)
    r = client.post(f"{API}/counselors/import", files={"file": ("x.xlsx", bio.getvalue())}, headers=_admin(client))
    assert r.status_code == 422 and "الزامی" in r.json()["detail"]
    r2 = client.post(f"{API}/counselors/import", files={"file": ("y.txt", b"not excel")}, headers=_admin(client))
    assert r2.status_code == 422


def test_otp_login_flow_issues_full_session(client, env):
    # کاربر دارای موبایل (همان حسابی که ایمپورت می‌سازد)
    n1 = _nid("007612349")
    data = _xlsx([_valid_row("007612349", "09121110999")])
    r = client.post(f"{API}/counselors/import", files={"file": ("f.xlsx", data)}, headers=_admin(client))
    assert r.json()["created"] == 1, r.text

    req = client.post(f"{API}/auth/otp/request", json={"mobile": "09121110999", "purpose": "login"})
    assert req.status_code == 200, req.text
    dev_code = req.json().get("dev_code")
    assert dev_code and len(dev_code) == 6  # تا وصل شدن سامانهٔ پیامک، کد نمایش داده می‌شود

    ver = client.post(f"{API}/auth/otp/verify", json={"mobile": "09121110999", "code": dev_code, "purpose": "login"})
    assert ver.status_code == 200, ver.text
    tok = ver.json()["access_token"]
    me = client.get(f"{API}/auth/me", headers=bearer(tok))
    assert me.status_code == 200 and me.json()["username"] == n1

    # کد یک‌بارمصرف است - استفادهٔ دوباره نمی‌شود
    ver2 = client.post(f"{API}/auth/otp/verify", json={"mobile": "09121110999", "code": dev_code, "purpose": "login"})
    assert ver2.status_code == 400


def test_otp_login_unknown_mobile_404(client, env):
    client.post(f"{API}/auth/otp/request", json={"mobile": "09120009999", "purpose": "login"})
    # کد غلط → 400 (بدون افشای موجود بودن حساب)
    r = client.post(f"{API}/auth/otp/verify", json={"mobile": "09120009999", "code": "000000", "purpose": "login"})
    assert r.status_code == 400


def test_otp_login_wrong_code_rejected(client, env):
    n1 = _nid("007612348")
    data = _xlsx([_valid_row("007612348", "09121110988")])
    client.post(f"{API}/counselors/import", files={"file": ("g.xlsx", data)}, headers=_admin(client))
    req = client.post(f"{API}/auth/otp/request", json={"mobile": "09121110988", "purpose": "login"})
    code = req.json()["dev_code"]
    r = client.post(f"{API}/auth/otp/verify", json={"mobile": "09121110988", "code": "000000" if code != "000000" else "000001", "purpose": "login"})
    assert r.status_code == 400


# ---------------- فاز ۶۶ب: اتخاذ حساب موجود بدون پروندهٔ مشاور ----------------

def test_import_adopts_existing_user_without_counselor_profile(client, env):
    """بازتولید خطای میدانی ۱.۰.۲۶ در مسیر پنل: حسابی با username=کد ملی از قبل
    هست ولی پروندهٔ مشاور ندارد؛ ورود اکسل باید حساب را «اتخاذ» کند (پرونده
    بسازد، رمز را دست نزند) نه اینکه با تضاد ix_users_username خطا بدهد."""
    from app.core.security import hash_password
    from app.models.people import Counselor
    from app.models.user import User, UserStatus

    n1 = _nid("007612391")
    db = env["db"]
    db.expire_all()
    # حساب از قبل (مثلاً دستی ساخته‌شده) بدون هیچ پروندهٔ مشاور
    u = User(username=n1, display_name="حساب قدیمی", status=UserStatus.ACTIVE,
             must_change_password=False)
    u.password_hash = hash_password("old-secret-789")
    db.add(u)
    db.commit()
    uid = u.id
    old_hash = u.password_hash

    data = _xlsx([_valid_row("007612391", "09121110971", name="حساب قدیمی")])
    r = client.post(f"{API}/counselors/import", files={"file": ("h.xlsx", data)},
                    headers=_admin(client))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] == 1 and out["failed"] == 0, out

    db.expire_all()
    c = db.query(Counselor).filter(Counselor.national_id == n1).one()
    assert c.user_id == uid
    u2 = db.get(User, uid)
    assert u2.password_hash == old_hash  # رمز حفظ شد
    assert u2.display_name == "حساب قدیمی"
    assert u2.status == UserStatus.ACTIVE
    assert any(r_.code == "COUNSELOR" for r_ in u2.roles)
    # فقط یک حساب با این username
    assert db.query(User).filter(User.username == n1).count() == 1
