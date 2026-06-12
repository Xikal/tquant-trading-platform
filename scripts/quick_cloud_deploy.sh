#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/cloud_ssh_lib.sh"

CLOUD_HOST="${CLOUD_HOST:-}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_SSH_KEY="${CLOUD_SSH_KEY:-}"
CLOUD_PROJECT_DIR="${CLOUD_PROJECT_DIR:-/home/ubuntu/gupiao-upload}"
CLOUD_APP_PORT="${CLOUD_APP_PORT:-18090}"
BACKEND_API_PORT="${BACKEND_API_PORT:-18091}"
CLOUD_DOMAIN="${CLOUD_DOMAIN:-}"
CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-}"
CLOUD_PUBLIC_BASE_URL="${CLOUD_PUBLIC_BASE_URL:-}"
CLOUD_SSH_TIMEOUT="${CLOUD_SSH_TIMEOUT:-2400}"
CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-30}"
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
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED="${FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED:-false}"
FRONTEND_NEXT_CUTOVER_PATHS="${FRONTEND_NEXT_CUTOVER_PATHS:-}"
DATA_QUALITY_SLA_ENABLED="${DATA_QUALITY_SLA_ENABLED:-}"
VERIFY_PUBLIC_DOMAIN="${VERIFY_PUBLIC_DOMAIN:-0}"
VERIFY_PUBLIC_ENTRY="${VERIFY_PUBLIC_ENTRY:-1}"
DEPLOY_TARGET_SCOPE="${DEPLOY_TARGET_SCOPE:-auto}"
DEPLOY_FRONTEND_NEXT_REQUIRED="${DEPLOY_FRONTEND_NEXT_REQUIRED:-0}"
DEPLOY_CHANGED_FILES_FROM="${DEPLOY_CHANGED_FILES_FROM:-}"
DEPLOY_COMPOSE_TOPOLOGY="${DEPLOY_COMPOSE_TOPOLOGY:-monolith}"
BACKEND_API_COMPOSE_FILE="${BACKEND_API_COMPOSE_FILE:-}"
FRONTEND_COMPOSE_FILE="${FRONTEND_COMPOSE_FILE:-}"
DB_MIGRATION_COMPOSE_FILE="${DB_MIGRATION_COMPOSE_FILE:-docker-compose.mysql.yml}"
RUNTIME_COMPOSE_FILE="${RUNTIME_COMPOSE_FILE:-docker-compose.mysql.yml}"
GO_COMPOSE_FILE="${GO_COMPOSE_FILE:-docker-compose.mysql.yml}"
DEPLOY_SYNC_MODE="${DEPLOY_SYNC_MODE:-package-only}"
DEPLOY_PREBUILT_IMAGES_ENABLED="${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}"
DEPLOY_PREBUILT_WEB_IMAGE_REF="${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"
DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF="${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"
REMOTE_NODE_BASE_IMAGE="${REMOTE_NODE_BASE_IMAGE:-}"
REMOTE_RUST_BASE_IMAGE="${REMOTE_RUST_BASE_IMAGE:-}"
REMOTE_PYTHON_BASE_IMAGE="${REMOTE_PYTHON_BASE_IMAGE:-}"
DEPLOY_PREBUILT_GO_BFF_IMAGE_REF="${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}"
DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF="${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}"
DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF="${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"
DEPLOY_WITH_ANALYTICS_WORKER="${DEPLOY_WITH_ANALYTICS_WORKER:-0}"
DEPLOY_EMBED_RUNTIME_SCHEDULER="${DEPLOY_EMBED_RUNTIME_SCHEDULER:-0}"
DEPLOY_D5_GATE_SUMMARY="${DEPLOY_D5_GATE_SUMMARY:-docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json}"
VERIFY_WEB_IMAGE_SYNC=1
RUN_REMOTE_PREFLIGHT="${RUN_REMOTE_PREFLIGHT:-1}"
RUN_REMOTE_SAFE_CLEANUP="${RUN_REMOTE_SAFE_CLEANUP:-1}"
REMOTE_PREFLIGHT_READ_ONLY="${REMOTE_PREFLIGHT_READ_ONLY:-0}"
REMOTE_MIN_FREE_GB="${REMOTE_MIN_FREE_GB:-8}"
REMOTE_ROOT_WARN_PCT="${REMOTE_ROOT_WARN_PCT:-70}"
REMOTE_ROOT_BLOCK_PCT="${REMOTE_ROOT_BLOCK_PCT:-80}"
REMOTE_DOCKER_BUILD_CACHE_WARN_GB="${REMOTE_DOCKER_BUILD_CACHE_WARN_GB:-2}"
REMOTE_MYSQL_SLOW_LOG_WARN_MB="${REMOTE_MYSQL_SLOW_LOG_WARN_MB:-512}"
REMOTE_BINLOG_EXPIRE_MAX_SECONDS="${REMOTE_BINLOG_EXPIRE_MAX_SECONDS:-259200}"
REMOTE_MAX_BINLOG_SIZE_WARN_MB="${REMOTE_MAX_BINLOG_SIZE_WARN_MB:-256}"
REMOTE_MYSQL_BACKUP_MIN_COUNT="${REMOTE_MYSQL_BACKUP_MIN_COUNT:-1}"
REMOTE_MIN_SWAP_MB="${REMOTE_MIN_SWAP_MB:-2048}"
REMOTE_TEMP_SWAP_PATH="${REMOTE_TEMP_SWAP_PATH:-/swapfile-codex-deploy}"
REMOTE_TEMP_SWAP_MB="${REMOTE_TEMP_SWAP_MB:-2048}"
REMOTE_REMOVE_TEMP_SWAP_AFTER_DEPLOY="${REMOTE_REMOVE_TEMP_SWAP_AFTER_DEPLOY:-1}"

log() {
  printf '[quick-deploy] %s\n' "$*"
}

resolved_public_base_url() {
  if [[ -n "$CLOUD_PUBLIC_BASE_URL" ]]; then
    printf '%s' "${CLOUD_PUBLIC_BASE_URL%/}"
  elif [[ "$HTTPS_REQUIRED" == "1" ]]; then
    printf 'https://%s' "$CLOUD_HOST"
  else
    printf 'http://%s:%s' "$CLOUD_HOST" "$CLOUD_APP_PORT"
  fi
}

print_deploy_summary() {
  local outcome="$1"
  local mode="safe"
  if [[ "$FAST_MODE" == "1" ]]; then
    mode="fast-risk-accepted"
  elif [[ "$RUN_FULL_TESTS" == "1" ]]; then
    mode="full"
  fi
  local public_base
  public_base="$(resolved_public_base_url)"
  log "summary outcome=${outcome} mode=${mode} scope=${DEPLOY_TARGET_SCOPE} target=${CLOUD_USER}@${CLOUD_HOST} port=${CLOUD_APP_PORT} domain=${CLOUD_DOMAIN:-none} public_base=${public_base} https_required=${HTTPS_REQUIRED} public_entry_verify=${VERIFY_PUBLIC_ENTRY} public_domain_verify=${VERIFY_PUBLIC_DOMAIN} performance_verify=${RUN_PERFORMANCE_VERIFY} prebuilt_images=${DEPLOY_PREBUILT_IMAGES_ENABLED}"
  log "summary sync_mode=${DEPLOY_SYNC_MODE}"
  if [[ -n "$CLOUD_DOMAIN" ]]; then
    log "summary urls default=${public_base}/monitor http=http://${CLOUD_HOST}:${CLOUD_APP_PORT} domain=https://${CLOUD_DOMAIN}"
  else
    log "summary urls default=${public_base}/monitor http=http://${CLOUD_HOST}:${CLOUD_APP_PORT}"
  fi
}

usage() {
  cat <<'EOF'
Usage: scripts/quick_cloud_deploy.sh [options]

Defaults:
  host   required via CLOUD_HOST or --host
  user   ubuntu
  key    required via CLOUD_SSH_KEY or --key unless CLOUD_PASSWORD is set
  port   18090

Options:
  --verify-only   Skip deploy and verify current remote state. Remote preflight runs read-only.
  --full          Run the slower local checks and latest-data acceptance.
  --fast-risk-accepted
                 Skip local compile/build checks for emergency deploys only.
  --scope <auto|frontend-next|backend-api|db-migration|worker|go|ops|all>
                 Choose deployment target. auto is the default and uses changed files.
  --changed-files-from <file>
                 Read changed files from a newline-separated file for auto scope resolution.
  --compose-topology <monolith|separated>
                 Select monolith or separated deployment topology.
  --backend-api-compose-file <file>
                 Compose file used for backend-api scope.
  --frontend-compose-file <file>
                 Compose file used for frontend-next/frontend-web scope.
  --db-migration-compose-file <file>
                 Compose file used for migration scope.
  --runtime-compose-file <file>
                 Compose file used for worker scope.
  --go-compose-file <file>
                 Compose file used for Go service scope.
  --sync-mode <delta-package|package-only|git-inplace|git-clone>
                 Choose release sync mode. delta-package falls back to package-only.
  --prebuilt-images
                 Pull prebuilt images on the server and restart instead of building app images.
  --prebuilt-web-image <ref>
                 Image ref to tag as tquant-web:mysql when --prebuilt-images is enabled.
  --prebuilt-analytics-image <ref>
                 Image ref to tag as tquant-analytics:mysql when --prebuilt-images is enabled.
  --with-analytics-worker
                 Start and verify the optional analytics-worker profile.
  --embed-runtime-scheduler
                 Verify/deploy with runtime-worker embedded scheduler. The standalone
                 runtime-scheduler container is allowed to be absent only with this flag.
  --d5-gate-summary <file>
                 Local D5 gate summary JSON required by --embed-runtime-scheduler.
  --prebuilt-go-bff-image <ref>
                 Image ref to tag as tquant-go-bff:mysql when --prebuilt-images is enabled.
  --prebuilt-go-market-read-image <ref>
                 Image ref to tag as tquant-go-market-read:mysql when --prebuilt-images is enabled.
  --prebuilt-go-scan-image <ref>
                 Image ref to tag as tquant-go-scan-worker:mysql when --prebuilt-images is enabled.
  --frontend-next-required
                 Fail instead of falling back when frontend-next has no dist artifact.
  --performance-verify
                 Run online Go/Rust performance gates after deploy/verify.
                 Defaults to 2 rounds with 8 samples per round.
  --performance-rounds <n>
                 Override online performance validation rounds.
  --performance-samples <n>
                 Override samples per online performance validation round.
  --public-domain-verify
                 Fail when the public HTTPS domain cannot be reached.
  --public-base-url <url>
                 Override the default public entry URL. Defaults to https://<host>.
  --skip-public-entry-verify
                 Skip local verification of the default public entry URL.
  --skip-remote-preflight
                 Skip remote disk/swap/docker preflight before deployment.
  --skip-remote-cleanup
                 Keep old upload packages and temp hotpatch dirs during preflight.
  --remote-root-block-pct <n>
                 Stop before deploy when root filesystem usage is at or above this percent.
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
    --changed-files-from)
      DEPLOY_CHANGED_FILES_FROM="${2:?missing changed files path}"
      shift 2
      ;;
    --compose-topology)
      DEPLOY_COMPOSE_TOPOLOGY="${2:?missing compose topology}"
      shift 2
      ;;
    --backend-api-compose-file)
      BACKEND_API_COMPOSE_FILE="${2:?missing backend api compose file}"
      shift 2
      ;;
    --frontend-compose-file)
      FRONTEND_COMPOSE_FILE="${2:?missing frontend compose file}"
      shift 2
      ;;
    --db-migration-compose-file)
      DB_MIGRATION_COMPOSE_FILE="${2:?missing db migration compose file}"
      shift 2
      ;;
    --runtime-compose-file)
      RUNTIME_COMPOSE_FILE="${2:?missing runtime compose file}"
      shift 2
      ;;
    --go-compose-file)
      GO_COMPOSE_FILE="${2:?missing go compose file}"
      shift 2
      ;;
    --frontend-next-required)
      DEPLOY_FRONTEND_NEXT_REQUIRED=1
      shift
      ;;
    --sync-mode)
      DEPLOY_SYNC_MODE="${2:?missing sync mode}"
      shift 2
      ;;
    --prebuilt-images)
      DEPLOY_PREBUILT_IMAGES_ENABLED=1
      shift
      ;;
    --prebuilt-web-image)
      DEPLOY_PREBUILT_WEB_IMAGE_REF="${2:?missing prebuilt web image ref}"
      shift 2
      ;;
    --prebuilt-analytics-image)
      DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF="${2:?missing prebuilt analytics image ref}"
      shift 2
      ;;
    --with-analytics-worker)
      DEPLOY_WITH_ANALYTICS_WORKER=1
      shift
      ;;
    --embed-runtime-scheduler)
      DEPLOY_EMBED_RUNTIME_SCHEDULER=1
      shift
      ;;
    --d5-gate-summary)
      DEPLOY_D5_GATE_SUMMARY="${2:?missing D5 gate summary path}"
      shift 2
      ;;
    --prebuilt-go-bff-image)
      DEPLOY_PREBUILT_GO_BFF_IMAGE_REF="${2:?missing prebuilt go bff image ref}"
      shift 2
      ;;
    --prebuilt-go-market-read-image)
      DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF="${2:?missing prebuilt go market read image ref}"
      shift 2
      ;;
    --prebuilt-go-scan-image)
      DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF="${2:?missing prebuilt go scan image ref}"
      shift 2
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
    --public-base-url)
      CLOUD_PUBLIC_BASE_URL="${2:?missing public base url}"
      shift 2
      ;;
    --skip-public-entry-verify)
      VERIFY_PUBLIC_ENTRY=0
      shift
      ;;
    --skip-remote-preflight)
      RUN_REMOTE_PREFLIGHT=0
      shift
      ;;
    --skip-remote-cleanup)
      RUN_REMOTE_SAFE_CLEANUP=0
      shift
      ;;
    --remote-root-block-pct)
      REMOTE_ROOT_BLOCK_PCT="${2:?missing remote root block percent}"
      shift 2
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

export CLOUD_HOST CLOUD_USER CLOUD_SSH_KEY CLOUD_PROJECT_DIR CLOUD_APP_PORT BACKEND_API_PORT
export CLOUD_SSH_TIMEOUT CLOUD_SSH_CONNECT_TIMEOUT CLOUD_SSH_SERVER_ALIVE_COUNT_MAX
export CLOUD_DOMAIN CLOUD_CERT_EMAIL CLOUD_PUBLIC_BASE_URL CLOUD_AUTH_COOKIE_SECURE CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE
export FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED
export FRONTEND_NEXT_CUTOVER_PATHS
export DATA_QUALITY_SLA_ENABLED
export AUTO_INITIAL_GIT_COMMIT AUTO_INSTALL_BACKUP_CRON AUTO_CONFIGURE_HTTPS REFRESH_HTTPS_CONFIG HTTPS_REQUIRED
export VERIFY_PUBLIC_DOMAIN VERIFY_PUBLIC_ENTRY
export RUN_COMPILE RUN_FRONTEND_BUILD RUN_STRATEGY_TEST RUN_FULL_TESTS RUN_LATEST_DATA_ACCEPTANCE
export DEPLOY_TARGET_SCOPE DEPLOY_FRONTEND_NEXT_REQUIRED DEPLOY_CHANGED_FILES_FROM
export DEPLOY_COMPOSE_TOPOLOGY
export BACKEND_API_COMPOSE_FILE FRONTEND_COMPOSE_FILE DB_MIGRATION_COMPOSE_FILE RUNTIME_COMPOSE_FILE GO_COMPOSE_FILE
export DEPLOY_SYNC_MODE
export DEPLOY_PREBUILT_IMAGES_ENABLED
export DEPLOY_PREBUILT_WEB_IMAGE_REF
export DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF
export DEPLOY_PREBUILT_GO_BFF_IMAGE_REF
export DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF
export DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF
export DEPLOY_WITH_ANALYTICS_WORKER
export DEPLOY_EMBED_RUNTIME_SCHEDULER
export DEPLOY_D5_GATE_SUMMARY
export REMOTE_NODE_BASE_IMAGE REMOTE_RUST_BASE_IMAGE REMOTE_PYTHON_BASE_IMAGE
export CLOUD_SSH_TIMEOUT CLOUD_SSH_CONNECT_TIMEOUT CLOUD_SSH_SERVER_ALIVE_COUNT_MAX
export RUN_PERFORMANCE_VERIFY_ROUNDS RUN_PERFORMANCE_VERIFY_SAMPLES
export RUN_REMOTE_PREFLIGHT RUN_REMOTE_SAFE_CLEANUP REMOTE_PREFLIGHT_READ_ONLY REMOTE_MIN_FREE_GB REMOTE_MIN_SWAP_MB
export REMOTE_ROOT_WARN_PCT REMOTE_ROOT_BLOCK_PCT REMOTE_DOCKER_BUILD_CACHE_WARN_GB
export REMOTE_MYSQL_SLOW_LOG_WARN_MB REMOTE_BINLOG_EXPIRE_MAX_SECONDS REMOTE_MAX_BINLOG_SIZE_WARN_MB
export REMOTE_TEMP_SWAP_PATH REMOTE_TEMP_SWAP_MB REMOTE_REMOVE_TEMP_SWAP_AFTER_DEPLOY

if [[ -z "$CLOUD_HOST" ]]; then
  log "CLOUD_HOST is required. Use --host <host> or export CLOUD_HOST."
  exit 2
fi
if [[ -z "$CLOUD_SSH_KEY" && -z "${CLOUD_PASSWORD:-}" ]]; then
  log "CLOUD_SSH_KEY or CLOUD_PASSWORD is required. Use --key <path> or export CLOUD_SSH_KEY/CLOUD_PASSWORD."
  exit 2
fi
if [[ "$FAST_MODE" == "1" && "$FAST_RISK_ACCEPTED" != "1" ]]; then
  log "fast mode requires --fast-risk-accepted"
  exit 2
fi
if [[ -n "$CLOUD_SSH_KEY" && ! -f "$CLOUD_SSH_KEY" ]]; then
  log "ssh key not found: $CLOUD_SSH_KEY"
  exit 2
fi
if [[ -n "$CLOUD_SSH_KEY" ]]; then
  chmod 600 "$CLOUD_SSH_KEY" 2>/dev/null || true
fi

embed_runtime_scheduler_requested() {
  case "$(printf '%s' "$DEPLOY_EMBED_RUNTIME_SCHEDULER" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_d5_gate_summary_path() {
  if [[ "$DEPLOY_D5_GATE_SUMMARY" = /* ]]; then
    printf '%s' "$DEPLOY_D5_GATE_SUMMARY"
  else
    printf '%s/%s' "$ROOT_DIR" "$DEPLOY_D5_GATE_SUMMARY"
  fi
}

verify_d5_scheduler_embed_gate() {
  if ! embed_runtime_scheduler_requested; then
    return 0
  fi
  local summary_path
  summary_path="$(resolve_d5_gate_summary_path)"
  log "verify D5 scheduler embed gate: ${summary_path}"
  python3 "$ROOT_DIR/scripts/verify_d5_scheduler_embed_gate.py" \
    --summary "$summary_path" \
    --fail-on-blocked
}

remote_preflight() {
  if [[ "$RUN_REMOTE_PREFLIGHT" != "1" ]]; then
    return 0
  fi
  local preflight_mode="read-only resource gate"
  if [[ "$REMOTE_PREFLIGHT_READ_ONLY" == "1" ]]; then
    preflight_mode="read-only resource gate"
  elif [[ "$RUN_REMOTE_SAFE_CLEANUP" == "1" || "${REMOTE_TEMP_SWAP_MB:-0}" -gt 0 ]]; then
    preflight_mode="resource gate with safe cleanup"
  fi
  log "remote preflight: ${preflight_mode}"
  cloud_ssh env \
    CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" \
    RUN_REMOTE_SAFE_CLEANUP="$RUN_REMOTE_SAFE_CLEANUP" \
    REMOTE_PREFLIGHT_READ_ONLY="$REMOTE_PREFLIGHT_READ_ONLY" \
    REMOTE_MIN_FREE_GB="$REMOTE_MIN_FREE_GB" \
    REMOTE_ROOT_WARN_PCT="$REMOTE_ROOT_WARN_PCT" \
    REMOTE_ROOT_BLOCK_PCT="$REMOTE_ROOT_BLOCK_PCT" \
    REMOTE_DOCKER_BUILD_CACHE_WARN_GB="$REMOTE_DOCKER_BUILD_CACHE_WARN_GB" \
    REMOTE_MYSQL_SLOW_LOG_WARN_MB="$REMOTE_MYSQL_SLOW_LOG_WARN_MB" \
    REMOTE_BINLOG_EXPIRE_MAX_SECONDS="$REMOTE_BINLOG_EXPIRE_MAX_SECONDS" \
    REMOTE_MAX_BINLOG_SIZE_WARN_MB="$REMOTE_MAX_BINLOG_SIZE_WARN_MB" \
    REMOTE_MYSQL_BACKUP_MIN_COUNT="$REMOTE_MYSQL_BACKUP_MIN_COUNT" \
    REMOTE_MIN_SWAP_MB="$REMOTE_MIN_SWAP_MB" \
    REMOTE_TEMP_SWAP_PATH="$REMOTE_TEMP_SWAP_PATH" \
    REMOTE_TEMP_SWAP_MB="$REMOTE_TEMP_SWAP_MB" \
    bash -s <<'REMOTE'
set -euo pipefail

free_root_gb() {
  df -BG / | awk 'NR==2 {gsub("G", "", $4); print $4 + 0}'
}

root_used_pct() {
  df -P / | awk 'NR==2 {gsub("%", "", $5); print $5 + 0}'
}

swap_total_mb() {
  awk '/SwapTotal/ {print int($2 / 1024)}' /proc/meminfo
}

docker_build_cache_gb() {
  sudo docker system df 2>/dev/null | awk '
    $1 == "Build" && $2 == "Cache" {
      value=$5
      number=value
      gsub(/[^0-9.]/, "", number)
      if (value ~ /Gi?B$/ || value ~ /GB$/ || value ~ /G$/) print int(number + 0)
      else if (value ~ /Mi?B$/ || value ~ /MB$/ || value ~ /M$/) print int((number + 0) / 1024)
      else if (value ~ /Ki?B$/ || value ~ /KB$/ || value ~ /K$/) print 0
      else print 0
    }'
}

mysql_slow_log_mb() {
  local slow_log="/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log"
  if sudo test -f "$slow_log"; then
    sudo du -m "$slow_log" | awk '{print $1 + 0}'
  else
    echo 0
  fi
}

mysql_binlog_expire_seconds() {
  cd "$CLOUD_PROJECT_DIR"
  if test -f .env; then
    set -a
    . ./.env
    set +a
  fi
  if test -n "${MYSQL_ROOT_PASSWORD:-}"; then
    sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT @@binlog_expire_logs_seconds;" 2>/dev/null || echo unknown
  else
    echo unknown
  fi
}

mysql_max_binlog_size_mb() {
  cd "$CLOUD_PROJECT_DIR"
  if test -f .env; then
    set -a
    . ./.env
    set +a
  fi
  if test -n "${MYSQL_ROOT_PASSWORD:-}"; then
    sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT FLOOR(@@max_binlog_size / 1024 / 1024);" 2>/dev/null || echo unknown
  else
    echo unknown
  fi
}

mysql_compose_resource_config_present() {
  if test -f "$CLOUD_PROJECT_DIR/docker-compose.mysql.yml" \
    && grep -q -- '--binlog-expire-logs-seconds=${MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}' "$CLOUD_PROJECT_DIR/docker-compose.mysql.yml" \
    && grep -q -- '--max-binlog-size=${MYSQL_MAX_BINLOG_SIZE:-256M}' "$CLOUD_PROJECT_DIR/docker-compose.mysql.yml"; then
    echo present
  else
    echo missing
  fi
}

journald_resource_config_present() {
  if sudo test -f /etc/systemd/journald.conf.d/tquant-resource.conf; then
    echo present
  else
    echo missing
  fi
}

deploy_backup_count() {
  sudo find /home -maxdepth 1 -type d -name 'gupiao-deploy-backup-*' 2>/dev/null | wc -l | tr -d '[:space:]'
}

mysql_backup_count() {
  sudo find /home -path '*/mysql-backups/*.sql.gz' -type f 2>/dev/null | wc -l | tr -d '[:space:]'
}

remote_resource_gate() {
  local used_pct build_cache_gb slow_log_mb binlog_expire max_binlog_size_mb mysql_compose_resource_config journald_resource_config backup_count mysql_backups
  used_pct="$(root_used_pct)"
  echo "preflight:root_used_pct=${used_pct}"
  if test "$used_pct" -ge "${REMOTE_ROOT_BLOCK_PCT:-80}"; then
    echo "preflight:blocking_root_used_pct=${used_pct}" >&2
    exit 42
  elif test "$used_pct" -ge "${REMOTE_ROOT_WARN_PCT:-70}"; then
    echo "preflight:warning_root_used_pct=${used_pct}"
  fi

  build_cache_gb="$(docker_build_cache_gb)"
  if test -n "$build_cache_gb"; then
    echo "preflight:docker_build_cache_gb=${build_cache_gb}"
    if test "$build_cache_gb" -ge "${REMOTE_DOCKER_BUILD_CACHE_WARN_GB:-2}"; then
      echo "preflight:warning_docker_build_cache_gb=${build_cache_gb}"
    fi
  fi

  slow_log_mb="$(mysql_slow_log_mb)"
  echo "preflight:mysql_slow_log_mb=${slow_log_mb}"
  if test "$slow_log_mb" -ge "${REMOTE_MYSQL_SLOW_LOG_WARN_MB:-512}"; then
    echo "preflight:warning_mysql_slow_log_mb=${slow_log_mb}"
  fi

  binlog_expire="$(mysql_binlog_expire_seconds)"
  echo "preflight:binlog_expire_seconds=${binlog_expire}"
  if test "$binlog_expire" != "unknown" && test "$binlog_expire" -gt "${REMOTE_BINLOG_EXPIRE_MAX_SECONDS:-259200}"; then
    echo "preflight:warning_binlog_expire_seconds=${binlog_expire}"
  fi

  max_binlog_size_mb="$(mysql_max_binlog_size_mb)"
  echo "preflight:max_binlog_size_mb=${max_binlog_size_mb}"
  if test "$max_binlog_size_mb" != "unknown" && test "$max_binlog_size_mb" -gt "${REMOTE_MAX_BINLOG_SIZE_WARN_MB:-256}"; then
    echo "preflight:warning_max_binlog_size_mb=${max_binlog_size_mb}"
  fi

  mysql_compose_resource_config="$(mysql_compose_resource_config_present)"
  echo "preflight:mysql_compose_resource_config=${mysql_compose_resource_config}"
  if test "$mysql_compose_resource_config" != "present"; then
    echo "preflight:warning_mysql_compose_resource_config=${mysql_compose_resource_config}"
  fi

  journald_resource_config="$(journald_resource_config_present)"
  echo "preflight:journald_resource_config=${journald_resource_config}"
  if test "$journald_resource_config" != "present"; then
    echo "preflight:warning_journald_resource_config=${journald_resource_config}"
  fi

  backup_count="$(deploy_backup_count)"
  echo "preflight:deploy_backup_count=${backup_count}"
  if test "$backup_count" -gt "${REMOTE_DEPLOY_BACKUP_WARN_COUNT:-3}"; then
    echo "preflight:warning_deploy_backup_count=${backup_count}"
  fi

  mysql_backups="$(mysql_backup_count)"
  echo "preflight:mysql_backup_count=${mysql_backups}"
  if test "$mysql_backups" -lt "${REMOTE_MYSQL_BACKUP_MIN_COUNT:-1}"; then
    echo "preflight:warning_mysql_backup_count=${mysql_backups}"
  fi
}

echo "preflight:project_dir=${CLOUD_PROJECT_DIR}"
echo "preflight:disk_before"
df -h /
echo "preflight:swap_before"
free -m || true
echo "preflight:docker_before"
sudo docker system df || true
remote_resource_gate

if test "${REMOTE_PREFLIGHT_READ_ONLY:-0}" != "1" && test "${RUN_REMOTE_SAFE_CLEANUP:-1}" = "1"; then
  echo "preflight:safe_cleanup"
  find /home/ubuntu -maxdepth 1 -type f \( -name 'gupiao-deploy-*' -o -name 'gupiao-delta-deploy-*' -o -name 'gupiao-frontend-hot-*' -o -name 'gupiao_remote_verify*.sh' \) -print -delete || true
  find /tmp -maxdepth 1 -type d \( -name 'gupiao-python-hot-*' -o -name 'tquant-queue-hotpatch-*' \) -print -exec rm -rf {} + || true
fi

FREE_GB="$(free_root_gb)"
echo "preflight:root_free_gb=${FREE_GB}"
if test "${REMOTE_PREFLIGHT_READ_ONLY:-0}" != "1" && test "$FREE_GB" -lt "${REMOTE_MIN_FREE_GB:-8}"; then
  echo "preflight:low_disk_safe_prune"
  sudo docker builder prune -f || true
  sudo docker image prune -f || true
  echo "preflight:docker_volumes_kept"
  FREE_GB="$(free_root_gb)"
  echo "preflight:root_free_gb_after_prune=${FREE_GB}"
fi

if test "$FREE_GB" -lt 4; then
  echo "preflight:root_free_gb_below_hard_minimum=${FREE_GB}" >&2
  exit 42
fi

SWAP_MB="$(swap_total_mb)"
echo "preflight:swap_total_mb=${SWAP_MB}"
if test "${REMOTE_PREFLIGHT_READ_ONLY:-0}" != "1" && test "$SWAP_MB" -lt "${REMOTE_MIN_SWAP_MB:-2048}" && test "${REMOTE_TEMP_SWAP_MB:-0}" -gt 0; then
  echo "preflight:create_temp_swap=${REMOTE_TEMP_SWAP_PATH}:${REMOTE_TEMP_SWAP_MB}M"
  if ! sudo swapon --show=NAME --noheadings | grep -Fxq "${REMOTE_TEMP_SWAP_PATH}"; then
    if ! test -f "${REMOTE_TEMP_SWAP_PATH}"; then
      sudo fallocate -l "${REMOTE_TEMP_SWAP_MB}M" "${REMOTE_TEMP_SWAP_PATH}" 2>/dev/null || sudo dd if=/dev/zero of="${REMOTE_TEMP_SWAP_PATH}" bs=1M count="${REMOTE_TEMP_SWAP_MB}"
      sudo chmod 600 "${REMOTE_TEMP_SWAP_PATH}"
      sudo mkswap "${REMOTE_TEMP_SWAP_PATH}" >/dev/null
    fi
    sudo swapon "${REMOTE_TEMP_SWAP_PATH}"
  fi
fi

echo "preflight:disk_after"
df -h /
echo "preflight:swap_after"
free -m || true
echo "preflight:docker_after"
sudo docker system df || true
REMOTE
}

run_verify_only_preflight() {
  if [[ "$RUN_REMOTE_PREFLIGHT" != "1" ]]; then
    return 0
  fi
  log "verify-only remote preflight: read-only resource gate"
  (
    RUN_REMOTE_SAFE_CLEANUP=0
    REMOTE_PREFLIGHT_READ_ONLY=1
    REMOTE_TEMP_SWAP_MB=0
    remote_preflight
  )
}

remote_post_deploy_cleanup() {
  if [[ "$RUN_REMOTE_PREFLIGHT" != "1" || "$REMOTE_REMOVE_TEMP_SWAP_AFTER_DEPLOY" != "1" ]]; then
    return 0
  fi
  log "remote post-deploy cleanup: remove temporary deploy swap when idle"
  cloud_ssh env REMOTE_TEMP_SWAP_PATH="$REMOTE_TEMP_SWAP_PATH" bash -s <<'REMOTE'
set -euo pipefail
if test "${REMOTE_TEMP_SWAP_PATH}" != "/swapfile-codex-deploy"; then
  echo "post_cleanup:skip_non_default_temp_swap=${REMOTE_TEMP_SWAP_PATH}"
  exit 0
fi
if sudo swapon --show=NAME --noheadings | grep -Fxq "${REMOTE_TEMP_SWAP_PATH}"; then
  if sudo swapoff "${REMOTE_TEMP_SWAP_PATH}"; then
    sudo rm -f "${REMOTE_TEMP_SWAP_PATH}"
    echo "post_cleanup:temp_swap_removed"
  else
    echo "post_cleanup:temp_swap_still_in_use"
  fi
else
  sudo rm -f "${REMOTE_TEMP_SWAP_PATH}" 2>/dev/null || true
  echo "post_cleanup:temp_swap_absent"
fi
REMOTE
}

verify_remote() {
  log "verify remote service health"
  if [[ "$DEPLOY_TARGET_SCOPE" == "frontend-next" ]]; then
    VERIFY_WEB_IMAGE_SYNC=0
  fi
  cloud_ssh env CLOUD_APP_PORT="$CLOUD_APP_PORT" CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" VERIFY_WEB_IMAGE_SYNC="$VERIFY_WEB_IMAGE_SYNC" DEPLOY_WITH_ANALYTICS_WORKER="$DEPLOY_WITH_ANALYTICS_WORKER" DEPLOY_EMBED_RUNTIME_SCHEDULER="$DEPLOY_EMBED_RUNTIME_SCHEDULER" bash -s <<'REMOTE'
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
with_analytics_worker() {
  case "$(printf '%s' "${DEPLOY_WITH_ANALYTICS_WORKER:-0}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}
embedded_scheduler_enabled() {
  case "$(printf '%s' "${DEPLOY_EMBED_RUNTIME_SCHEDULER:-0}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}
web_image_containers() {
  printf 'tquant-app-mysql tquant-runtime-worker-mysql'
  if ! embedded_scheduler_enabled; then
    printf ' tquant-runtime-scheduler-mysql'
  fi
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
for name in tquant-app-mysql tquant-runtime-worker-mysql tquant-go-bff-gateway tquant-go-market-read-service tquant-go-scan-worker; do
  wait_for_container "$name"
done
if embedded_scheduler_enabled; then
  echo "runtime_scheduler:embedded"
else
  wait_for_container tquant-runtime-scheduler-mysql
fi
sudo docker rm -f tquant-backtest-worker-mysql 2>/dev/null || true
if with_analytics_worker; then
  wait_for_container tquant-analytics-worker-mysql
else
  echo "analytics_worker:skipped_on_demand"
fi
if test "${VERIFY_WEB_IMAGE_SYNC:-1}" = "1"; then
  EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
  for container in $(web_image_containers); do
    ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
    test "$ACTUAL_WEB_IMAGE" = "$EXPECTED_WEB_IMAGE"
  done
  echo web_image:ok
else
  echo web_image:skipped_frontend_hot
  echo web_image:skipped_frontend_next
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
assert payload.get('checks', {}).get('frontend_next_dist') is True, payload
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
if with_analytics_worker; then
  sudo docker exec tquant-analytics-worker-mysql python - <<'PY'
import duckdb, pyarrow  # noqa: F401
from app.core.database import ping_database

ping_database()
print("analytics_worker_readyz:ok")
PY
else
  echo "analytics_worker_readyz:skipped_on_demand"
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

verify_public_entry() {
  if [[ "$VERIFY_PUBLIC_ENTRY" != "1" ]]; then
    return 0
  fi
  local public_base
  public_base="$(resolved_public_base_url)"
  log "verify default public entry ${public_base}"
  curl -k -sS -f --max-time 15 "${public_base}/readyz" >/tmp/gupiao_public_entry_readyz.json
  python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_public_entry_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
print('public_entry:ok')
PY
}

if [[ "$VERIFY_ONLY" == "1" ]]; then
  verify_d5_scheduler_embed_gate
  run_verify_only_preflight
  verify_remote
  verify_public_entry
  performance_verify
  print_deploy_summary "verify-ok"
  exit 0
fi

if [[ -n "$CLOUD_SSH_KEY" ]]; then
  log "deploy to ${CLOUD_USER}@${CLOUD_HOST} using ssh-key:${CLOUD_SSH_KEY}"
else
  log "deploy to ${CLOUD_USER}@${CLOUD_HOST} using password"
fi
if [[ "$FAST_MODE" == "1" ]]; then
  log "fast mode: local checks skipped by explicit --fast-risk-accepted, HTTPS automation/cron disabled, production-safe cookies kept enabled"
else
  log "safe mode: local compile/build checks enabled; HTTPS automation/cron disabled, production-safe cookies kept enabled"
fi
verify_d5_scheduler_embed_gate
remote_preflight
RUN_COMPILE="$RUN_LOCAL_CHECKS" \
RUN_FRONTEND_BUILD="$RUN_LOCAL_CHECKS" \
RUN_STRATEGY_TEST="$RUN_STRATEGY_TEST" \
RUN_FULL_TESTS="$RUN_FULL_TESTS" \
RUN_LATEST_DATA_ACCEPTANCE="$RUN_LATEST_DATA_ACCEPTANCE" \
DEPLOY_TARGET_SCOPE="$DEPLOY_TARGET_SCOPE" \
DEPLOY_FRONTEND_NEXT_REQUIRED="$DEPLOY_FRONTEND_NEXT_REQUIRED" \
DEPLOY_CHANGED_FILES_FROM="$DEPLOY_CHANGED_FILES_FROM" \
DEPLOY_COMPOSE_TOPOLOGY="$DEPLOY_COMPOSE_TOPOLOGY" \
BACKEND_API_COMPOSE_FILE="$BACKEND_API_COMPOSE_FILE" \
FRONTEND_COMPOSE_FILE="$FRONTEND_COMPOSE_FILE" \
DB_MIGRATION_COMPOSE_FILE="$DB_MIGRATION_COMPOSE_FILE" \
RUNTIME_COMPOSE_FILE="$RUNTIME_COMPOSE_FILE" \
GO_COMPOSE_FILE="$GO_COMPOSE_FILE" \
DEPLOY_SYNC_MODE="$DEPLOY_SYNC_MODE" \
REMOTE_NODE_BASE_IMAGE="$REMOTE_NODE_BASE_IMAGE" \
REMOTE_RUST_BASE_IMAGE="$REMOTE_RUST_BASE_IMAGE" \
REMOTE_PYTHON_BASE_IMAGE="$REMOTE_PYTHON_BASE_IMAGE" \
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
BACKEND_API_PORT="$BACKEND_API_PORT" \
CLOUD_DOMAIN="$CLOUD_DOMAIN" \
CLOUD_CERT_EMAIL="$CLOUD_CERT_EMAIL" \
CLOUD_AUTH_COOKIE_SECURE="$CLOUD_AUTH_COOKIE_SECURE" \
CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="$CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE" \
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED="$FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED" \
FRONTEND_NEXT_CUTOVER_PATHS="$FRONTEND_NEXT_CUTOVER_PATHS" \
DATA_QUALITY_SLA_ENABLED="$DATA_QUALITY_SLA_ENABLED" \
DEPLOY_WITH_ANALYTICS_WORKER="$DEPLOY_WITH_ANALYTICS_WORKER" \
DEPLOY_EMBED_RUNTIME_SCHEDULER="$DEPLOY_EMBED_RUNTIME_SCHEDULER" \
DEPLOY_D5_GATE_SUMMARY="$DEPLOY_D5_GATE_SUMMARY" \
VERIFY_PUBLIC_DOMAIN="$VERIFY_PUBLIC_DOMAIN" \
CLOUD_SSH_TIMEOUT="$CLOUD_SSH_TIMEOUT" \
CLOUD_SSH_CONNECT_TIMEOUT="$CLOUD_SSH_CONNECT_TIMEOUT" \
CLOUD_SSH_SERVER_ALIVE_COUNT_MAX="$CLOUD_SSH_SERVER_ALIVE_COUNT_MAX" \
"$ROOT_DIR/scripts/deploy_cloud_server.sh"

verify_remote
verify_public_entry
performance_verify
remote_post_deploy_cleanup
print_deploy_summary "deploy-ok"
