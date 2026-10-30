"""فاز ۶۳ - درج مقیاس‌ها و تفسیر سطح‌بندی‌شدهٔ آزمون‌ها (سازگار با فاز ۵۰).

اجرا: python seed_psych_scales.py   (در محیط backend — پس از seed_psych_tests)

- منبع داده: backend/psych_seed/scales.json (تولیدشده از محتوای تفسیری فاز ۶۳)؛
- idempotent: مقیاس‌های هر ابزار حذف و از نو درج می‌شوند (نسخهٔ علمی جدید)؛
- والد قبل از فرزند درج می‌شود تا parent_id قابل ست‌شدن باشد؛
- ابزارهای بدون ردیف در scales.json دست‌نخورده می‌مانند (بدون مقیاس → گزارش
  کلاسیک گیج نمره).
"""
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.psych_test import PsychScale, PsychTest

SEED_DIR = Path(__file__).resolve().parent / "psych_seed"
SCALES_FILE = SEED_DIR / "scales.json"


def main() -> int:
    if not SCALES_FILE.is_file():
        print(f"فایل مقیاس‌ها یافت نشد: {SCALES_FILE}")
        return 1
    docs = json.loads(SCALES_FILE.read_text(encoding="utf-8"))

    db = SessionLocal()
    inserted, missing = 0, []
    try:
        for doc in docs:
            slug = doc["test_slug"]
            t = db.scalars(select(PsychTest).where(PsychTest.slug == slug)).first()
            if t is None:
                missing.append(slug)
                continue
            # نسخهٔ علمی جدید: مقیاس‌های قبلی این ابزار حذف و از نو درج می‌شود
            for s in db.scalars(select(PsychScale).where(PsychScale.test_id == t.id)).all():
                db.delete(s)
            db.flush()

            # والد‌ها اول؛ children با key به والد وصل می‌شوند
            id_by_key: dict[str, object] = {}
            for idx, sc in enumerate(doc["scales"]):
                s = PsychScale(
                    test_id=t.id,
                    parent_id=None,
                    key=sc["key"],
                    title=sc["title"],
                    description=sc.get("description"),
                    match_names=sc.get("match_names"),
                    levels=sc.get("levels"),
                    color=sc.get("color"),
                    direction=sc.get("direction") or "balanced",
                    sort_order=idx,
                )
                db.add(s)
                db.flush()
                id_by_key[sc["key"]] = s.id
                for j, ch in enumerate(sc.get("children") or []):
                    cs = PsychScale(
                        test_id=t.id,
                        parent_id=s.id,
                        key=ch["key"],
                        title=ch["title"],
                        description=ch.get("description"),
                        match_names=ch.get("match_names"),
                        levels=ch.get("levels"),
                        color=ch.get("color"),
                        direction=ch.get("direction") or "balanced",
                        sort_order=j,
                    )
                    db.add(cs)
                    db.flush()
                    id_by_key[ch["key"]] = cs.id
            inserted += len(id_by_key)

        db.commit()
        print(f"درج مقیاس‌ها انجام شد — کل ردیف: {inserted}")
        if missing:
            print(f"هشدار: {len(missing)} ابزار یافت نشد (اول seed_psych_tests را اجرا کنید):")
            for m in missing:
                print(f"  - {m}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
