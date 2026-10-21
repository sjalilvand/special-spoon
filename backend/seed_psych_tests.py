"""فاز ۴۷ و ۵۰ - درج بانک آزمون‌های روان‌شناسی استاندارد (B37).

اجرا:  docker compose run --rm api python seed_psych_tests.py
یا:    python seed_psych_tests.py  (در محیط backend)

- idempotent: ابزار موجود با همان slug حذف سؤال‌ها و درج مجدد می‌شود
  (نسخه علمی جدید)؛ ابزار تازه با وضعیت فایل (published/draft) درج می‌شود.
- دسته‌های موضوعی (B32) در صورت نبود، ساخته می‌شوند.
- فاز ۵۰: پوشش کامل ۲۲ آزمون مرجع «راز زندگی» + متادیتای کاتالوگ
  (code/age_range/estimated_minutes/accent_color/sort_order) + عکس پیوست
  سؤال‌های تصویری (ریون) با کپی به uploads/psych_images + meta.json برای
  متادیتای ابزارهای قبلی بدون دست‌زدن به سؤال‌ها.
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


def _numeric_sorted(paths: list[Path]) -> list[Path]:
    """ترتیب عددی tests_part2 < tests_part10 (نه لغوی)."""
    def key(p: Path):
        digits = "".join(ch for ch in p.stem if ch.isdigit())
        return (int(digits) if digits else 0, p.name)
    return sorted(paths, key=key)


def _copy_question_image(rel: str) -> str:
    """فاز ۵۰ — کپی عکس سؤال از psych_seed/images به uploads/psych_images.

    خروجی: مسیر نسبی برای image_path (سرو از /api/v1/public/psych-images).
    """
    src = SEED_DIR / "images" / rel
    if not src.is_file():
        raise SystemExit(f"عکس سؤال یافت نشد: {src}")
    dst_dir = Path("uploads/psych_images") / Path(rel).parent
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / Path(rel).name
    if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
        dst.write_bytes(src.read_bytes())
    return rel


def _get_or_create_topic(db, name: str):
    from sqlalchemy import select as _select
    topic = db.scalars(_select(Topic).where(Topic.slug == slug_topic_slug(name))).first()
    if topic is None:
        topic = Topic(name=name, slug=slug_topic_slug(name),
                      description="دسته موضوعی ابزارهای روان‌سنجی — درج اولیه سامانه",
                      is_active=True, sort_order=0)
        db.add(topic)
        db.flush()
    return topic


def _apply_meta(db, t: PsychTest, meta: dict) -> None:
    """اعمال متادیتای فاز ۵۰ روی ابزار."""
    t.code = meta.get("code")
    t.age_range = meta.get("age_range")
    t.estimated_minutes = meta.get("estimated_minutes")
    t.accent_color = meta.get("accent_color")
    t.sort_order = int(meta.get("sort_order") or 0)


def main() -> int:
    files = _numeric_sorted(list(SEED_DIR.glob("tests_part*.json")))
    if not files:
        print(f"هیچ فایل داده‌ای در {SEED_DIR} نیست")
        return 1
    tests: list[dict] = []
    for f in files:
        tests.extend(json.loads(f.read_text(encoding="utf-8")))

    db = SessionLocal()
    created, updated, meta_only = [], [], []
    try:
        for t_data in tests:
            slug = t_data["slug"]
            topic = _get_or_create_topic(db, t_data["topic"])

            existing = db.scalars(select(PsychTest).where(PsychTest.slug == slug)).first()
            if existing is not None:
                # نسخه علمی جدید: سؤال‌ها و بازه‌ها از نو
                for q in db.scalars(select(PsychQuestion).where(PsychQuestion.test_id == existing.id)).all():
                    db.delete(q)
                for i in db.scalars(select(PsychInterpretation).where(PsychInterpretation.test_id == existing.id)).all():
                    db.delete(i)
                existing.title = t_data["title"]
                existing.description = t_data["description"]
                existing.topic_id = topic.id
                existing.status = t_data.get("status", PsychStatus.PUBLISHED)
                existing.review_note = "درج اولیه بانک آزمون‌ها توسط سامانه (فاز ۵۰)"
                db.flush()
                test = existing
                updated.append(t_data["title"])
            else:
                test = PsychTest(
                    slug=slug, title=t_data["title"], description=t_data["description"],
                    topic_id=topic.id, status=t_data.get("status", PsychStatus.PUBLISHED),
                    review_note="درج اولیه بانک آزمون‌ها توسط سامانه (فاز ۵۰)",
                )
                db.add(test)
                db.flush()
                created.append(t_data["title"])
            _apply_meta(db, test, t_data)

            for idx, q in enumerate(t_data["questions"]):
                image_rel = q.get("image")
                db.add(PsychQuestion(
                    test_id=test.id,
                    prompt=q["prompt"].strip(),
                    options=resolve_options(q["options"]),
                    subscale=q.get("subscale"),
                    image_path=_copy_question_image(image_rel) if image_rel else None,
                    sort_order=idx,
                ))
            for idx, i in enumerate(t_data["interpretations"]):
                db.add(PsychInterpretation(
                    test_id=test.id,
                    score_min=int(i["score_min"]),
                    score_max=int(i["score_max"]),
                    label=i["label"].strip(),
                    guidance=i.get("guidance"),
                    sort_order=idx,
                ))

        # فاز ۵۰ — متادیتای ابزارهای بدون فایل کامل (bdi-ii و بقیه فرم‌های فاز ۴۷)
        # پس از ساخت/به‌روزرسانی همه ابزارها اعمال می‌شود تا در دیتابیس خالی هم مؤثر باشد.
        meta_path = SEED_DIR / "meta.json"
        if meta_path.is_file():
            for slug, meta in json.loads(meta_path.read_text(encoding="utf-8")).items():
                t = db.scalars(select(PsychTest).where(PsychTest.slug == slug)).first()
                if t is None:
                    continue
                _apply_meta(db, t, meta)
                meta_only.append(slug)

        db.commit()
        print(f"درج انجام شد — جدید: {len(created)} | به‌روزرسانی: {len(updated)} | فقط متادیتا: {len(meta_only)}")
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
