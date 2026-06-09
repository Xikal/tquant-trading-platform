#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ENV="${RUNTIME_ENV_PATH:-$ROOT_DIR/backend/data/runtime.env}"
ROOT_ENV="${ROOT_ENV_PATH:-$ROOT_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"

mkdir -p "$BACKUP_DIR"

read_database_url() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    printf '%s\n' "$DATABASE_URL"
    return
  fi
  if [[ -n "${MYSQL_DSN:-}" ]]; then
    printf '%s\n' "$MYSQL_DSN"
    return
  fi
  if [[ -f "$RUNTIME_ENV" ]]; then
    local runtime_url
    runtime_url="$(grep -E '^(DATABASE_URL|MYSQL_DSN)=' "$RUNTIME_ENV" | tail -1 | cut -d= -f2- | sed 's/^"//;s/"$//')" || true
    if [[ -n "$runtime_url" ]]; then
      printf '%s\n' "$runtime_url"
      return
    fi
  fi
  if [[ -f "$ROOT_ENV" ]]; then
    local root_url
    root_url="$(grep -E '^(DATABASE_URL|MYSQL_DSN)=' "$ROOT_ENV" | tail -1 | cut -d= -f2- | sed 's/^"//;s/"$//')" || true
    if [[ -n "$root_url" ]]; then
      printf '%s\n' "$root_url"
      return
    fi
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
  local docker_runner
  if docker_runner="$(mysql_compose_runner)"; then
    backup_mysql_with_compose "$url" "$docker_runner"
    return
  fi
  if command -v mysqldump >/dev/null 2>&1; then
    backup_mysql_with_command mysqldump "$url"
    return
  fi
  if command -v mariadb-dump >/dev/null 2>&1; then
    backup_mysql_with_command mariadb-dump "$url"
    return
  fi
  echo "当前环境未安装 mysqldump/mariadb-dump，且未发现可用 MySQL 容器，无法备份 MySQL。" >&2
  exit 1
}

mysql_compose_runner() {
  if command -v docker >/dev/null 2>&1 && docker compose -f "$ROOT_DIR/docker-compose.mysql.yml" ps mysql >/dev/null 2>&1; then
    printf 'docker\n'
    return 0
  fi
  if command -v sudo >/dev/null 2>&1 && sudo -n docker compose -f "$ROOT_DIR/docker-compose.mysql.yml" ps mysql >/dev/null 2>&1; then
    printf 'sudo docker\n'
    return 0
  fi
  return 1
}

backup_mysql_with_command() {
  local dump_command="$1"
  local url="$2"
  python3 - "$url" "$BACKUP_DIR/t_quant-$TIMESTAMP.sql.gz" "$dump_command" <<'PY'
import gzip
import subprocess
import sys
from urllib.parse import urlparse, unquote

url = urlparse(sys.argv[1])
target = sys.argv[2]
dump_command = sys.argv[3]
database = url.path.lstrip("/")
cmd = [
    dump_command,
    "--no-tablespaces",
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

backup_mysql_with_compose() {
  local url="$1"
  local docker_runner="$2"
  python3 - "$url" "$BACKUP_DIR/t_quant-$TIMESTAMP.sql.gz" "$ROOT_DIR/docker-compose.mysql.yml" "$docker_runner" <<'PY'
import gzip
import shlex
import subprocess
import sys
from urllib.parse import urlparse, unquote

url = urlparse(sys.argv[1])
target = sys.argv[2]
compose_file = sys.argv[3]
docker_runner = shlex.split(sys.argv[4])
database = url.path.lstrip("/")
user = unquote(url.username or "root")
password = unquote(url.password or "")
if not database:
    print("MySQL DSN 缺少数据库名，无法备份。", file=sys.stderr)
    sys.exit(1)
dump_script = "command -v mysqldump >/dev/null 2>&1 && exec mysqldump \"$@\" || exec mariadb-dump \"$@\""
cmd = [
    *docker_runner,
    "compose",
    "-f",
    compose_file,
    "exec",
    "-T",
    "mysql",
    "sh",
    "-lc",
    dump_script,
    "dump",
    "--no-tablespaces",
    "-h",
    "127.0.0.1",
    "-P",
    str(url.port or 3306),
    "-u",
    user,
]
if password:
    cmd.append(f"-p{password}")
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
