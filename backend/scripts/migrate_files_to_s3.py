"""فاز ۳۸ - گام ۲ طرح مهاجرت ADR-04: CLI انتقال فایل‌های local به S3/MinIO.

اجرا (روی سرور، کنار backend):
    cd backend
    python scripts/migrate_files_to_s3.py --dry-run          # اول بدون نوشتن
    python scripts/migrate_files_to_s3.py --limit 200        # اجرای مرحله‌ای
    python scripts/migrate_files_to_s3.py --limit 200 --loop # تا اتمام، دسته‌دسته

پیش‌نیاز: DATABASE_URL + S3_* کامل در محیط/.env (آداپتور s3_ready باشد).
طراحی idempotent است: هر تعداد اجرای مجدد امن؛ فقط ردیف‌های storage='local'
پیمایش می‌شوند؛ نسخه محلی حذف نمی‌شود (تسویه = گام ۴ طرح ADR-04).
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
from app.services.storage_migration import migrate_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="مهاجرت idempotent فایل‌های local به S3/MinIO (گام ۲ طرح ADR-04)")
    parser.add_argument("--limit", type=int, default=200, help="سقف ردیف در هر دسته (پیش‌فرض ۲۰۰)")
    parser.add_argument("--dry-run", action="store_true", help="فقط شمارش؛ هیچ نوشتنی انجام نمی‌شود")
    parser.add_argument("--loop", action="store_true", help="تا اتمام ردیف‌های local تکرار کن (دسته‌دسته)")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="مکث بین دسته‌ها در حالت --loop")
    args = parser.parse_args()

    s = get_settings()
    if not objstore.s3_ready(s):
        print(
            "[خطا] آداپتور S3 آماده نیست — S3_ENDPOINT_URL/S3_BUCKET/S3_ACCESS_KEY/"
            "S3_SECRET_KEY را کامل کنید و boto3 را نصب کنید.",
            file=sys.stderr,
        )
        return 1

    total_scanned = total_migrated = total_would = total_missing = total_mismatch = total_errors = 0
    rounds = 0
    while True:
        rounds += 1
        db = SessionLocal()
        try:
            report = migrate_batch(db, s=s, limit=args.limit, dry_run=args.dry_run)
        finally:
            db.close()
        print(f"batch #{rounds}: {report.summary()}")
        for line in report.details:
            print(f"  {line}")
        total_scanned += report.scanned
        total_migrated += report.migrated
        total_would += report.would_migrate
        total_missing += report.skipped_missing
        total_mismatch += report.checksum_mismatch
        total_errors += report.errors
        if not args.loop or report.scanned < args.limit:
            break
        time.sleep(max(0.0, args.sleep_seconds))

    mode = "dry-run" if args.dry_run else "migrate"
    print(
        f"TOTAL [{mode}] rounds={rounds} scanned={total_scanned} migrated={total_migrated} "
        f"would_migrate={total_would} missing={total_missing} "
        f"checksum_mismatch={total_mismatch} errors={total_errors}"
    )
    if not args.dry_run:
        print("نسخه محلی فایل‌ها حفظ شد — تسویه volume محلی = گام ۴ طرح ADR-04 (پس از پایداری).")
    return 0 if total_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
