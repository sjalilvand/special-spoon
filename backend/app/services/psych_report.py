"""فاز ۶۳ - سازندهٔ گزارش تحلیلی چندلایهٔ نتایج آزمون (مدل مرجع ای‌سنج).

ورودی: ابزار + سؤال‌ها + پاسخ‌ها؛ خروجی: snapshot ساخت‌یافتهٔ JSON برای
``psych_attempts.result_payload``:

    {
      "version": 1,
      "total": {"score": 312, "max": 960, "percent": 33, "label": "پروفایل متعادل", "guidance": "..."},
      "dominant": {"key": "o", "title": "باز بودن", "percent": 78} | None,
      "scales": [
        {"key": "n", "title": "روان‌رنجوری", "description": "...", "color": "#b04a5a",
         "direction": "balanced", "score": 150, "max": 192, "percent": 78,
         "level": {"label": "بالا", "text": "...", "guidance": "..."} | None,
         "children": [ {... وجه‌ها ...} ]}
      ]
    }

قواعد:
- مقیاس برگ (بدون فرزند): نمره = جمع امتیاز گزینه‌های انتخابی سؤال‌هایی که
  ``subscale`` آن‌ها در ``match_names`` است؛ بیشینه = جمع بیشینهٔ همان گزینه‌ها؛
- مقیاس بعد (دارای فرزند): نمره = جمع نمرهٔ فرزندها (بیشینه به همان روش)؛
- سطح: اولین بازهٔ ``levels`` شامل نمره؛ بدون بازه → سطح None (فقط نمره/درصد)؛
- «مقیاس غالب»: بالاترین درصد در میان بُعدهای سطح بالا (حداقل ۳ بُعد) —
  برای ابزارهای صفتی مانند نئو/هالند/گاردنر معنا دارد.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.psych_test import PsychScale, PsychTest, PsychQuestion


def _level_for(levels: list | None, score: int) -> dict | None:
    for lv in levels or []:
        try:
            if int(lv["min"]) <= score <= int(lv["max"]):
                return {
                    "label": str(lv.get("label") or ""),
                    "text": lv.get("text") or None,
                    "guidance": lv.get("guidance") or None,
                }
        except (TypeError, ValueError):
            continue
    return None


# فاز ۶۵ - نوارهای شدت عمومی (درصد نسبت به بیشینهٔ همان بعد) برای ابزارهایی که
# هیچ ردیف PsychScale ندارند؛ برچسب‌ها توصیفی‌اند (نه تشخیصی) و مقیاس‌های
# ثبت‌شدهٔ seed (سطح‌بندی اختصاصی) همیشه بر آن‌ها اولویت دارند.
_GENERIC_LEVELS: tuple[tuple[int, str, str], ...] = (
    (34, "در محدوده عادی", "نمرهٔ این بعد در محدودهٔ عادی قرار دارد."),
    (50, "خفیف", "نشانه‌های خفیفی در این بعد دیده می‌شود؛ پیگیری عادی کافی است."),
    (67, "متوسط", "این بعد نسبتاً برجسته است؛ گفت‌وگو دربارهٔ آن با مشاور مفید خواهد بود."),
    (101, "شدید", "این بعد فشار قابل‌توجهی را نشان می‌دهد؛ بررسی آن در جلسه با مشاور توصیه می‌شود."),
)


def _generic_level(percent: int) -> dict:
    """سطح عمومی بر پایهٔ درصد ۰..۱۰۰"""
    for cap, label, text in _GENERIC_LEVELS:
        if percent < cap:
            return {"label": label, "text": text, "guidance": None}
    cap, label, text = _GENERIC_LEVELS[-1]
    return {"label": label, "text": text, "guidance": None}


def build_report_payload(
    db: Session,
    test: PsychTest,
    questions: list[PsychQuestion],
    answers: list[int],
    total_score: int,
    total_max: int,
    total_label: str | None = None,
    total_guidance: str | None = None,
) -> dict | None:
    scales = db.scalars(
        select(PsychScale).where(PsychScale.test_id == test.id).order_by(PsychScale.sort_order)
    ).all()
    if not scales:
        return _synthesize_from_subscales(
            questions, answers, total_score=total_score, total_max=total_max,
            total_label=total_label, total_guidance=total_guidance,
        )

    # نمره و بیشینهٔ هر مقیاس برگ از سؤال‌های هم‌نام با match_names
    # (وجه‌ها هم parent_id دارند؛ مقیاس بعد match_names ندارد — تطابق نام کافی است)
    raw: dict[uuid.UUID, dict] = {s.id: {"score": 0, "max": 0, "scale": s} for s in scales}
    for qi, q in enumerate(questions):
        sub = q.subscale
        if not sub or qi >= len(answers):
            continue
        opts = q.options or []
        idx = answers[qi]
        try:
            got = int(opts[idx].get("score", 0))
            top = max(int(o.get("score", 0)) for o in opts)
        except (IndexError, TypeError, ValueError):
            continue
        for s in scales:
            if sub in (s.match_names or []):
                raw[s.id]["score"] += got
                raw[s.id]["max"] += top

    # مرتب‌سازی فرزندها زیر والد + جمع نمرهٔ بعد از فرزندها
    out_scales: list[dict] = []
    for s in scales:
        if s.parent_id is not None:
            continue
        children = [
            {"key": c.key, "title": c.title, "description": c.description,
             "color": c.color, "direction": c.direction,
             "score": raw[c.id]["score"], "max": raw[c.id]["max"],
             "percent": round(raw[c.id]["score"] / raw[c.id]["max"] * 100) if raw[c.id]["max"] else 0,
             "level": _level_for(c.levels, raw[c.id]["score"]),
             "children": None}
            for c in scales if c.parent_id == s.id
        ]
        score = raw[s.id]["score"] + sum(c["score"] for c in children)
        smax = raw[s.id]["max"] + sum(c["max"] for c in children)
        out_scales.append({
            "key": s.key, "title": s.title, "description": s.description,
            "color": s.color, "direction": s.direction,
            "score": score, "max": smax,
            "percent": round(score / smax * 100) if smax else 0,
            "level": _level_for(s.levels, score),
            "children": children or None,
        })

    # مقیاس غالب: بالاترین درصد در بُعدهای سطح بالا (حداقل ۳ بُعد)
    # max() با ترتیب فعلی (sort_order) اولین بیشینه را نگه می‌دارد — تعادل سید
    dominant = None
    top_with_pct = [x for x in out_scales if x["max"] > 0]
    if len(top_with_pct) >= 3:
        best = max(top_with_pct, key=lambda x: x["percent"])
        dominant = {"key": best["key"], "title": best["title"], "percent": best["percent"]}

    return {
        "version": 1,
        "total": {
            "score": total_score,
            "max": total_max,
            "label": total_label,
            "guidance": total_guidance,
        },
        "dominant": dominant,
        "scales": out_scales,
    }


def _synthesize_from_subscales(
    questions: list[PsychQuestion],
    answers: list[int],
    total_score: int,
    total_max: int,
    total_label: str | None = None,
    total_guidance: str | None = None,
) -> dict | None:
    """فاز ۶۵ - فالبک سنتز گزارش از زیرمقیاس‌های سؤال‌ها.

    ابزار بدون ردیف PsychScale (مثلاً ابزار دستی ادمین یا بانک پیش از اجرای
    seed مقیاس‌ها) به‌جای نمای سادهٔ گیج، گزارش چندلایهٔ فاز ۶۳ می‌گیرد:
    یک مقیاس به‌ازای هر زیرمقیاس + سطح عمومی درصدی. ابزار تک‌بعدی (بدون
    subscale) همان‌طور که قبلاً None برمی‌گرداند (نمای کلاسیک گیج کافی است).
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for qi, q in enumerate(questions):
        sub = q.subscale
        if not sub or qi >= len(answers):
            continue
        opts = q.options or []
        try:
            got = int(opts[answers[qi]].get("score", 0))
            top = max(int(o.get("score", 0)) for o in opts)
        except (IndexError, TypeError, ValueError):
            continue
        if sub not in groups:
            groups[sub] = {"score": 0, "max": 0}
            order.append(sub)
        groups[sub]["score"] += got
        groups[sub]["max"] += top
    if not order:
        return None
    out_scales: list[dict] = []
    for name in order:
        g = groups[name]
        pct = round(g["score"] / g["max"] * 100) if g["max"] else 0
        out_scales.append({
            "key": name,
            "title": name,
            "description": None,
            "color": None,
            # جهت بالینی: نمرهٔ بالاتر = بدتر (ابزارهای دارای subscale در این پلتفرم
            # عمدتاً نشانه‌محورند؛ مقیاس‌های seed اختصاصی همیشه جایگزین‌اند)
            "direction": "higher_worse",
            "score": g["score"], "max": g["max"], "percent": pct,
            "level": _generic_level(pct),
            "children": None,
        })
    dominant = None
    top_with_pct = [x for x in out_scales if x["max"] > 0]
    if len(top_with_pct) >= 3:
        best = max(top_with_pct, key=lambda x: x["percent"])
        dominant = {"key": best["key"], "title": best["title"], "percent": best["percent"]}
    return {
        "version": 1,
        "total": {
            "score": total_score,
            "max": total_max,
            "label": total_label,
            "guidance": total_guidance,
        },
        "dominant": dominant,
        "scales": out_scales,
    }
