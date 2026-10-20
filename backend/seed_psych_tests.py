"""فاز ۴۷ - درج بانک آزمون‌های روان‌شناسی استاندارد (B37).

اجرا:  docker compose run --rm api python seed_psych_tests.py
یا:    python seed_psych_tests.py  (در محیط backend)

- idempotent: ابزار موجود با همان slug حذف سؤال‌ها و درج مجدد می‌شود
  (نسخه علمی جدید)؛ ابزار تازه status=published با یادداشت درج اولیه.
- دسته‌های موضوعی (B32) در صورت نبود، ساخته می‌شوند.
- مقیاس‌های آماده: never0-3، freq0-3، freq0-4، freq4-0، agree0-3،
  agree3-0، ghqNeg، ghqPos — سؤال بدون subscale برای ابزار تک‌بُعدی.
"""
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.psych_test import (
    PsychAttempt, PsychInterpretation, PsychQuestion, PsychStatus, PsychTest,
)
from app.models.topics import Topic

SEED_DIR = Path(__file__).resolve().parent / "psych_seed"

SCALES: dict[str, list[tuple[str, int]]] = {
    "never0-3": [("هرگز", 0), ("چند روز", 1), ("بیش از نصف روزها", 2), ("تقریباً هر روز", 3)],
    "freq0-3": [("هرگز", 0), ("به‌ندرت", 1), ("اغلب", 2), ("همیشه", 3)],
    "freq0-4": [("هرگز", 0), ("به‌ندرت", 1), ("گاهی", 2), ("بیشتر وقت‌ها", 3), ("همیشه", 4)],
    "freq4-0": [("هرگز", 4), ("به‌ندرت", 3), ("گاهی", 2), ("بیشتر وقت‌ها", 1), ("همیشه", 0)],
    "agree0-3": [("کاملاً مخالفم", 0), ("مخالفم", 1), ("موافقم", 2), ("کاملاً موافقم", 3)],
    "agree3-0": [("کاملاً موافقم", 0), ("موافقم", 1), ("مخالفم", 2), ("کاملاً مخالفم", 3)],
    "ghqNeg": [("بهتر از حد معمول", 0), ("مثل همیشه", 0), ("کمتر از حد معمول", 1), ("بسیار کمتر از حد معمول", 1)],
    "ghqPos": [("بیشتر از حد معمول", 0), ("مثل همیشه", 0), ("کمتر از حد معمول", 1), ("بسیار کمتر از حد معمول", 1)],
}


def resolve_options(raw) -> list[dict]:
    if isinstance(raw, str):
        scale = SCALES.get(raw)
        if scale is None:
            raise SystemExit(f"مقیاس ناشناخته: {raw}")
        return [{"label": lbl, "score": int(s)} for lbl, s in scale]
    return [{"label": str(o[0]), "score": int(o[1])} for o in raw]


def main() -> int:
    files = sorted(SEED_DIR.glob("tests_part*.json"))
    if not files:
        print(f"هیچ فایل داده‌ای در {SEED_DIR} نیست")
        return 1
    tests: list[dict] = []
    for f in files:
        tests.extend(json.loads(f.read_text(encoding="utf-8")))

    db = SessionLocal()
    created, updated = [], []
    try:
        for t in tests:
            slug = t["slug"]
            topic = db.scalars(select(Topic).where(Topic.slug == slug_topic_slug(t["topic"]))).first()
            if topic is None:
                topic = Topic(name=t["topic"], slug=slug_topic_slug(t["topic"]),
                              description="دسته موضوعی ابزارهای روان‌سنجی — درج اولیه سامانه",
                              is_active=True, sort_order=0)
                db.add(topic)
                db.flush()

            existing = db.scalars(select(PsychTest).where(PsychTest.slug == slug)).first()
            if existing is not None:
                # نسخه علمی جدید: سؤال‌ها و بازه‌ها از نو
                for q in db.scalars(select(PsychQuestion).where(PsychQuestion.test_id == existing.id)).all():
                    db.delete(q)
                for i in db.scalars(select(PsychInterpretation).where(PsychInterpretation.test_id == existing.id)).all():
                    db.delete(i)
                existing.title = t["title"]
                existing.description = t["description"]
                existing.topic_id = topic.id
                existing.status = PsychStatus.PUBLISHED
                existing.review_note = "درج اولیه بانک آزمون‌ها توسط سامانه (فاز ۴۷)"
                db.flush()
                test = existing
                updated.append(t["title"])
            else:
                test = PsychTest(
                    slug=slug, title=t["title"], description=t["description"],
                    topic_id=topic.id, status=PsychStatus.PUBLISHED,
                    review_note="درج اولیه بانک آزمون‌ها توسط سامانه (فاز ۴۷)",
                )
                db.add(test)
                db.flush()
                created.append(t["title"])

            for idx, q in enumerate(t["questions"]):
                db.add(PsychQuestion(
                    test_id=test.id,
                    prompt=q["prompt"].strip(),
                    options=resolve_options(q["options"]),
                    subscale=q.get("subscale"),
                    sort_order=idx,
                ))
            for idx, i in enumerate(t["interpretations"]):
                db.add(PsychInterpretation(
                    test_id=test.id,
                    score_min=int(i["score_min"]),
                    score_max=int(i["score_max"]),
                    label=i["label"].strip(),
                    guidance=i.get("guidance"),
                    sort_order=idx,
                ))

        db.commit()
        print(f"درج انجام شد — جدید: {len(created)} | به‌روزرسانی: {len(updated)}")
        for title in created:
            print(f"  + {title}")
        for title in updated:
            print(f"  ~ {title}")
        return 0
    finally:
        db.close()


def slug_topic_slug(name: str) -> str:
    mapping = {
        "سلامت روان": "salamat-ravan",
        "فردی": "fardi",
        "زوج و خانواده": "zoj-khanevade",
        "شغلی": "shoghli",
        "هوش": "hoosh",
    }
    return mapping.get(name, name.replace(" ", "-").lower())


if __name__ == "__main__":
    sys.exit(main())
