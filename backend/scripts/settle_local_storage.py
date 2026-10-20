"""فاز ۴۱ - گام ۴ طرح مهاجرت ADR-04: CLI تسویه volume محلی.

اجرا (روی سرور، کنار backend):
    cd backend
    python scripts/settle_local_storage.py --dry-run            # اول فقط گزارش
    python scripts/settle_local_storage.py                      # مهاجرت + گزارش (بدون حذف)
    python scripts/settle_local_storage.py --enforce            # + حذف نسخه محلی پس از راستی‌آزمایی
    python scripts/settle_local_storage.py --enforce --loop     # تا اتمام، دسته‌دسته

پیش‌نیاز: DATABASE_URL + S3_* کامل در محیط/.env (آداپتور s3_ready باشد) و
اجرای موفق migrate_files_to_s3.py (گام ۲). طراحی idempotent است: هر تعداد
اجرای مجدد امن؛ حذف فیزیکی فقط با --enforce و فقط پس از خواندن مجدد از S3 و
مقایسه sha256؛ خطا/ناسازگاری → نسخه محلی حفظ می‌شود.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# backend/ را به sys.path اضافه می‌کند تا «python scripts/...» از ریشه backend کار کند
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import object_storage as objstore  # noqa: E402
from app.services.storage_settlement import settle_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="تسویه idempotent volume محلی (گام ۴ طرح ADR-04) — حذف فقط با --enforce"
    )
    parser.add_argument("--limit", type=int, default=200, help="سقف ردیف در هر دسته (پیش‌فرض ۲۰۰)")
    parser.add_argument("--dry-run", action="store_true", help="فقط شمارش؛ هیچ نوشتنی انجام نمی‌شود")
    parser.add_argument(
        "--enforce", action="store_true",
        help="پس از راستی‌آزمایی S3، نسخه محلی ردیف‌های s3 حذف شود (بدون آن فقط گزارش)",
    )
    parser.add_argument("--loop", action="store_true", help="تا اتمام ردیف‌ها تکرار کن (دسته‌دسته)")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="مکث بین دسته‌ها در --loop")
    args = parser.parse_args()

    if args.loop and args.dry_run:
        print("[خطا] --loop با --dry-run بی‌معناست (dry-run هیچ چیزی را تغییر نمی‌دهد).", file=sys.stderr)
        return 1

    s = get_settings()
    if not objstore.s3_ready(s):
        print(
            "[خطا] آداپتور S3 آماده نیست — S3_ENDPOINT_URL/S3_BUCKET/S3_ACCESS_KEY/"
            "S3_SECRET_KEY را کامل کنید و boto3 را نصب کنید.",
            file=sys.stderr,
        )
        return 1

    total = {
        "scanned": 0, "migrated": 0, "would_migrate": 0, "skipped_missing": 0,
        "checksum_mismatch": 0, "leftover_scanned": 0, "cleaned": 0,
        "would_clean": 0, "verify_failed": 0, "bytes_freed": 0, "errors": 0,
    }
    rounds = 0
    while True:
        rounds += 1
        db = SessionLocal()
        try:
            report = settle_batch(
                db, s=s, limit=args.limit, dry_run=args.dry_run, enforce=args.enforce
            )
        finally:
            db.close()
        print(f"batch #{rounds}: {report.summary()}")
        for line in report.details:
            print(f"  {line}")
        for key in total:
            total[key] += getattr(report, key)
        # اتمام: دسته‌ای که نه ردیف local دارد و نه نسخه محلیِ ردیف s3 → کار تمام است
        if not args.loop or (report.scanned == 0 and report.leftover_scanned == 0):
            break
        time.sleep(max(0.0, args.sleep_seconds))

    mode = "dry-run" if args.dry_run else ("settle+clean" if args.enforce else "settle")
    print(
        f"TOTAL [{mode}] rounds={rounds} migrated={total['migrated']} "
        f"would_migrate={total['would_migrate']} missing={total['skipped_missing']} "
        f"checksum_mismatch={total['checksum_mismatch']} | leftover={total['leftover_scanned']} "
        f"cleaned={total['cleaned']} would_clean={total['would_clean']} "
        f"verify_failed={total['verify_failed']} bytes_freed={total['bytes_freed']} "
        f"errors={total['errors']}"
    )
    if not args.dry_run and not args.enforce:
        print("نسخه محلی حفظ شد — حذف فیزیکی فقط با --enforce و پس از راستی‌آزمایی S3 انجام می‌شود.")
    if total["errors"] == 0 and total["verify_failed"] == 0:
        print("گزارش پاک است → می‌توانید volume محلی را «فقط-خواندنی» کنید (رو/:ro در compose).")
    return 0 if total["errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
