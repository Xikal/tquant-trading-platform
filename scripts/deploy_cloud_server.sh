#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/cloud_ssh_lib.sh"

CLOUD_HOST="${CLOUD_HOST:-}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_PROJECT_DIR="${CLOUD_PROJECT_DIR:-/home/ubuntu/gupiao-upload}"
CLOUD_COMPOSE_FILE="${CLOUD_COMPOSE_FILE:-docker-compose.mysql.yml}"
CLOUD_APP_PORT="${CLOUD_APP_PORT:-18090}"
CLOUD_KEEP_BACKUPS="${CLOUD_KEEP_BACKUPS:-3}"
AUTO_INITIAL_GIT_COMMIT="${AUTO_INITIAL_GIT_COMMIT:-1}"
AUTO_INSTALL_BACKUP_CRON="${AUTO_INSTALL_BACKUP_CRON:-1}"
AUTO_CONFIGURE_HTTPS="${AUTO_CONFIGURE_HTTPS:-1}"
HTTPS_REQUIRED="${HTTPS_REQUIRED:-1}"
CLOUD_DOMAIN="${CLOUD_DOMAIN:-}"
CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-}"
CLOUD_AUTH_COOKIE_SECURE="${CLOUD_AUTH_COOKIE_SECURE:-}"
CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="${CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE:-}"
BACKUP_TIME="${BACKUP_TIME:-02:20}"
RUN_COMPILE="${RUN_COMPILE:-1}"
RUN_FRONTEND_BUILD="${RUN_FRONTEND_BUILD:-1}"
RUN_STRATEGY_TEST="${RUN_STRATEGY_TEST:-1}"
RUN_FULL_TESTS="${RUN_FULL_TESTS:-0}"
RUN_LATEST_DATA_ACCEPTANCE="${RUN_LATEST_DATA_ACCEPTANCE:-1}"
LATEST_DATA_ACCEPTANCE_REQUIRED="${LATEST_DATA_ACCEPTANCE_REQUIRED:-0}"

log() {
  printf '[deploy] %s\n' "$*"
}

require_cloud_host() {
  if [[ -n "$CLOUD_HOST" ]]; then
    return 0
  fi
  log "CLOUD_HOST is required. Example: CLOUD_HOST=<server-ip-or-domain> $0"
  exit 2
}

require_https_config() {
  if [[ "$AUTO_CONFIGURE_HTTPS" != "1" ]]; then
    return 0
  fi
  if [[ -z "$CLOUD_DOMAIN" || -z "$CLOUD_CERT_EMAIL" ]]; then
    log "CLOUD_DOMAIN and CLOUD_CERT_EMAIL are required when AUTO_CONFIGURE_HTTPS=1"
    exit 2
  fi
}

run_local_checks() {
  if [[ "$AUTO_INITIAL_GIT_COMMIT" == "1" ]]; then
    log "ensure initial git commit"
    "$ROOT_DIR/scripts/ensure_initial_git_commit.sh"
  fi
  if [[ "$RUN_COMPILE" == "1" ]]; then
    log "compile backend"
    python3 -m compileall "$ROOT_DIR/backend/app" "$ROOT_DIR/backend/tests" "$ROOT_DIR/scripts" >/dev/null
  fi
  if [[ "$RUN_STRATEGY_TEST" == "1" ]]; then
    log "run strategy replacement tests"
    PYTHONPATH="$ROOT_DIR/backend" "$ROOT_DIR/backend/.venv/bin/python" -m unittest \
      backend/tests/test_low_buy_strategy_replacement.py
  fi
  if [[ "$RUN_FULL_TESTS" == "1" ]]; then
    log "run full backend tests"
    PYTHONPATH="$ROOT_DIR/backend" "$ROOT_DIR/backend/.venv/bin/python" -m unittest discover \
      -s "$ROOT_DIR/backend/tests" -p 'test_*.py'
  fi
  if [[ "$RUN_FRONTEND_BUILD" == "1" ]]; then
    log "build frontend"
    npm --prefix "$ROOT_DIR/frontend" run build
  fi
}

make_package() {
  local package_path
  package_path="$(mktemp "/tmp/gupiao-deploy-$(date +%Y%m%d%H%M%S)-XXXXXX")"
  log "create package $package_path"
  COPYFILE_DISABLE=1 tar \
    --no-xattrs \
    --exclude='.git' \
    --exclude='.codex' \
    --exclude='.continue' \
    --exclude='.understand-anything' \
    --exclude='.runtime' \
    --exclude='.mysql-dist' \
    --exclude='.mysql-local' \
    --exclude='artifacts' \
    --exclude='backups' \
    --exclude='./data' \
    --exclude='backend/.venv' \
    --exclude='backend/.env' \
    --exclude='backend/__pycache__' \
    --exclude='backend/.pytest_cache' \
    --exclude='backend/data/runtime.env' \
    --exclude='backend/data/*.db' \
    --exclude='backend/data/*.sqlite' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/dist' \
    --exclude='frontend/*.tsbuildinfo' \
    --exclude='rust/*/target' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.log' \
    --exclude='._*' \
    --exclude='.DS_Store' \
    -czf "$package_path" -C "$ROOT_DIR" .
  printf '%s\n' "$package_path"
}

remote_deploy() {
  local package_path="$1"
  local remote_package="/home/${CLOUD_USER}/$(basename "$package_path")"
  log "upload package to ${CLOUD_USER}@${CLOUD_HOST}:${remote_package}"
  cloud_scp_to "$package_path" "$remote_package"

  log "backup current release and rebuild app container"
  cloud_ssh env \
    CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" \
    CLOUD_COMPOSE_FILE="$CLOUD_COMPOSE_FILE" \
    CLOUD_USER="$CLOUD_USER" \
    CLOUD_KEEP_BACKUPS="$CLOUD_KEEP_BACKUPS" \
    CLOUD_AUTH_COOKIE_SECURE="${CLOUD_AUTH_COOKIE_SECURE:-}" \
    CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="${CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE:-}" \
REMOTE_PACKAGE="$remote_package" \
    HTTPS_REQUIRED="$HTTPS_REQUIRED" \
    bash -s <<'REMOTE'
set -euo pipefail
TS=$(date +%Y%m%d%H%M%S)
cd /home/$CLOUD_USER
rm -rf gupiao-upload-new
mkdir gupiao-upload-new
tar -xzf "$REMOTE_PACKAGE" -C gupiao-upload-new
if test -d "$CLOUD_PROJECT_DIR/.runtime"; then cp -a "$CLOUD_PROJECT_DIR/.runtime" gupiao-upload-new/.runtime || true; fi
if test -f "$CLOUD_PROJECT_DIR/.env"; then cp -a "$CLOUD_PROJECT_DIR/.env" gupiao-upload-new/.env || true; fi
PROJECT_PARENT=$(dirname "$CLOUD_PROJECT_DIR")
sudo mkdir -p "$PROJECT_PARENT"
if test -d "$CLOUD_PROJECT_DIR"; then
  sudo mv "$CLOUD_PROJECT_DIR" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS"
  sudo chown -R "$CLOUD_USER:$CLOUD_USER" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS" || true
fi
sudo mv gupiao-upload-new "$CLOUD_PROJECT_DIR"
sudo chown -R "$CLOUD_USER:$CLOUD_USER" "$CLOUD_PROJECT_DIR"
cd "$CLOUD_PROJECT_DIR"
touch .env
if ! grep -Eq '^AUTH_SECRET_KEY=.{64,}' .env; then
  sed -i '/^AUTH_SECRET_KEY=/d' .env
  SECRET=$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
  printf 'AUTH_SECRET_KEY=%s\n' "$SECRET" >> .env
fi
if ! grep -Eq '^TQUANT_SETTINGS_ENCRYPTION_KEY=.{64,}' .env; then
  sed -i '/^TQUANT_SETTINGS_ENCRYPTION_KEY=/d' .env
  SETTINGS_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
  printf 'TQUANT_SETTINGS_ENCRYPTION_KEY=%s\n' "$SETTINGS_SECRET" >> .env
fi
if ! grep -Eq '^TQUANT_INTERNAL_SERVICE_TOKEN=.{32,}' .env; then
  sed -i '/^TQUANT_INTERNAL_SERVICE_TOKEN=/d' .env
  INTERNAL_SERVICE_TOKEN=$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
  printf 'TQUANT_INTERNAL_SERVICE_TOKEN=%s\n' "$INTERNAL_SERVICE_TOKEN" >> .env
fi
AUTH_COOKIE_SECURE_VALUE="$CLOUD_AUTH_COOKIE_SECURE"
if test -z "$AUTH_COOKIE_SECURE_VALUE"; then
  AUTH_COOKIE_SECURE_VALUE=true
fi
if test "$(printf '%s' "$AUTH_COOKIE_SECURE_VALUE" | tr '[:upper:]' '[:lower:]')" != "true"; then
  echo "production cloud deployment requires AUTH_COOKIE_SECURE=true" >&2
  exit 2
fi
if test -n "$CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE" && test "$(printf '%s' "$CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE" | tr '[:upper:]' '[:lower:]')" != "false"; then
  echo "production cloud deployment requires AUTH_ALLOW_INSECURE_HTTP_COOKIE=false" >&2
  exit 2
fi
sed -i '/^AUTH_COOKIE_SECURE=/d' .env
printf 'AUTH_COOKIE_SECURE=%s\n' "$AUTH_COOKIE_SECURE_VALUE" >> .env
sed -i '/^AUTH_ALLOW_INSECURE_HTTP_COOKIE=/d' .env
printf 'AUTH_ALLOW_INSECURE_HTTP_COOKIE=false\n' >> .env
sed -i '/^HTTPS_REQUIRED=/d' .env
printf 'HTTPS_REQUIRED=%s\n' "$HTTPS_REQUIRED" >> .env
sed -i '/^WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=/d' .env
printf 'WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false\n' >> .env
sed -i '/^PAPER_AUTO_TRADING_ENABLED=/d' .env
printf 'PAPER_AUTO_TRADING_ENABLED=%s\n' "${PAPER_AUTO_TRADING_ENABLED:-false}" >> .env
sudo docker compose -f "$CLOUD_COMPOSE_FILE" build app analytics-worker
sudo docker compose -f "$CLOUD_COMPOSE_FILE" up --no-build --force-recreate --abort-on-container-exit --exit-code-from migration migration
sudo docker rm -f tquant-app-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql tquant-analytics-worker-mysql 2>/dev/null || true
sudo docker compose -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate app runtime-worker backtest-worker analytics-worker
EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
for container in tquant-app-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql; do
  ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
  if test "$ACTUAL_WEB_IMAGE" != "$EXPECTED_WEB_IMAGE"; then
    echo "$container is still running $ACTUAL_WEB_IMAGE; expected $EXPECTED_WEB_IMAGE" >&2
    exit 1
  fi
done
echo "web_image:updated"
EXPECTED_ANALYTICS_IMAGE=$(sudo docker image inspect tquant-analytics:mysql --format '{{.Id}}')
ACTUAL_ANALYTICS_IMAGE=$(sudo docker inspect tquant-analytics-worker-mysql --format '{{.Image}}')
if test "$ACTUAL_ANALYTICS_IMAGE" != "$EXPECTED_ANALYTICS_IMAGE"; then
  echo "tquant-analytics-worker-mysql is still running $ACTUAL_ANALYTICS_IMAGE; expected $EXPECTED_ANALYTICS_IMAGE" >&2
  exit 1
fi
for _ in $(seq 1 30); do
  ANALYTICS_STATUS=$(sudo docker inspect tquant-analytics-worker-mysql --format '{{.State.Health.Status}}' 2>/dev/null || echo none)
  echo "analytics-worker health:$ANALYTICS_STATUS"
  if test "$ANALYTICS_STATUS" = healthy; then
    break
  fi
  sleep 2
done
if test "$ANALYTICS_STATUS" != healthy; then
  echo "analytics-worker did not become healthy" >&2
  exit 1
fi
sudo docker exec tquant-analytics-worker-mysql python - <<'PY'
from app.core.database import ping_database
from app.services.analytics.dependencies import require_analytics_dependencies

require_analytics_dependencies()
ping_database()
print("analytics_worker_readyz:ok")
PY
sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data && chown -R tquant:tquant /app/backend/data' || true
python3 - <<'PY'
from pathlib import Path
from urllib.parse import quote

path = Path('.env')
text = path.read_text(encoding='utf-8')
values = {}
for line in text.splitlines():
    if line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    values[key.strip()] = value.strip()

dsn = values.get('MYSQL_DSN', '').strip()
if not dsn:
    user = values.get('MYSQL_USER', 'tquant_app').strip() or 'tquant_app'
    password = values.get('MYSQL_PASSWORD', '').strip()
    database = values.get('MYSQL_DATABASE', 't_quant').strip() or 't_quant'
    if password:
        dsn = f"mysql+mysqldb://{quote(user, safe='')}:{quote(password, safe='')}@mysql:3306/{quote(database, safe='')}?charset=utf8mb4"
        if not text.endswith('\n'):
            text += '\n'
        text += f"MYSQL_DSN={dsn}\n"
        path.write_text(text, encoding='utf-8')
        print('mysql_dsn:created')
PY
sudo docker compose -f "$CLOUD_COMPOSE_FILE" build go-bff-gateway go-market-read-service go-scan-worker
sudo docker compose -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate go-bff-gateway go-market-read-service go-scan-worker
EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
for container in tquant-app-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql; do
  ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
  if test "$ACTUAL_WEB_IMAGE" != "$EXPECTED_WEB_IMAGE"; then
    echo "$container changed away from web image after Go service deploy" >&2
    exit 1
  fi
done
sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data/ml_models && chown -R tquant:tquant /app/backend/data' || true
ls -dt /home/$CLOUD_USER/gupiao-deploy-backup-* 2>/dev/null | tail -n +$((CLOUD_KEEP_BACKUPS + 1)) | xargs -r sudo rm -rf
rm -f "$REMOTE_PACKAGE"
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
REMOTE
}

remote_configure_ops() {
  if [[ "$AUTO_INSTALL_BACKUP_CRON" == "1" ]]; then
    log "install remote database backup cron"
    cloud_ssh "set -euo pipefail
cd '$CLOUD_PROJECT_DIR'
BACKUP_TIME='$BACKUP_TIME' ./scripts/install_backup_cron.sh"
  fi

  if [[ "$AUTO_CONFIGURE_HTTPS" == "1" ]]; then
    log "configure remote HTTPS certificate"
    local https_cmd
    https_cmd="set -euo pipefail
cd '$CLOUD_PROJECT_DIR'
sudo DOMAIN='$CLOUD_DOMAIN' APP_PORT='$CLOUD_APP_PORT' EMAIL='$CLOUD_CERT_EMAIL' ./scripts/install_https_nginx.sh"
    if [[ "$HTTPS_REQUIRED" == "1" ]]; then
      cloud_ssh "$https_cmd"
    else
      cloud_ssh "$https_cmd" || log "warning: HTTPS 自动配置失败；部署继续，检查 DNS/80端口/证书限额后重试"
    fi
  else
    log "refresh remote nginx config when HTTPS site already exists"
    cloud_ssh "set -euo pipefail
cd '$CLOUD_PROJECT_DIR'
if test -n '$CLOUD_DOMAIN' -a -f /etc/nginx/sites-available/weisilianghua.conf; then
  sudo REQUIRE_EMAIL=0 DOMAIN='$CLOUD_DOMAIN' APP_PORT='$CLOUD_APP_PORT' ./scripts/install_https_nginx.sh
fi"
  fi
}

verify_remote() {
  log "wait for container health"
  cloud_ssh env CLOUD_APP_PORT="$CLOUD_APP_PORT" CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" bash -s <<'REMOTE'
set -euo pipefail
for _ in $(seq 1 40); do
  STATUS=$(sudo docker inspect tquant-app-mysql --format '{{.State.Health.Status}}' 2>/dev/null || echo none)
  echo "health:$STATUS"
  if test "$STATUS" = healthy; then break; fi
  sleep 3
done
curl -sS -f --max-time 10 "http://127.0.0.1:${CLOUD_APP_PORT}/readyz" >/tmp/gupiao_readyz.json
python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
assert payload.get('checks', {}).get('database') is True, payload
assert payload.get('checks', {}).get('frontend_dist') is True, payload
print('readyz:ok')
PY
AUTH_STATUS=$(curl -sS -o /tmp/gupiao_auth_guard.json -w '%{http_code}' --max-time 10 "http://127.0.0.1:${CLOUD_APP_PORT}/api/screeners/low-buy?limit=4&scan_limit=24")
test "$AUTH_STATUS" = 401
echo protected_api:ok
curl -sS -f -o /tmp/gupiao_home.html --max-time 10 "http://127.0.0.1:${CLOUD_APP_PORT}/"
grep -q '<div id="root"></div>' /tmp/gupiao_home.html
echo frontend:ok
cd "$CLOUD_PROJECT_DIR"
if test -f .env; then
  set -a
  . ./.env
  set +a
fi
if test -n "${MYSQL_ROOT_PASSWORD:-}"; then
  sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW VARIABLES WHERE Variable_name IN ('slow_query_log','long_query_time','innodb_buffer_pool_size');" >/tmp/gupiao_mysql_tuning.txt
  grep -q $'slow_query_log\tON' /tmp/gupiao_mysql_tuning.txt
  echo mysql_tuning:ok
else
  echo mysql_tuning:skipped_missing_password
fi
REMOTE
}

verify_go_remote() {
  log "verify go services"
  cloud_ssh bash -s <<'REMOTE'
set -euo pipefail
for name in tquant-go-bff-gateway tquant-go-market-read-service tquant-go-scan-worker; do
  for _ in $(seq 1 30); do
    STATUS=$(sudo docker inspect "$name" --format '{{.State.Health.Status}}' 2>/dev/null || echo none)
    echo "$name health:$STATUS"
    if test "$STATUS" = healthy; then
      break
    fi
    sleep 2
  done
done
sudo docker exec tquant-go-bff-gateway wget -qO- http://127.0.0.1:8091/readyz >/tmp/go_bff_readyz.json
sudo docker exec tquant-go-market-read-service wget -qO- http://127.0.0.1:8092/readyz >/tmp/go_market_readyz.json
sudo docker exec tquant-go-scan-worker wget -qO- http://127.0.0.1:8093/readyz >/tmp/go_scan_readyz.json
python3 - <<'PY'
import json
for path in ['/tmp/go_bff_readyz.json', '/tmp/go_market_readyz.json', '/tmp/go_scan_readyz.json']:
    payload = json.load(open(path, encoding='utf-8'))
    assert payload.get('ok') is True or payload.get('status') == 'ok', payload
print('go_services:ok')
PY
REMOTE
}

verify_latest_data_remote() {
  if [[ "$RUN_LATEST_DATA_ACCEPTANCE" != "1" ]]; then
    return 0
  fi
  log "verify latest low-buy data closure"
  local remote_cmd
  remote_cmd="set -euo pipefail
cd '$CLOUD_PROJECT_DIR'
sudo docker exec tquant-app-mysql python scripts/latest_data_acceptance.py --publish-if-ready --repair --enqueue-missing --notify-on-fail"
  if [[ "$LATEST_DATA_ACCEPTANCE_REQUIRED" == "1" ]]; then
    cloud_ssh "$remote_cmd"
  else
    cloud_ssh "$remote_cmd" || log "warning: 最新数据闭环验收未通过；已尝试入队刷新并发送告警，部署继续"
  fi
}

main() {
  require_cloud_host
  require_https_config
  run_local_checks
  local package_path
  package_path="$(make_package | tail -n 1)"
  remote_deploy "$package_path"
  remote_configure_ops
  verify_remote
  verify_go_remote
  verify_latest_data_remote
  rm -f "$package_path"
  log "done: http://${CLOUD_HOST}:${CLOUD_APP_PORT} / https://${CLOUD_DOMAIN}"
}

main "$@"
