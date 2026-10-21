# -*- coding: utf-8 -*-
"""فاز ۵۰ — ابزارهای مشترک مولد بانک آزمون مطابق مرجع ۲۲ آزمون «راز زندگی».

هر آزمون یک dict با ساختار هماهنگ با psych_seed/tests_part*.json است:
{
  slug, code, title, description, topic, status,
  age_range, estimated_minutes, accent_color, sort_order,
  questions: [{prompt, options: [[label, score]...] | "scale", subscale, image}],
  interpretations: [{score_min, score_max, label, guidance}],
}
"""
from __future__ import annotations

import random

# ------------------------------------------------------------- مقیاس‌های گزینه‌ای
AGREE4 = [("کاملاً مخالفم", 0), ("مخالفم", 1), ("موافقم", 2), ("کاملاً موافقم", 3)]
AGREE5 = [("کاملاً مخالفم", 0), ("مخالفم", 1), ("نظری ندارم", 2), ("موافقم", 3), ("کاملاً موافقم", 4)]
FREQ4 = [("هرگز", 0), ("به‌ندرت", 1), ("اغلب", 2), ("همیشه", 3)]
FREQ5 = [("هرگز", 0), ("به‌ندرت", 1), ("گاهی", 2), ("بیشتر وقت‌ها", 3), ("همیشه", 4)]
YESNO = [("بله", 1), ("خیر", 0)]
YESNO_R = [("بله", 0), ("خیر", 1)]
TF = [("درست", 1), ("نادرست", 0)]
TF_R = [("درست", 0), ("نادرست", 1)]
LIKE = [("دوست دارم", 1), ("دوست ندارم", 0)]
SAT5 = [("خیلی ناراضی", 0), ("ناراضی", 1), ("نظری ندارم", 2), ("راضی", 3), ("خیلی راضی", 4)]
ABC = [("الف", 0), ("ب", 1), ("ج", 2)]
PROD4 = [("خیلی کم", 0), ("کم", 1), ("زیاد", 2), ("خیلی زیاد", 3)]
# امتیازدهی GHQ (0-0-1-1) — برای گویه‌های نشانه‌ای و سلامت‌محور
GHQ_NEG = [("بهتر از حد معمول", 0), ("مثل همیشه", 0), ("کمتر از حد معمول", 1), ("بسیار کمتر از حد معمول", 1)]
GHQ_POS = [("بیشتر از حد معمول", 0), ("مثل همیشه", 0), ("کمتر از حد معمول", 1), ("بسیار کمتر از حد معمول", 1)]

SCALE_NAMES = {
    "agree4": AGREE4, "agree5": AGREE5, "freq4": FREQ4, "freq5": FREQ5,
    "yesno": YESNO, "yesno_r": YESNO_R, "tf": TF, "tf_r": TF_R,
    "like": LIKE, "sat5": SAT5, "abc": ABC, "prod4": PROD4,
    "ghqNeg": GHQ_NEG, "ghqPos": GHQ_POS,
}


def q(prompt: str, opts, subscale: str | None = None, reverse: bool = False, image: str | None = None) -> dict:
    """ساخت یک سؤال؛ reverse یعنی جدول امتیاز معکوس شود (برای گویه‌های معکوس)."""
    if isinstance(opts, str):
        base = list(SCALE_NAMES[opts])
        if reverse:
            base = [(lbl, max(s for _, s in SCALE_NAMES[opts]) - s) for lbl, s in base]
        out = {"prompt": prompt, "options": base}
    else:
        out = {"prompt": prompt, "options": [[lbl, int(s)] for lbl, s in opts]}
    if subscale:
        out["subscale"] = subscale
    if image:
        out["image"] = image
    return out


def test(slug, code, title, en, desc, topic, age, minutes, color, order, status, questions, interps) -> dict:
    return {
        "slug": slug, "code": code, "title": title, "en": en,
        "description": desc, "topic": topic, "status": status,
        "age_range": age, "estimated_minutes": minutes,
        "accent_color": color, "sort_order": order,
        "questions": questions, "interpretations": interps,
    }


def bands(total_max: int, specs: list[tuple[float, float, str, str]]) -> list[dict]:
    """ساخت بازه‌های تفسیر بر حسب نسبت (lo, hi, label, guidance)."""
    return [
        {"score_min": int(round(total_max * lo)), "score_max": int(round(total_max * hi)),
         "label": label, "guidance": guidance}
        for lo, hi, label, guidance in specs
    ]


def interleave(items: list[dict], rng: random.Random) -> list[dict]:
    """ترتیب سؤال‌ها را بین زیرمقیاس‌ها پراکنده می‌کند (شبیه ابزار واقعی)."""
    grouped: dict[str, list[dict]] = {}
    for it in items:
        grouped.setdefault(it.get("subscale") or f"_s{len(grouped)}", []).append(it)
    keys = list(grouped)
    out: list[dict] = []
    while any(grouped.values()):
        for k in keys:
            if grouped[k]:
                out.append(grouped[k].pop(rng.randrange(len(grouped[k]))))
    return out


def expand(stems: list[str], prefixes: list[str], target: int) -> list[str]:
    """گسترش پایه گویه‌ها با قیدهای آغازین برای رسیدن به تعداد هدف.

    قیدها طوری انتخاب شده‌اند که با جمله کامل سازگار باشند و تکرار معنایی
    رخ ندهد (هر stem حداکثر یک بار هر قید را می‌گیرد).
    """
    out: list[str] = list(stems)
    pi = 0
    while len(out) < target:
        s = stems[pi % len(stems)]
        p = prefixes[(pi // len(stems)) % len(prefixes)]
        cand = f"{p} {s}"
        if cand not in out:
            out.append(cand)
        else:
            out.append(f"{prefixes[(pi + 1) % len(prefixes)]} {s}")
        pi += 1
    return out[:target]
