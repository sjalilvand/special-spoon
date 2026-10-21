"""فاز ۵۰ — تکمیل بانک آزمون مطابق مرجع ۲۲ آزمون + عکس پیوست سؤال + مشخصات اولیه.

پوشش:
- فایل‌های seed: هر ۲۲ کد مرجع با تعداد سؤال درست (MMPI-370، MCMI-175،
  NEO-240، 16PF-187، MBTI-88 و ...) + بازه تفسیر + ساختار گزینه‌ها
- عکس‌های ریون: ۹۶ فایل PNG موجود (۳۶ CPM + ۶۰ RSPM) و هر سؤال تصویری فایل دارد
- meta.json: متادیتای ۱۱ ابزار قبلی
- API: public_tests شامل کد/مدت/سن/رنگ + paper شامل image_url
- API: ثبت اجرا با مشخصات اولیه (demographics) و snapshot آن
- API: endpoint عکس سرو می‌دهد و مسیر ناامن (traversal) → 404
"""
import json
from pathlib import Path

import pytest

from conftest import bearer, login

API = "/api/v1"

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = BACKEND_DIR / "psych_seed"

# مرجع ۲۲ آزمون «راز زندگی»: کد → تعداد سؤال
REFERENCE: dict[str, tuple[str, int]] = {
    "MMPI-SF-370": ("mmpi-sf-370", 370),
    "MBTI-88": ("mbti-88", 88),
    "MCMI-III-175": ("mcmi-iii-175", 175),
    "NEO-PI-R": ("neo-pi-r", 240),
    "SCH-EQ-33": ("shering-eq-33", 33),
    "BNQ-35": ("glasser-bnq", 35),
    "MES-40": ("mes-40", 40),
    "EQ-i-90": ("baron-eq-i-90", 90),
    "BDI-II-21": ("bdi-ii", 21),
    "BAI-21": ("bai", 21),
    "CA-16PF-187": ("cattell-16pf-187", 187),
    "CPM-36": ("raven-cpm-36", 36),
    "RSPM-60": ("raven-rspm-60", 60),
    "MIT-80": ("gardner-mit-80", 80),
    "TTCT-60": ("torrance-ttct-60", 60),
    "SCAT-27": ("schein-anchors", 27),
    "MSQ-19": ("minnesota-msq-19", 19),
    "OSI-60": ("osipow-osi-60", 60),
    "MSEIS-41": ("schutte-mseis-41", 41),
    "JCQ-37": ("jazani-jcq-37", 37),
    "GHQ-28": ("ghq-28", 28),
    "HCQ-60": ("holland-hcq-60", 60),
}


def _load_all_tests() -> dict[str, dict]:
    def num_key(p: Path):
        digits = "".join(ch for ch in p.stem if ch.isdigit())
        return int(digits) if digits else 0

    out: dict[str, dict] = {}
    for f in sorted(SEED_DIR.glob("tests_part*.json"), key=num_key):
        for t in json.loads(f.read_text(encoding="utf-8")):
            out[t["slug"]] = t
    return out


# ---------------------------------------------------------------- seed files
def test_reference_22_codes_present_with_exact_counts():
    tests = _load_all_tests()
    meta = json.loads((SEED_DIR / "meta.json").read_text(encoding="utf-8"))
    for code, (slug, count) in REFERENCE.items():
        t = tests.get(slug)
        assert t is not None, f"کد مرجع {code} در بانک نیست"
        # کد یا در خود فایل است یا از meta.json تأمین می‌شود (فرم‌های فاز ۴۷)
        assert t.get("code") or meta.get(slug, {}).get("code"), f"{slug} بدون کد مرجع"
        assert (t.get("code") or meta[slug]["code"]) == code
        assert len(t["questions"]) == count, f"{code}: {len(t['questions'])} ≠ {count}"
        assert t["interpretations"], f"{code} بدون بازه تفسیر"


def test_seed_options_and_bands_consistent():
    tests = _load_all_tests()
    for slug, t in tests.items():
        assert t["questions"] and t["interpretations"], slug
        for q in t["questions"]:
            opts = q["options"]
            if isinstance(opts, str):  # مقیاس‌های فایل‌های قدیمی
                continue
            assert len(opts) >= 2, slug
            assert all(isinstance(s, int) and s >= 0 for _, s in opts), slug
        max_total = sum(max(s for _, s in q["options"]) for q in t["questions"]
                        if not isinstance(q["options"], str))
        if max_total:
            bands_max = max(i["score_max"] for i in t["interpretations"])
            assert bands_max >= max_total, f"{slug}: بازه تفسیر نمره {max_total} را نمی‌پوشاند"


def test_raven_images_exist_for_all_items():
    tests = _load_all_tests()
    img_questions = [
        (slug, q["image"]) for slug, t in tests.items()
        for q in t["questions"] if q.get("image")
    ]
    assert len(img_questions) == 96  # ۳۶ CPM + ۶۰ RSPM
    for slug, rel in img_questions:
        assert (SEED_DIR / "images" / rel).is_file(), f"{slug}: عکس {rel} نیست"
    cpm = sum(1 for _, r in img_questions if r.startswith("cpm/"))
    rspm = sum(1 for _, r in img_questions if r.startswith("rspm/"))
    assert cpm == 36 and rspm == 60


def test_meta_json_covers_existing_tests():
    meta = json.loads((SEED_DIR / "meta.json").read_text(encoding="utf-8"))
    for slug in ("bdi-ii", "bai", "dass-21", "phq-9", "gad-7", "pss-10",
                 "ghq-12", "rosenberg", "mes-20", "eq-24", "gardner-mit"):
        m = meta.get(slug)
        assert m and m.get("code") and m.get("estimated_minutes"), slug


def test_draft_status_mirrors_reference_disabled():
    """ابزارهای غیرفعال مرجع (کارت‌های ۱۵–۲۰) در سامانه پیش‌نویس‌اند."""
    tests = _load_all_tests()
    for slug in ("torrance-ttct-60", "minnesota-msq-19", "osipow-osi-60",
                 "schutte-mseis-41", "jazani-jcq-37"):
        assert tests[slug]["status"] == "draft", slug


# ---------------------------------------------------------------- API
@pytest.fixture(scope="session", autouse=True)
def _seed_bank():
    """بانک آزمون یک بار روی rosepsy_test بارگذاری می‌شود (فاز ۵۰)."""
    import seed_psych_tests
    assert seed_psych_tests.main() == 0


@pytest.fixture(autouse=True)
def _env(env):
    return env


def test_public_tests_expose_reference_metadata(client):
    r = client.get(f"{API}/public/psych-tests")
    assert r.status_code == 200
    items = {t["slug"]: t for t in r.json()["items"]}
    assert "raven-cpm-36" in items
    cpm = items["raven-cpm-36"]
    assert cpm["code"] == "CPM-36"
    assert cpm["estimated_minutes"] == 30
    assert cpm["accent_color"] == "#f43f5e"
    assert cpm["age_range"] == "کودکان ۵ تا ۹ سال"
    # ابزارهای پیش‌نویس در فهرست عمومی نیستند
    assert "torrance-ttct-60" not in items


def test_public_paper_includes_image_urls(client):
    r = client.get(f"{API}/public/psych-tests/raven-rspm-60/paper")
    assert r.status_code == 200
    body = r.json()
    assert body["test"]["code"] == "RSPM-60"
    qs = body["questions"]
    assert len(qs) == 60
    assert all(q["image_url"] and q["image_url"].startswith("/api/v1/public/psych-images/rspm/")
               for q in qs)
    # ابزار متنی بدون عکس
    r2 = client.get(f"{API}/public/psych-tests/bdi-ii/paper")
    assert all(not q["image_url"] for q in r2.json()["questions"])


def test_psych_image_endpoint_serves_and_blocks_traversal(client):
    ok = client.get(f"{API}/public/psych-images/cpm/cpm_001.png")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("image/png")
    assert ok.content[:8] == b"\x89PNG\r\n\x1a\n"
    for bad in ("..%2F..%2Fsecret.txt", "cpm/../../app/main.py"):
        r = client.get(f"{API}/public/psych-images/{bad}")
        assert r.status_code == 404


def test_attempt_accepts_demographics(client):
    """مشخصات اولیه (فرم مرجع) در اجرا snapshot می‌شود."""
    tok = login(client, "t_admin")
    headers = bearer(tok)
    paper = client.get(f"{API}/public/psych-tests/bdi-ii/paper").json()
    answers = [0] * len(paper["questions"])
    demo = {"gender": "زن", "age": "۳۰", "education": "کارشناسی", "marital": "متاهل"}
    r = client.post(f"{API}/public/psych-tests/bdi-ii/attempts",
                    json={"answers": answers, "demographics": demo}, headers=headers)
    assert r.status_code == 201, r.text
    attempt = r.json()["attempt"]
    assert attempt["demographics"] == demo

    # اجرای بدون demographics → فیلد null می‌ماند
    r2 = client.post(f"{API}/public/psych-tests/bai/attempts",
                     json={"answers": [0] * 21}, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["attempt"]["demographics"] is None
