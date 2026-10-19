"""فاز ۳۸ - گام ۲ طرح مهاجرت ADR-04: انتقال idempotent فایل‌های local به S3/MinIO.

منطق مطابق طرح مصوب سند:
- فقط ردیف‌های ``files.storage='local'`` پیمایش می‌شود → اجرای مجدد امن است
  (ادامه از همان‌جا؛ ردیف‌های منتقل‌شده دیگر در پیمایش نمی‌آیند)؛
- بایت‌ها از دایرکتوری محلی خوانده می‌شود؛ فایل ناموجود → skip با گزارش شفاف
  (هرگز روی داده ناقص تصمیم نمی‌گیریم)؛
- ``put_object`` با همان ``storage_key``؛ سپس خواندن مجدد از S3 و مقایسه
  sha256 با checksum ردیف (راستی‌آزمایی مطابق طرح)؛
- فقط بعد از راستی‌آزمایی، ``files.storage='s3'`` ثبت می‌شود — دانلود از
  پروایدر ردیف می‌خواند پس هیچ لحظه‌ای فایل از دسترس خارج نمی‌شود؛
- نسخه محلی حذف نمی‌شود (تسویه volume = گام ۴ طرح؛ تصمیم دستی پس از پایداری).
  نتیجه: rollback = تنظیم ``files.storage='local'`` بدون هیچ حرکت داده؛
- سقف ردیف در هر اجرا (``limit``) برای اجرای مرحله‌ای بدون فشار روی سرویس.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.file import StoredFile
from app.services import file_storage as fs
from app.services import object_storage as objstore


@dataclass
class MigrationReport:
    """گزارش شفاف اجرا — خروجی CLI و آزمون‌ها."""

    scanned: int = 0
    migrated: int = 0
    would_migrate: int = 0
    skipped_missing: int = 0
    checksum_mismatch: int = 0
    errors: int = 0
    dry_run: bool = False
    details: list[str] = field(default_factory=list)

    def summary(self) -> str:
        mode = "dry-run" if self.dry_run else "migrate"
        return (
            f"[{mode}] scanned={self.scanned} migrated={self.migrated} "
            f"would_migrate={self.would_migrate} missing={self.skipped_missing} "
            f"checksum_mismatch={self.checksum_mismatch} errors={self.errors}"
        )


def migrate_batch(
    db: Session,
    s: Settings | None = None,
    limit: int = 200,
    dry_run: bool = False,
) -> MigrationReport:
    """یک دسته (batch) فایل محلی را به S3 منتقل می‌کند؛ خروجی: MigrationReport.

    در dry-run هیچ نوشتنی انجام نمی‌شود (نه S3 و نه DB) — فقط شمارش.
    خطای S3 در ردیفی → skip همان ردیف با ثبت خطا؛ ادامه بقیه (fail-soft).
    """
    s = s or get_settings()
    report = MigrationReport(dry_run=dry_run)

    if not objstore.s3_ready(s):
        raise RuntimeError(
            "آداپتور S3 آماده نیست: S3_ENDPOINT_URL/S3_BUCKET/S3_ACCESS_KEY/"
            "S3_SECRET_KEY کامل نیست یا boto3 نصب نیست (migrate بدون مهاجرت الکی ممنوع)"
        )

    rows = (
        db.execute(
            select(StoredFile)
            .where(StoredFile.storage == "local")
            .order_by(StoredFile.created_at, StoredFile.id)
            .limit(max(1, int(limit)))
        )
        .scalars()
        .all()
    )

    changed = False
    for row in rows:
        report.scanned += 1
        tag = f"file={row.storage_key}"

        # ۱) خواندن محلی — ناموجود → skip (برای گام ۴/تسویه دستی گزارش می‌ماند)
        path = fs.storage_path(s.upload_dir, row.storage_key)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except FileNotFoundError:
            report.skipped_missing += 1
            report.details.append(f"SKIP missing-local {tag}")
            continue
        except OSError as exc:
            report.errors += 1
            report.details.append(f"ERROR read-local {tag}: {exc.__class__.__name__}")
            continue

        # ۲) صحت داده محلی قبل از هر حرکت — ناسازگار → دستی بررسی شود
        sha = hashlib.sha256(data).hexdigest()
        if row.sha256 and sha != row.sha256:
            report.checksum_mismatch += 1
            report.details.append(f"SKIP checksum-mismatch {tag}")
            continue

        if dry_run:
            report.would_migrate += 1
            continue

        # ۳) put با همان کلید + راستی‌آزمایی با خواندن مجدد از S3
        try:
            objstore._s3_put(s, row.storage_key, data)
            readback = objstore._s3_get(s, row.storage_key)
        except Exception as exc:  # noqa: BLE001 - خطای خود سرویس S3
            report.errors += 1
            report.details.append(
                f"ERROR s3 {tag}: {exc.__class__.__name__} (فایل محلی دست‌نخورده ماند)"
            )
            continue
        if hashlib.sha256(readback).hexdigest() != row.sha256:
            report.errors += 1
            report.details.append(f"ERROR s3-verify {tag} (فایل محلی دست‌نخورده ماند)")
            continue

        # ۴) فقط پس از راستی‌آزمایی — پروایدر ردیف عوض می‌شود (دانلود بلافاصله از s3)
        row.storage = "s3"
        db.add(row)
        changed = True
        report.migrated += 1
        report.details.append(f"OK migrated {tag}")

    if changed and not dry_run:
        db.commit()
    return report
