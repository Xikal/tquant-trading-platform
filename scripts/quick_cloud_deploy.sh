#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/cloud_ssh_lib.sh"

CLOUD_HOST="${CLOUD_HOST:-}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_SSH_KEY="${CLOUD_SSH_KEY:-}"
CLOUD_PROJECT_DIR="${CLOUD_PROJECT_DIR:-/home/ubuntu/gupiao-upload}"
CLOUD_APP_PORT="${CLOUD_APP_PORT:-18090}"
CLOUD_DOMAIN="${CLOUD_DOMAIN:-}"
CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-}"
CLOUD_SSH_TIMEOUT="${CLOUD_SSH_TIMEOUT:-2400}"
CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-15}"
CLOUD_SSH_SERVER_ALIVE_COUNT_MAX="${CLOUD_SSH_SERVER_ALIVE_COUNT_MAX:-120}"

FAST_MODE=0
FAST_RISK_ACCEPTED=0
VERIFY_ONLY=0
RUN_LOCAL_CHECKS=1
RUN_FRONTEND_BUILD=1
RUN_FULL_TESTS=0
RUN_STRATEGY_TEST=1
RUN_LATEST_DATA_ACCEPTANCE=0
RUN_PERFORMANCE_VERIFY=0
RUN_PERFORMANCE_VERIFY_ROUNDS="${RUN_PERFORMANCE_VERIFY_ROUNDS:-2}"
RUN_PERFORMANCE_VERIFY_SAMPLES="${RUN_PERFORMANCE_VERIFY_SAMPLES:-8}"
AUTO_INITIAL_GIT_COMMIT=0
AUTO_INSTALL_BACKUP_CRON=0
AUTO_CONFIGURE_HTTPS=0
REFRESH_HTTPS_CONFIG=0
HTTPS_REQUIRED=1
CLOUD_AUTH_COOKIE_SECURE=true
CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE=false
VERIFY_PUBLIC_DOMAIN="${VERIFY_PUBLIC_DOMAIN:-0}"
DEPLOY_TARGET_SCOPE="${DEPLOY_TARGET_SCOPE:-auto}"
DEPLOY_FRONTEND_HOT_REQUIRED="${DEPLOY_FRONTEND_HOT_REQUIRED:-0}"
VERIFY_WEB_IMAGE_SYNC=1

log() {
  printf '[quick-deploy] %s\n' "$*"
}

print_deploy_summary() {
  local outcome="$1"
  local mode="safe"
  if [[ "$FAST_MODE" == "1" ]]; then
    mode="fast-risk-accepted"
  elif [[ "$RUN_FULL_TESTS" == "1" ]]; then
    mode="full"
  fi
  log "summary outcome=${outcome} mode=${mode} scope=${DEPLOY_TARGET_SCOPE} target=${CLOUD_USER}@${CLOUD_HOST} port=${CLOUD_APP_PORT} domain=${CLOUD_DOMAIN:-none} https_required=${HTTPS_REQUIRED} public_domain_verify=${VERIFY_PUBLIC_DOMAIN} performance_verify=${RUN_PERFORMANCE_VERIFY}"
  if [[ -n "$CLOUD_DOMAIN" ]]; then
    log "summary urls http=http://${CLOUD_HOST}:${CLOUD_APP_PORT} https=https://${CLOUD_DOMAIN}"
  else
    log "summary urls http=http://${CLOUD_HOST}:${CLOUD_APP_PORT}"
  fi
}

usage() {
  cat <<'EOF'
Usage: scripts/quick_cloud_deploy.sh [options]

Defaults:
  host   required via CLOUD_HOST or --host
  user   ubuntu
  key    required via CLOUD_SSH_KEY or --key
  port   18090

Options:
  --verify-only   Skip deploy and only verify the current remote state.
  --full          Run the slower local checks and latest-data acceptance.
  --fast-risk-accepted
                 Skip local compile/build checks for emergency deploys only.
  --scope <auto|all|frontend-hot|go|ops>
                 Choose deployment target. auto is the default and uses changed files.
  --frontend-hot-required
                 Fail instead of falling back when frontend-hot has no dist artifact.
  --performance-verify
                 Run online Go/Rust performance gates after deploy/verify.
                 Defaults to 2 rounds with 8 samples per round.
  --performance-rounds <n>
                 Override online performance validation rounds.
  --performance-samples <n>
                 Override samples per online performance validation round.
  --public-domain-verify
                 Fail when the public HTTPS domain cannot be reached.
  --configure-https
                 Request or renew certificates and install nginx config.
  --refresh-https-config
                 Refresh existing nginx config without requesting certificates.
  --install-backup-cron
                 Install or refresh the remote database backup cron.
  --host <host>   Override cloud host.
  --user <user>   Override cloud ssh user.
  --key <path>    Override ssh private key path.
  --project-dir <path>
  --port <port>
  --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify-only)
      VERIFY_ONLY=1
      shift
      ;;
    --full)
      FAST_MODE=0
      RUN_LOCAL_CHECKS=1
      RUN_FRONTEND_BUILD=1
      RUN_FULL_TESTS=1
      RUN_STRATEGY_TEST=1
      RUN_LATEST_DATA_ACCEPTANCE=1
      shift
      ;;
    --fast-risk-accepted)
      FAST_MODE=1
      FAST_RISK_ACCEPTED=1
      RUN_LOCAL_CHECKS=0
      RUN_FRONTEND_BUILD=0
      RUN_FULL_TESTS=0
      RUN_STRATEGY_TEST=0
      RUN_LATEST_DATA_ACCEPTANCE=0
      shift
      ;;
    --scope)
      DEPLOY_TARGET_SCOPE="${2:?missing scope}"
      shift 2
      ;;
    --frontend-hot-required)
      DEPLOY_FRONTEND_HOT_REQUIRED=1
      shift
      ;;
    --performance-verify)
      RUN_PERFORMANCE_VERIFY=1
      shift
      ;;
    --performance-rounds)
      RUN_PERFORMANCE_VERIFY_ROUNDS="${2:?missing performance rounds}"
      shift 2
      ;;
    --performance-samples)
      RUN_PERFORMANCE_VERIFY_SAMPLES="${2:?missing performance samples}"
      shift 2
      ;;
    --public-domain-verify)
      VERIFY_PUBLIC_DOMAIN=1
      shift
      ;;
    --configure-https)
      AUTO_CONFIGURE_HTTPS=1
      REFRESH_HTTPS_CONFIG=0
      shift
      ;;
    --refresh-https-config)
      REFRESH_HTTPS_CONFIG=1
      shift
      ;;
    --install-backup-cron)
      AUTO_INSTALL_BACKUP_CRON=1
      shift
      ;;
    --host)
      CLOUD_HOST="${2:?missing host}"
      shift 2
      ;;
    --user)
      CLOUD_USER="${2:?missing user}"
      shift 2
      ;;
    --key)
      CLOUD_SSH_KEY="${2:?missing key}"
      shift 2
      ;;
    --project-dir)
      CLOUD_PROJECT_DIR="${2:?missing project dir}"
      shift 2
      ;;
    --port)
      CLOUD_APP_PORT="${2:?missing port}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      log "unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

export CLOUD_HOST CLOUD_USER CLOUD_SSH_KEY CLOUD_PROJECT_DIR CLOUD_APP_PORT
export CLOUD_SSH_TIMEOUT CLOUD_SSH_CONNECT_TIMEOUT CLOUD_SSH_SERVER_ALIVE_COUNT_MAX
export CLOUD_DOMAIN CLOUD_CERT_EMAIL CLOUD_AUTH_COOKIE_SECURE CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE
export AUTO_INITIAL_GIT_COMMIT AUTO_INSTALL_BACKUP_CRON AUTO_CONFIGURE_HTTPS REFRESH_HTTPS_CONFIG HTTPS_REQUIRED
export VERIFY_PUBLIC_DOMAIN
export RUN_COMPILE RUN_FRONTEND_BUILD RUN_STRATEGY_TEST RUN_FULL_TESTS RUN_LATEST_DATA_ACCEPTANCE
export DEPLOY_TARGET_SCOPE DEPLOY_FRONTEND_HOT_REQUIRED
export CLOUD_SSH_TIMEOUT CLOUD_SSH_CONNECT_TIMEOUT CLOUD_SSH_SERVER_ALIVE_COUNT_MAX
export RUN_PERFORMANCE_VERIFY_ROUNDS RUN_PERFORMANCE_VERIFY_SAMPLES

if [[ -z "$CLOUD_HOST" ]]; then
  log "CLOUD_HOST is required. Use --host <host> or export CLOUD_HOST."
  exit 2
fi
if [[ -z "$CLOUD_SSH_KEY" ]]; then
  log "CLOUD_SSH_KEY is required. Use --key <path> or export CLOUD_SSH_KEY."
  exit 2
fi
if [[ "$FAST_MODE" == "1" && "$FAST_RISK_ACCEPTED" != "1" ]]; then
  log "fast mode requires --fast-risk-accepted"
  exit 2
fi
if [[ ! -f "$CLOUD_SSH_KEY" ]]; then
  log "ssh key not found: $CLOUD_SSH_KEY"
  exit 2
fi
chmod 600 "$CLOUD_SSH_KEY" 2>/dev/null || true

verify_remote() {
  log "verify remote service health"
  if [[ "$DEPLOY_TARGET_SCOPE" == "frontend-hot" ]]; then
    VERIFY_WEB_IMAGE_SYNC=0
  fi
  cloud_ssh env CLOUD_APP_PORT="$CLOUD_APP_PORT" CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" VERIFY_WEB_IMAGE_SYNC="$VERIFY_WEB_IMAGE_SYNC" bash -s <<'REMOTE'
set -euo pipefail
dump_container_diagnostics() {
  local name="$1"
  echo "diagnostics:$name" >&2
  sudo docker inspect "$name" --format '{{json .State}}' 2>/dev/null >&2 || true
  sudo docker logs --tail=120 "$name" 2>/dev/null >&2 || true
}
wait_for_container() {
  local name="$1"
  local status=""
  for _ in $(seq 1 60); do
    status=$(sudo docker inspect "$name" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || echo missing)
    echo "$name status:$status"
    case "$status" in
      healthy|running)
        return 0
        ;;
    esac
    sleep 2
  done
  echo "$name status did not reach running/healthy" >&2
  dump_container_diagnostics "$name"
  return 1
}
curl_retry() {
  local output_path="$1"
  local url="$2"
  local max_time="${3:-20}"
  local attempts="${4:-5}"
  local attempt
  for attempt in $(seq 1 "$attempts"); do
    if curl -sS -f -o "$output_path" --max-time "$max_time" "$url"; then
      return 0
    fi
    echo "curl_retry:${attempt}/${attempts}:${url}" >&2
    sleep $((attempt * 2))
  done
  return 1
}
for name in tquant-app-mysql tquant-runtime-scheduler-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql tquant-go-bff-gateway tquant-go-market-read-service tquant-go-scan-worker; do
  wait_for_container "$name"
done
if test "${VERIFY_WEB_IMAGE_SYNC:-1}" = "1"; then
  EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
  for container in tquant-app-mysql tquant-runtime-scheduler-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql; do
    ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
    test "$ACTUAL_WEB_IMAGE" = "$EXPECTED_WEB_IMAGE"
  done
  echo web_image:ok
else
  echo web_image:skipped_frontend_hot
fi
grep -Eq '^AUTH_COOKIE_SECURE=true$' "$CLOUD_PROJECT_DIR/.env"
grep -Eq '^AUTH_ALLOW_INSECURE_HTTP_COOKIE=false$' "$CLOUD_PROJECT_DIR/.env"
grep -Eq '^HTTPS_REQUIRED=1$' "$CLOUD_PROJECT_DIR/.env"
grep -Eq '^TQUANT_INTERNAL_SERVICE_TOKEN=.{32,}$' "$CLOUD_PROJECT_DIR/.env"
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
API_FALLBACK_STATUS=$(curl -sS -D /tmp/gupiao_api_fallback_headers.txt -o /tmp/gupiao_api_fallback.json -w '%{http_code}' --max-time 10 "http://127.0.0.1:${CLOUD_APP_PORT}/api/__missing_smoke__")
test "$API_FALLBACK_STATUS" = 404
grep -qi '^Content-Type: application/json' /tmp/gupiao_api_fallback_headers.txt
python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_api_fallback.json', encoding='utf-8'))
assert payload.get('detail') == 'API endpoint not found', payload
print('api_fallback:ok')
PY
curl_retry /tmp/gupiao_home.html "http://127.0.0.1:${CLOUD_APP_PORT}/" 20 5
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

performance_verify() {
  if [[ "$RUN_PERFORMANCE_VERIFY" != "1" ]]; then
    return 0
  fi
  local round
  for round in $(seq 1 "$RUN_PERFORMANCE_VERIFY_ROUNDS"); do
    log "run online Go/Rust performance gates round ${round}/${RUN_PERFORMANCE_VERIFY_ROUNDS} samples=${RUN_PERFORMANCE_VERIFY_SAMPLES}"
    "$ROOT_DIR/scripts/measure_cloud_go_rust_performance.py" \
      --host "$CLOUD_HOST" \
      --user "$CLOUD_USER" \
      --key "$CLOUD_SSH_KEY" \
      --base-url "http://127.0.0.1:${CLOUD_APP_PORT}" \
      --project-dir "$CLOUD_PROJECT_DIR" \
      --samples "$RUN_PERFORMANCE_VERIFY_SAMPLES"
  done
}

if [[ "$VERIFY_ONLY" == "1" ]]; then
  verify_remote
  performance_verify
  print_deploy_summary "verify-ok"
  exit 0
fi

log "deploy to ${CLOUD_USER}@${CLOUD_HOST} using ${CLOUD_SSH_KEY}"
if [[ "$FAST_MODE" == "1" ]]; then
  log "fast mode: local checks skipped by explicit --fast-risk-accepted, HTTPS automation/cron disabled, production-safe cookies kept enabled"
else
  log "safe mode: local compile/build checks enabled; HTTPS automation/cron disabled, production-safe cookies kept enabled"
fi
RUN_COMPILE="$RUN_LOCAL_CHECKS" \
RUN_FRONTEND_BUILD="$RUN_LOCAL_CHECKS" \
RUN_STRATEGY_TEST="$RUN_STRATEGY_TEST" \
RUN_FULL_TESTS="$RUN_FULL_TESTS" \
RUN_LATEST_DATA_ACCEPTANCE="$RUN_LATEST_DATA_ACCEPTANCE" \
DEPLOY_TARGET_SCOPE="$DEPLOY_TARGET_SCOPE" \
DEPLOY_FRONTEND_HOT_REQUIRED="$DEPLOY_FRONTEND_HOT_REQUIRED" \
AUTO_INITIAL_GIT_COMMIT="$AUTO_INITIAL_GIT_COMMIT" \
AUTO_INSTALL_BACKUP_CRON="$AUTO_INSTALL_BACKUP_CRON" \
AUTO_CONFIGURE_HTTPS="$AUTO_CONFIGURE_HTTPS" \
REFRESH_HTTPS_CONFIG="$REFRESH_HTTPS_CONFIG" \
HTTPS_REQUIRED="$HTTPS_REQUIRED" \
CLOUD_HOST="$CLOUD_HOST" \
CLOUD_USER="$CLOUD_USER" \
CLOUD_SSH_KEY="$CLOUD_SSH_KEY" \
CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" \
CLOUD_APP_PORT="$CLOUD_APP_PORT" \
CLOUD_DOMAIN="$CLOUD_DOMAIN" \
CLOUD_CERT_EMAIL="$CLOUD_CERT_EMAIL" \
CLOUD_AUTH_COOKIE_SECURE="$CLOUD_AUTH_COOKIE_SECURE" \
CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="$CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE" \
VERIFY_PUBLIC_DOMAIN="$VERIFY_PUBLIC_DOMAIN" \
CLOUD_SSH_TIMEOUT="$CLOUD_SSH_TIMEOUT" \
CLOUD_SSH_CONNECT_TIMEOUT="$CLOUD_SSH_CONNECT_TIMEOUT" \
CLOUD_SSH_SERVER_ALIVE_COUNT_MAX="$CLOUD_SSH_SERVER_ALIVE_COUNT_MAX" \
"$ROOT_DIR/scripts/deploy_cloud_server.sh"

verify_remote
performance_verify
print_deploy_summary "deploy-ok"
