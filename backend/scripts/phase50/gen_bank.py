# -*- coding: utf-8 -*-
"""فاز ۵۰ — مولد بانک آزمون مطابق مرجع ۲۲ آزمون «راز زندگی».

اجرا (از پوشه backend):
    python scripts/phase50/gen_bank.py

خروجی: psych_seed/tests_part5..10.json + psych_seed/images/cpm|rspm/*.png
به‌همراه meta.json (متادیتای ابزارهای موجود قبلی).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import items_core
import items_eq
import items_neo
import items_raven
import items_upgrade

SEED_DIR = Path(__file__).resolve().parents[2] / "psych_seed"


def main() -> int:
    parts: dict[str, list[dict]] = {
        "tests_part5.json": items_core.build_both(),
        "tests_part6.json": items_neo.build_all(),
        "tests_part7.json": [items_eq.build_eqi90(20261021), items_eq.build_sch_eq33(20261021),
                             items_eq.build_sseis41(20261021), items_eq.build_ghq28(20261021)],
        "tests_part8.json": [items_eq.build_msq19(20261021), items_eq.build_osi60(20261021),
                             items_eq.build_jcq37(20261021), items_eq.build_hcq60(20261021),
                             items_eq.build_ttct60(20261021)],
        "tests_part9.json": items_raven.build_all(),
        "tests_part10.json": items_upgrade.build_all(),
    }
    total_q = 0
    for fname, tests in parts.items():
        out = SEED_DIR / fname
        out.write_text(json.dumps(tests, ensure_ascii=False, indent=1), encoding="utf-8")
        nq = sum(len(t["questions"]) for t in tests)
        total_q += nq
        print(f"{fname}: {len(tests)} آزمون | {nq} سؤال")
        for t in tests:
            subs = len({q.get("subscale") for q in t["questions"] if q.get("subscale")})
            imgs = sum(1 for q in t["questions"] if q.get("image"))
            print(f"   {t['code']:14s} {t['title'][:44]:46s} qs={len(t['questions']):4d} "
                  f"subs={subs:2d} imgs={imgs:3d} status={t['status']} total_max={sum(max(s for _, s in q['options']) for q in t['questions'])}")
    print(f"\nمجموع: {sum(len(v) for v in parts.values())} آزمون جدید/ارتقا | {total_q} سؤال")

    # متادیتای ابزارهای موجود قبلی (بدون دست‌زدن به سؤال‌ها)
    meta = {
        "bdi-ii": {"code": "BDI-II-21", "age_range": "بزرگسالان - نوجوانان", "estimated_minutes": 10,
                   "accent_color": "#facc15", "sort_order": 9},
        "bai": {"code": "BAI-21", "age_range": "بزرگسالان - نوجوانان", "estimated_minutes": 10,
                "accent_color": "#4ade80", "sort_order": 10},
        "dass-21": {"code": "DASS-21", "age_range": "بزرگسالان", "estimated_minutes": 10,
                    "accent_color": "#b04a5a", "sort_order": 24},
        "phq-9": {"code": "PHQ-9", "age_range": "بزرگسالان", "estimated_minutes": 5,
                  "accent_color": "#b04a5a", "sort_order": 25},
        "gad-7": {"code": "GAD-7", "age_range": "بزرگسالان", "estimated_minutes": 5,
                  "accent_color": "#b04a5a", "sort_order": 26},
        "pss-10": {"code": "PSS-10", "age_range": "بزرگسالان", "estimated_minutes": 5,
                   "accent_color": "#b04a5a", "sort_order": 27},
        "ghq-12": {"code": "GHQ-12", "age_range": "بزرگسالان", "estimated_minutes": 5,
                   "accent_color": "#facc15", "sort_order": 28},
        "rosenberg": {"code": "RSE-10", "age_range": "بالای ۱۵ سال", "estimated_minutes": 5,
                      "accent_color": "#7a5c8a", "sort_order": 29},
        "mes-20": {"code": "MES-20", "age_range": "بزرگسالان", "estimated_minutes": 10,
                   "accent_color": "#ec4899", "sort_order": 30},
        "eq-24": {"code": "EQ-24", "age_range": "بالای ۱۵ سال", "estimated_minutes": 10,
                  "accent_color": "#9333ea", "sort_order": 31},
        "gardner-mit": {"code": "MIT-40", "age_range": "نوجوان، بزرگسال", "estimated_minutes": 12,
                        "accent_color": "#9333ea", "sort_order": 15},
    }
    (SEED_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"meta.json: {len(meta)} ابزار موجود")
    return 0


if __name__ == "__main__":
    sys.exit(main())
