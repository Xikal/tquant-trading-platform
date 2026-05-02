#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ENV="${RUNTIME_ENV_PATH:-$ROOT_DIR/backend/data/runtime.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"

mkdir -p "$BACKUP_DIR"

read_database_url() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    printf '%s\n' "$DATABASE_URL"
    return
  fi
  if [[ -f "$RUNTIME_ENV" ]]; then
    grep -E '^DATABASE_URL=' "$RUNTIME_ENV" | tail -1 | cut -d= -f2- | sed 's/^"//;s/"$//'
    return
  fi
  printf 'sqlite:///./data/t_quant.db\n'
}

backup_sqlite() {
  local raw_path="$1"
  local db_path="$raw_path"
  if [[ "$db_path" != /* ]]; then
    db_path="$ROOT_DIR/backend/${db_path#./}"
  fi
  if [[ ! -f "$db_path" ]]; then
    echo "未找到 SQLite 数据库：$db_path" >&2
    exit 1
  fi
  local target="$BACKUP_DIR/t_quant-$TIMESTAMP.db"
  cp "$db_path" "$target"
  gzip -f "$target"
  echo "SQLite 备份完成：$target.gz"
}

backup_mysql() {
  local url="$1"
  if ! command -v mysqldump >/dev/null 2>&1; then
    echo "当前环境未安装 mysqldump，无法备份 MySQL。" >&2
    exit 1
  fi
  python3 - "$url" "$BACKUP_DIR/t_quant-$TIMESTAMP.sql.gz" <<'PY'
import gzip
import subprocess
import sys
from urllib.parse import urlparse, unquote

url = urlparse(sys.argv[1])
target = sys.argv[2]
database = url.path.lstrip("/")
cmd = [
    "mysqldump",
    "-h", url.hostname or "127.0.0.1",
    "-P", str(url.port or 3306),
    "-u", unquote(url.username or "root"),
]
if url.password:
    cmd.append(f"-p{unquote(url.password)}")
cmd.append(database)
with gzip.open(target, "wb") as output:
    subprocess.run(cmd, check=True, stdout=output)
print(f"MySQL 备份完成：{target}")
PY
}

DATABASE_URL_VALUE="$(read_database_url)"
case "$DATABASE_URL_VALUE" in
  sqlite:///*) backup_sqlite "${DATABASE_URL_VALUE#sqlite:///}" ;;
  sqlite:////*) backup_sqlite "/${DATABASE_URL_VALUE#sqlite:////}" ;;
  mysql*://*) backup_mysql "$DATABASE_URL_VALUE" ;;
  *) echo "暂不支持的 DATABASE_URL：$DATABASE_URL_VALUE" >&2; exit 1 ;;
esac

find "$BACKUP_DIR" -type f \( -name 't_quant-*.db.gz' -o -name 't_quant-*.sql.gz' \) -mtime +14 -delete
