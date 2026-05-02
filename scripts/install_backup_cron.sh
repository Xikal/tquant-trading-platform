#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_TIME="${BACKUP_TIME:-02:20}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
LOG_FILE="${LOG_FILE:-$ROOT_DIR/.runtime/backup_database.log}"

mkdir -p "$(dirname "$LOG_FILE")" "$BACKUP_DIR"

hour="${BACKUP_TIME%%:*}"
minute="${BACKUP_TIME##*:}"
if ! [[ "$hour" =~ ^[0-9]{1,2}$ && "$minute" =~ ^[0-9]{1,2}$ ]]; then
  echo "BACKUP_TIME 必须是 HH:MM，例如 02:20" >&2
  exit 1
fi

cron_line="$minute $hour * * * BACKUP_DIR=\"$BACKUP_DIR\" \"$ROOT_DIR/scripts/backup_database.sh\" >> \"$LOG_FILE\" 2>&1"
marker="# tquant database backup"

tmp_file="$(mktemp)"
crontab -l 2>/dev/null | grep -v "$marker" | grep -v "backup_database.sh" > "$tmp_file" || true
{
  cat "$tmp_file"
  echo "$marker"
  echo "$cron_line"
} | crontab -
rm -f "$tmp_file"

echo "数据库备份 cron 已安装：每天 $BACKUP_TIME，备份目录 $BACKUP_DIR"
