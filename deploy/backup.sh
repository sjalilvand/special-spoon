#!/bin/sh
# Rosepsy backup (بند ۱۳ سند) - اجرا: docker compose --profile ops run --rm backup
set -eu

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT="/backups/rosepsy_db_${TIMESTAMP}.dump"

mkdir -p /backups
pg_dump -h db -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -f "${OUT}"
echo "[backup] OK -> ${OUT}"
# یادآوری بند ۱۳.۱ سند: این پشتیبان باید به مقصد جدا از سرور اصلی منتقل شود.
