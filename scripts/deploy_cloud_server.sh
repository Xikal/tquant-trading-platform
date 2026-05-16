#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/cloud_ssh_lib.sh"

CLOUD_HOST="${CLOUD_HOST:-43.143.243.97}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_PROJECT_DIR="${CLOUD_PROJECT_DIR:-/home/ubuntu/gupiao-upload}"
CLOUD_COMPOSE_FILE="${CLOUD_COMPOSE_FILE:-docker-compose.mysql.yml}"
CLOUD_APP_PORT="${CLOUD_APP_PORT:-18090}"
CLOUD_KEEP_BACKUPS="${CLOUD_KEEP_BACKUPS:-3}"
AUTO_INITIAL_GIT_COMMIT="${AUTO_INITIAL_GIT_COMMIT:-1}"
AUTO_INSTALL_BACKUP_CRON="${AUTO_INSTALL_BACKUP_CRON:-1}"
AUTO_CONFIGURE_HTTPS="${AUTO_CONFIGURE_HTTPS:-1}"
HTTPS_REQUIRED="${HTTPS_REQUIRED:-0}"
CLOUD_DOMAIN="${CLOUD_DOMAIN:-weisilianghua.cloud}"
CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-admin@${CLOUD_DOMAIN}}"
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
    --exclude='.runtime' \
    --exclude='.mysql-dist' \
    --exclude='.mysql-local' \
    --exclude='artifacts' \
    --exclude='backups' \
    --exclude='data' \
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
  cloud_ssh "set -euo pipefail
TS=\$(date +%Y%m%d%H%M%S)
cd /home/${CLOUD_USER}
rm -rf gupiao-upload-new
mkdir gupiao-upload-new
tar -xzf '$remote_package' -C gupiao-upload-new
if test -d '$CLOUD_PROJECT_DIR/.runtime'; then cp -a '$CLOUD_PROJECT_DIR/.runtime' gupiao-upload-new/.runtime || true; fi
if test -f '$CLOUD_PROJECT_DIR/.env'; then cp -a '$CLOUD_PROJECT_DIR/.env' gupiao-upload-new/.env || true; fi
PROJECT_PARENT=\$(dirname '$CLOUD_PROJECT_DIR')
sudo mkdir -p \"\$PROJECT_PARENT\"
if test -d '$CLOUD_PROJECT_DIR'; then
  sudo mv '$CLOUD_PROJECT_DIR' '/home/${CLOUD_USER}/gupiao-deploy-backup-'\$TS
  sudo chown -R '${CLOUD_USER}:${CLOUD_USER}' '/home/${CLOUD_USER}/gupiao-deploy-backup-'\$TS || true
fi
sudo mv gupiao-upload-new '$CLOUD_PROJECT_DIR'
sudo chown -R '${CLOUD_USER}:${CLOUD_USER}' '$CLOUD_PROJECT_DIR'
cd '$CLOUD_PROJECT_DIR'
touch .env
if ! grep -Eq '^AUTH_SECRET_KEY=.{16,}' .env; then
  sed -i '/^AUTH_SECRET_KEY=/d' .env
  SECRET=\$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
  printf 'AUTH_SECRET_KEY=%s\n' \"\$SECRET\" >> .env
fi
if ! grep -q '^AUTH_COOKIE_SECURE=' .env; then printf 'AUTH_COOKIE_SECURE=true\n' >> .env; fi
sudo docker compose -f '$CLOUD_COMPOSE_FILE' up --build --force-recreate --abort-on-container-exit --exit-code-from migration migration
sudo docker compose -f '$CLOUD_COMPOSE_FILE' run --rm --user root --entrypoint sh app -c 'mkdir -p /app/backend/data && chown -R tquant:tquant /app/backend/data'
sudo docker compose -f '$CLOUD_COMPOSE_FILE' up -d --build app runtime-worker backtest-worker
sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data/ml_models && chown -R tquant:tquant /app/backend/data' || true
ls -dt /home/${CLOUD_USER}/gupiao-deploy-backup-* 2>/dev/null | tail -n +$((CLOUD_KEEP_BACKUPS + 1)) | xargs -r sudo rm -rf
rm -f '$remote_package'
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
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
  fi
}

verify_remote() {
  log "wait for container health"
  cloud_ssh "set -euo pipefail
for _ in \$(seq 1 40); do
  STATUS=\$(sudo docker inspect tquant-app-mysql --format '{{.State.Health.Status}}' 2>/dev/null || echo none)
  echo health:\$STATUS
  if test \"\$STATUS\" = healthy; then break; fi
  sleep 3
done
curl -sS -f --max-time 10 http://127.0.0.1:${CLOUD_APP_PORT}/readyz >/tmp/gupiao_readyz.json
python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
assert payload.get('checks', {}).get('database') is True, payload
assert payload.get('checks', {}).get('frontend_dist') is True, payload
print('readyz:ok')
PY
AUTH_STATUS=\$(curl -sS -o /tmp/gupiao_auth_guard.json -w '%{http_code}' --max-time 10 'http://127.0.0.1:${CLOUD_APP_PORT}/api/screeners/low-buy?limit=4&scan_limit=24')
test \"\$AUTH_STATUS\" = 401
echo protected_api:ok
curl -sS -f -o /tmp/gupiao_home.html --max-time 10 http://127.0.0.1:${CLOUD_APP_PORT}/
grep -q '<div id=\"root\"></div>' /tmp/gupiao_home.html
echo frontend:ok"
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
  run_local_checks
  local package_path
  package_path="$(make_package | tail -n 1)"
  remote_deploy "$package_path"
  remote_configure_ops
  verify_remote
  verify_latest_data_remote
  rm -f "$package_path"
  log "done: http://${CLOUD_HOST}:${CLOUD_APP_PORT} / https://${CLOUD_DOMAIN}"
}

main "$@"
