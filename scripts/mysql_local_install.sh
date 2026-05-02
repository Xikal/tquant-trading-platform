#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE_PATH="$ROOT_DIR/.mysql-dist/mysql-8.4.8-macos15-arm64.tar"
INSTALL_ROOT="$ROOT_DIR/.mysql-local"
MYSQL_HOME="$INSTALL_ROOT/mysql-8.4.8"
DATA_DIR="$INSTALL_ROOT/data"
RUNTIME_DIR="$ROOT_DIR/.runtime/mysql"
PID_FILE="$RUNTIME_DIR/mysql.pid"
SOCKET_FILE="$RUNTIME_DIR/mysql.sock"
LOG_FILE="$RUNTIME_DIR/mysql.log"
APP_URL_FILE="$RUNTIME_DIR/mysql_app_url.txt"
APP_USER="tquant_app"

mkdir -p "$RUNTIME_DIR" "$INSTALL_ROOT"

if [[ ! -d "$MYSQL_HOME" ]]; then
  if [[ ! -f "$ARCHIVE_PATH" ]]; then
    echo "MySQL archive not found: $ARCHIVE_PATH" >&2
    exit 1
  fi
  TMP_DIR="$INSTALL_ROOT/tmp-extract"
  rm -rf "$TMP_DIR"
  mkdir -p "$TMP_DIR"
  tar -xf "$ARCHIVE_PATH" -C "$TMP_DIR"

  INNER_ARCHIVE="$(find "$TMP_DIR" -maxdepth 1 -type f -name 'mysql-*.tar.gz' ! -name 'mysql-test-*' ! -name 'mysql-router-*' | head -n 1)"
  if [[ -n "$INNER_ARCHIVE" ]]; then
    tar -xzf "$INNER_ARCHIVE" -C "$TMP_DIR"
  fi

  EXTRACTED_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name 'mysql-*' | head -n 1)"
  if [[ -z "$EXTRACTED_DIR" ]]; then
    echo "Unable to find extracted MySQL directory" >&2
    exit 1
  fi
  rm -rf "$MYSQL_HOME"
  mv "$EXTRACTED_DIR" "$MYSQL_HOME"
  rm -rf "$TMP_DIR"
fi

if [[ ! -d "$DATA_DIR/mysql" ]]; then
  rm -rf "$DATA_DIR"
  mkdir -p "$DATA_DIR"
  "$MYSQL_HOME/bin/mysqld" \
    --no-defaults \
    --basedir="$MYSQL_HOME" \
    --datadir="$DATA_DIR" \
    --initialize-insecure
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
  echo "MySQL already running with pid $(cat "$PID_FILE")"
else
  nohup "$MYSQL_HOME/bin/mysqld" \
    --no-defaults \
    --basedir="$MYSQL_HOME" \
    --datadir="$DATA_DIR" \
    --socket="$SOCKET_FILE" \
    --port=3306 \
    --bind-address=127.0.0.1 \
    --pid-file="$PID_FILE" \
    --log-error="$LOG_FILE" \
    > /dev/null 2>&1 &
fi

for _ in $(seq 1 60); do
  if "$MYSQL_HOME/bin/mysqladmin" --protocol=tcp -h127.0.0.1 -P3306 -uroot ping >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! "$MYSQL_HOME/bin/mysqladmin" --protocol=tcp -h127.0.0.1 -P3306 -uroot ping >/dev/null 2>&1; then
  echo "MySQL did not become ready. Check $LOG_FILE" >&2
  exit 1
fi

if [[ -f "$APP_URL_FILE" ]]; then
  APP_URL="$(cat "$APP_URL_FILE")"
  APP_PASSWORD="$(echo "$APP_URL" | sed -E 's#mysql\+pymysql://[^:]+:([^@]+)@.*#\1#')"
else
  APP_PASSWORD="$(python3 - <<'PY'
import secrets
import string

alphabet = string.ascii_letters + string.digits
print("".join(secrets.choice(alphabet) for _ in range(20)))
PY
)"
  "$MYSQL_HOME/bin/mysql" --protocol=tcp -h127.0.0.1 -P3306 -uroot <<SQL
CREATE DATABASE IF NOT EXISTS t_quant
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${APP_USER}'@'127.0.0.1' IDENTIFIED BY '${APP_PASSWORD}';
ALTER USER '${APP_USER}'@'127.0.0.1' IDENTIFIED BY '${APP_PASSWORD}';
GRANT ALL PRIVILEGES ON t_quant.* TO '${APP_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
  APP_URL="mysql+pymysql://${APP_USER}:${APP_PASSWORD}@127.0.0.1:3306/t_quant?charset=utf8mb4"
  echo "$APP_URL" > "$APP_URL_FILE"
fi

echo "mysql_pid=$(cat "$PID_FILE")"
echo "mysql_socket=$SOCKET_FILE"
echo "mysql_log=$LOG_FILE"
echo "mysql_app_url=$(cat "$APP_URL_FILE")"
