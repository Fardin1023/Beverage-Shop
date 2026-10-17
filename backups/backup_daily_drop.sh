#!/bin/bash
# =============================================================================
# Automated Daily Logical Backup for Daily Drop Beverage Shop
# =============================================================================
set -e

BACKUP_DIR="${BACKUP_DIR:-/backups}"
mkdir -p "$BACKUP_DIR"

DATE_STR=$(date +%F)
BACKUP_FILE="${BACKUP_DIR}/daily_drop_${DATE_STR}.sql"

echo "Executing consistent transactional logical backup..."
mysqldump -u company_admin -pCompanyAdmin2026! \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  daily_drop_db > "$BACKUP_FILE"

echo "Backup completed successfully: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
