# -*- coding: utf-8 -*-
"""فاز ۵۷ — ساخت JSONهای بانک آزمون: NEO-240 واقعی، GHQ-28 رسمی و ۹ آزمون جدید.

اجرا (از پوشه backend):
    python scripts/phase57/build_all.py

- tests_part6.json: فقط ورودی neo-pi-r با گویه‌های واقعی فرم بلند بازنویسی می‌شود
  (کتل و MBTI دست‌نخورده می‌مانند).
- tests_part7.json: فقط ورودی ghq-28 با متن دقیق فرم فارسی بازنویسی می‌شود.
- tests_part11.json: ۹ آزمون جدید هم‌تراز کاتالوگ esanj ساخته می‌شود.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from neo_data import NEO_ITEMS, FACET_NAMES, facet_of  # noqa: E402
from ghq_data import GHQ_ITEMS, GHQ_OPTIONS_NEG, GHQ_OPTIONS_POS  # noqa: E402
from extra_tests import build_scl90, build_mbi, build_bpaq  # noqa: E402
import extra_tests2 as ex2  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[2] / "psych_seed"

AGREE5 = [("کاملاً مخالفم", 0), ("مخالفم", 1), ("نظری ندارم", 2), ("موافقم", 3), ("کاملاً موافقم", 4)]


def agree_opts(reverse: bool) -> list[list]:
    """ترتیب برچسب‌ها ثابت (مطابق فرم کاربر)؛ امتیازها بسته به معکوس بودن گویه."""
    if reverse:
        return [[lbl, 4 - s] for lbl, s in AGREE5]
    return [[lbl, s] for lbl, s in AGREE5]


def build_neo() -> dict:
    questions = []
    for idx, (prompt, reverse) in enumerate(NEO_ITEMS, 1):
        questions.append({
            "prompt": prompt,
            "options": agree_opts(reverse),
            "subscale": facet_of(idx),
        })
    interps = [
        {"score_min": 0, "score_max": 384, "label": "پروفایل پایین‌نو",
         "guidance": "جمع ویژگی‌های پنج‌گانه شما پایین است؛ تفسیر دقیق را از ریزنمرهٔ ۳۰ وجه و ۵ بعد (جمع شش وجه هر بعد) بخوانید."},
        {"score_min": 385, "score_max": 576, "label": "پروفایل متعادل",
         "guidance": "الگوی شخصیتی شما متعادل است؛ تفسیر دقیق را از ریزنمرهٔ ۳۰ وجه و ۵ بعد (جمع شش وجه هر بعد) بخوانید."},
        {"score_min": 577, "score_max": 720, "label": "پروفایل فعال",
         "guidance": "ویژگی‌های شخصیتی شما در سطح بالایی فعال است؛ تفسیر دقیق را از ریزنمرهٔ ۳۰ وجه و ۵ بعد بخوانید."},
        {"score_min": 721, "score_max": 960, "label": "پروفایل برجسته",
         "guidance": "ویژگی‌های شخصیتی شما برجسته و شدید است؛ تفسیر دقیق را از ریزنمرهٔ ۳۰ وجه و ۵ بعد بخوانید."},
    ]
    return {
        "slug": "neo-pi-r",
        "code": "NEO-PI-R-240",
        "title": "آزمون شخصیت نئو (فرم بلند ۲۴۰ گویه‌ای)",
        "en": "NEO PI-R Long Form",
        "description": (
            "جامع‌ترین ابزار سنجش شخصیت بر پایهٔ مدل پنج عاملی: روان‌رنجوری (نوروتیسم)، برون‌گرایی، "
            "باز بودن به تجربه، سازگاری و وجدان. این نسخهٔ رسمی فرم بلند با ۲۴۰ گویه است و علاوه بر "
            "نمرهٔ کل، ریزنمرهٔ ۳۰ وجه شخصیتی را گزارش می‌کند (هر بعد = جمع ۶ وجه آن). "
            "زمان برگزاری حدود ۴۵ تا ۶۰ دقیقه و پاسخ‌گویی به همهٔ گویه‌ها الزامی است."
        ),
        "topic": "فردی",
        "status": "published",
        "age_range": "بالای ۱۶ سال",
        "estimated_minutes": 60,
        "accent_color": "#6d4a8a",
        "sort_order": 2,
        "questions": questions,
        "interpretations": interps,
    }


def build_ghq() -> dict:
    questions = []
    for prompt, sub, positive in GHQ_ITEMS:
        opts = GHQ_OPTIONS_POS if positive else GHQ_OPTIONS_NEG
        questions.append({
            "prompt": prompt,
            "options": [[lbl, s] for lbl, s in opts],
            "subscale": sub,
        })
    interps = [
        {"score_min": 0, "score_max": 21, "label": "سلامت روان مطلوب",
         "guidance": "وضعیت سلامت عمومی شما مطلوب است (نمرهٔ برش GHQ-28 در نمره‌دهی لیکرت ۲۲ است). "
                     "ریزنمرهٔ چهار بُعد (هر بُعد از ۰ تا ۲۱) را نیز در نظر بگیرید."},
        {"score_min": 22, "score_max": 28, "label": "نشانه‌های خفیف",
         "guidance": "نشانه‌های خفیفی گزارش شده است؛ رصد وضعیت، خواب منظم و مراجعهٔ مشورتی در صورت ادامه توصیه می‌شود."},
        {"score_min": 29, "score_max": 42, "label": "نشانه‌های متوسط",
         "guidance": "سطح قابل توجهی نشانه گزارش شده است؛ مراجعه به مشاور یا روان‌شناس برای ارزیابی دقیق‌تر توصیه می‌شود."},
        {"score_min": 43, "score_max": 84, "label": "نشانه‌های شدید",
         "guidance": "سطح بالای پریشانی گزارش شده است؛ لطفاً در اولین فرصت با روان‌شناس یا روان‌پزشک مشورت کنید."},
    ]
    return {
        "slug": "ghq-28",
        "code": "GHQ-28",
        "title": "پرسشنامه سلامت عمومی (GHQ-28)",
        "en": "General Health Questionnaire-28",
        "description": (
            "ابزار غربالگری استاندارد سلامت روان گلدبرگ و هیلر با ۲۸ گویه دربارهٔ ماه گذشته؛ "
            "چهار زیرمقیاس ۷ گویه‌ای: نشانه‌های جسمانی، اضطراب و بی‌خوابی، کارکرد اجتماعی و افسردگی شدید. "
            "مقیاس پاسخ چهارگانی مطابق فرم رسمی (اصلا / در حد معمول / تقریبا در حد معمول / "
            "به مراتب بیش از حد معمول) با نمره‌دهی لیکرت ۰ تا ۳ و نمرهٔ برش ۲۲."
        ),
        "topic": "سلامت روان",
        "status": "published",
        "age_range": "بزرگسالان و نوجوانان",
        "estimated_minutes": 10,
        "accent_color": "#b04a5a",
        "sort_order": 4,
        "questions": questions,
        "interpretations": interps,
    }


def main() -> int:
    # --- NEO: جایگزینی فقط ورودی neo-pi-r در tests_part6.json
    p6 = SEED_DIR / "tests_part6.json"
    part6 = json.loads(p6.read_text(encoding="utf-8"))
    kept = [t for t in part6 if t["slug"] != "neo-pi-r"]
    kept.append(build_neo())
    p6.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tests_part6.json: {len(kept)} آزمون (neo-pi-r بازنویسی شد — {len(kept[-1]['questions'])} گویه)")

    # --- GHQ: جایگزینی فقط ورودی ghq-28 در tests_part7.json
    p7 = SEED_DIR / "tests_part7.json"
    part7 = json.loads(p7.read_text(encoding="utf-8"))
    kept = [t for t in part7 if t["slug"] != "ghq-28"]
    kept.append(build_ghq())
    p7.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tests_part7.json: {len(kept)} آزمون (ghq-28 بازنویسی شد — {len(kept[-1]['questions'])} گویه)")

    # --- آزمون‌های جدید esanj
    extras = [build_scl90(), build_mbi(), build_bpaq(), ex2.build_gse(), ex2.build_attach(),
              ex2.build_ata(), ex2.build_whoqol(), ex2.build_ffmq(), ex2.build_lss()]
    (SEED_DIR / "tests_part11.json").write_text(
        json.dumps(extras, ensure_ascii=False, indent=1), encoding="utf-8")
    total_q = sum(len(t["questions"]) for t in extras)
    print(f"tests_part11.json: {len(extras)} آزمون جدید | {total_q} سؤال")
    for t in extras:
        subs = len({q.get("subscale") for q in t["questions"] if q.get("subscale")})
        print(f"   {t['slug']:18s} {t['title'][:44]:46s} qs={len(t['questions']):3d} subs={subs}")

    # --- اعتبارسنجی‌ها
    for t in [build_neo(), build_ghq(), *extras]:
        n = len(t["questions"])
        assert 1 <= n <= 500
        mx = sum(max(s for _, s in q["options"]) for q in t["questions"])
        bands_covered = t["interpretations"][0]["score_min"] == 0 and t["interpretations"][-1]["score_max"] >= mx
        assert bands_covered, f"بازه تفسیر {t['slug']} کل نمره را نمی‌پوشاند (max={mx})"
        for qq in t["questions"]:
            scores = [s for _, s in qq["options"]]
            assert len(scores) >= 2 and all(0 <= s <= 6 for s in scores)
        print(f"[OK] {t['slug']:18s} qs={n:3d} max_total={mx:4d} bands=0..{t['interpretations'][-1]['score_max']}")

    # چک NEO: ۳۰ وجه × ۸ گویه
    from collections import Counter
    neo = build_neo()
    c = Counter(q["subscale"] for q in neo["questions"])
    assert len(c) == 30 and all(v == 8 for v in c.values()), "ساختار ۳۰ وجه خراب است"
    rev = sum(1 for qq in neo["questions"] if qq["options"][0][1] == 4)
    print(f"[OK] NEO: 30 وجه × 8 گویه | گویه‌های معکوس = {rev}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
