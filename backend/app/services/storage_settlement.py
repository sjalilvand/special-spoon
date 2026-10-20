"""فاز ۴۱ - گام ۴ طرح مهاجرت ADR-04: تسویه volume محلی.

طرح مصوب سند: «پس از پایداری، volume محلی فقط خواندنی و سپس حذف؛ local فقط
برای توسعه/آزمون.» با سوییچ فاز ۴۰ (STORAGE_BACKEND=s3) فایل‌های جدید به S3
می‌روند و اسکریپت گام ۲ فایل‌های قدیمی را منتقل کرده بود — اما «نسخه محلیِ»
فایل‌های منتقل‌شده عمداً حفظ شده بود (rollback بدون حرکت داده). این ماژول
تسویه نهایی را با سپر ایمنی عملیاتی می‌کند:

۱) **مهاجرت باقی‌مانده‌ها:** ردیف‌های ``files.storage='local'`` با همان منطق
   idempotent گام ۲ (``storage_migration.migrate_batch``) منتقل می‌شوند؛
۲) **پاک‌سازی نسخه‌های محلیِ ردیف‌های s3:** برای هر ردیف ``storage='s3'`` که
   هنوز بایت محلی دارد، ابتدا محتوا با «خواندن مجدد از S3» و مقایسه sha256 با
   checksum ردیف راستی‌آزمایی می‌شود — **حذف بدون اطمینان ممنوع است**:
   * خطای خواندن S3 → نسخه محلی حفظ (fail-soft، گزارش شفاف)؛
   * ناسازگاری checksum یا نبود checksum در ردیف → حذف نمی‌شود (بررسی دستی)؛
   * حذف فیزیکی فقط با ``enforce=True`` — بدون آن فقط گزارش WOULD-CLEAN؛
   * ``dry_run`` هیچ نوشتنی (نه S3، نه DB، نه دیسک) انجام نمی‌دهد.

نتیجه موفق: volume محلی خالی/کم‌حجم می‌شود و نقش آن به «سپر fallback فاز ۴۰
+ خواندن rollback ردیف‌های جامانده» محدود می‌ماند؛ تصمیم «فقط-خواندنی/حذف
کامل volume در compose» دستی و پس از گزارش پاک، مطابق سند است.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.file import StoredFile
from app.services import file_storage as fs
from app.services import object_storage as objstore
from app.services.storage_migration import migrate_batch


@dataclass
class SettlementReport:
    """گزارش شفاف تسویه — خروجی CLI و آزمون‌ها."""

    # فاز مهاجرت (منطق گام ۲ — ردیف‌های باقی‌مانده local)
    scanned: int = 0
    migrated: int = 0
    would_migrate: int = 0
    skipped_missing: int = 0
    checksum_mismatch: int = 0
    # فاز پاک‌سازی (ردیف‌های s3 که هنوز نسخه محلی دارند)
    leftover_scanned: int = 0
    cleaned: int = 0
    would_clean: int = 0
    verify_failed: int = 0
    bytes_freed: int = 0
    # مشترک
    errors: int = 0
    dry_run: bool = False
    enforce: bool = False
    details: list[str] = field(default_factory=list)

    def summary(self) -> str:
        mode = "dry-run" if self.dry_run else ("settle+clean" if self.enforce else "settle")
        return (
            f"[{mode}] migrated={self.migrated} would_migrate={self.would_migrate} "
            f"missing={self.skipped_missing} checksum_mismatch={self.checksum_mismatch} | "
            f"leftover={self.leftover_scanned} cleaned={self.cleaned} "
            f"would_clean={self.would_clean} verify_failed={self.verify_failed} "
            f"bytes_freed={self.bytes_freed} errors={self.errors}"
        )


def settle_batch(
    db: Session,
    s: Settings | None = None,
    limit: int = 200,
    dry_run: bool = False,
    enforce: bool = False,
) -> SettlementReport:
    """یک دسته تسویه: مهاجرت باقی‌مانده‌های local + پاک‌سازی نسخه‌های محلی s3.

    - ``enforce=False`` (پیش‌فرض): فقط مهاجرت + گزارش؛ هیچ بایت محلی حذف نمی‌شود؛
    - ``enforce=True``: پس از راستی‌آزمایی S3، نسخه محلی ردیف‌های s3 حذف می‌شود؛
    - ``dry_run=True``: فقط شمارش/گزارش — هیچ نوشتنی انجام نمی‌شود؛
    - اجرای مجدد هر تعداد بار امن است (idempotent).
    """
    s = s or get_settings()
    report = SettlementReport(dry_run=dry_run, enforce=enforce)

    if not objstore.s3_ready(s):
        raise RuntimeError(
            "آداپتور S3 آماده نیست: S3_ENDPOINT_URL/S3_BUCKET/S3_ACCESS_KEY/"
            "S3_SECRET_KEY کامل نیست یا boto3 نصب نیست (تسویه بدون راستی‌آزمایی ممنوع)"
        )

    # ------------------------------------------------ ۱) مهاجرت باقی‌مانده‌ها
    mig = migrate_batch(db, s=s, limit=limit, dry_run=dry_run)
    report.scanned = mig.scanned
    report.migrated = mig.migrated
    report.would_migrate = mig.would_migrate
    report.skipped_missing = mig.skipped_missing
    report.checksum_mismatch = mig.checksum_mismatch
    report.errors += mig.errors
    report.details.extend(mig.details)

    # --------------------------------- ۲) پاک‌سازی نسخه محلیِ ردیف‌های s3
    rows = (
        db.execute(
            select(StoredFile)
            .where(StoredFile.storage == "s3")
            .order_by(StoredFile.created_at, StoredFile.id)
            .limit(max(1, int(limit)))
        )
        .scalars()
        .all()
    )

    for row in rows:
        path = fs.storage_path(s.upload_dir, row.storage_key)
        if not os.path.exists(path):
            continue  # عادی‌ترین حالت: قبلاً تسویه شده یا هرگز محلی نبوده
        report.leftover_scanned += 1
        tag = f"file={row.storage_key}"

        # راستی‌آزمایی پیش از هر حذفی — خواندن مجدد از S3 و مقایسه checksum
        try:
            readback = objstore._s3_get(s, row.storage_key)
        except Exception as exc:  # noqa: BLE001 - خطای خود سرویس S3
            report.errors += 1
            report.details.append(
                f"ERROR s3-read {tag}: {exc.__class__.__name__} (نسخه محلی حفظ شد)"
            )
            continue
        if not row.sha256:
            report.verify_failed += 1
            report.details.append(f"SKIP no-checksum {tag} (حذف بدون ملاک ممنوع)")
            continue
        if hashlib.sha256(readback).hexdigest() != row.sha256:
            report.verify_failed += 1
            report.details.append(f"SKIP s3-verify-mismatch {tag} (نسخه محلی حفظ شد)")
            continue

        size = os.path.getsize(path)
        if dry_run or not enforce:
            report.would_clean += 1
            report.details.append(f"WOULD-CLEAN {tag} ({size} bytes)")
            continue

        try:
            fs.remove_file(s.upload_dir, row.storage_key)
        except OSError as exc:
            report.errors += 1
            report.details.append(f"ERROR remove-local {tag}: {exc.__class__.__name__}")
            continue
        report.cleaned += 1
        report.bytes_freed += size
        report.details.append(f"OK cleaned {tag} ({size} bytes freed)")

    return report
