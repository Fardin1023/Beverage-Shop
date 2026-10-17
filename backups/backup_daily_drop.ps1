# =============================================================================
# Automated Daily Logical Backup for Daily Drop Beverage Shop (PowerShell)
# =============================================================================
$ErrorActionPreference = "Stop"

$BackupDir = Join-Path $PSScriptRoot "backups_archive"
if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$DateStr = Get-Date -Format "yyyy-MM-dd"
$BackupFile = Join-Path $BackupDir "daily_drop_$DateStr.sql"

$MysqldumpPath = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
if (!(Test-Path $MysqldumpPath)) {
    $MysqldumpPath = "mysqldump"
}

Write-Host "Executing consistent transactional logical backup to $BackupFile..."
& $MysqldumpPath -u company_admin -pCompanyAdmin2026! --single-transaction --quick --routines --triggers daily_drop_db > $BackupFile

Write-Host "Backup completed successfully at $BackupFile"
