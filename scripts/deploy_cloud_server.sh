#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/cloud_ssh_lib.sh"

CLOUD_HOST="${CLOUD_HOST:-}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_PROJECT_DIR="${CLOUD_PROJECT_DIR:-/home/ubuntu/gupiao-upload}"
CLOUD_COMPOSE_FILE="${CLOUD_COMPOSE_FILE:-docker-compose.mysql.yml}"
CLOUD_APP_PORT="${CLOUD_APP_PORT:-18090}"
BACKEND_API_PORT="${BACKEND_API_PORT:-18091}"
DEPLOY_COMPOSE_TOPOLOGY="${DEPLOY_COMPOSE_TOPOLOGY:-monolith}"
if [[ "$DEPLOY_COMPOSE_TOPOLOGY" == "separated" ]]; then
  BACKEND_API_COMPOSE_FILE="${BACKEND_API_COMPOSE_FILE:-docker-compose.separated.yml}"
  FRONTEND_COMPOSE_FILE="${FRONTEND_COMPOSE_FILE:-docker-compose.separated.yml}"
else
  BACKEND_API_COMPOSE_FILE="${BACKEND_API_COMPOSE_FILE:-$CLOUD_COMPOSE_FILE}"
  FRONTEND_COMPOSE_FILE="${FRONTEND_COMPOSE_FILE:-$CLOUD_COMPOSE_FILE}"
fi
DB_MIGRATION_COMPOSE_FILE="${DB_MIGRATION_COMPOSE_FILE:-docker-compose.mysql.yml}"
RUNTIME_COMPOSE_FILE="${RUNTIME_COMPOSE_FILE:-docker-compose.mysql.yml}"
GO_COMPOSE_FILE="${GO_COMPOSE_FILE:-docker-compose.mysql.yml}"
CLOUD_KEEP_BACKUPS="${CLOUD_KEEP_BACKUPS:-3}"
AUTO_INITIAL_GIT_COMMIT="${AUTO_INITIAL_GIT_COMMIT:-1}"
AUTO_INSTALL_BACKUP_CRON="${AUTO_INSTALL_BACKUP_CRON:-1}"
AUTO_CONFIGURE_HTTPS="${AUTO_CONFIGURE_HTTPS:-1}"
REFRESH_HTTPS_CONFIG="${REFRESH_HTTPS_CONFIG:-1}"
HTTPS_REQUIRED="${HTTPS_REQUIRED:-1}"
CLOUD_DOMAIN="${CLOUD_DOMAIN:-}"
CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-}"
CLOUD_AUTH_COOKIE_SECURE="${CLOUD_AUTH_COOKIE_SECURE:-}"
CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="${CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE:-}"
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED="${FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED:-false}"
FRONTEND_NEXT_CUTOVER_PATHS="${FRONTEND_NEXT_CUTOVER_PATHS:-}"
DATA_QUALITY_SLA_ENABLED="${DATA_QUALITY_SLA_ENABLED:-}"
REMOTE_DEBIAN_APT_MIRROR="${REMOTE_DEBIAN_APT_MIRROR:-http://mirrors.tencentyun.com/debian}"
REMOTE_DEBIAN_APT_SECURITY_MIRROR="${REMOTE_DEBIAN_APT_SECURITY_MIRROR:-http://mirrors.tencentyun.com/debian-security}"
REMOTE_NODE_BASE_IMAGE="${REMOTE_NODE_BASE_IMAGE:-}"
REMOTE_RUST_BASE_IMAGE="${REMOTE_RUST_BASE_IMAGE:-}"
REMOTE_PYTHON_BASE_IMAGE="${REMOTE_PYTHON_BASE_IMAGE:-}"
VERIFY_PUBLIC_DOMAIN="${VERIFY_PUBLIC_DOMAIN:-0}"
BACKUP_TIME="${BACKUP_TIME:-02:20}"
DEPLOY_TARGET_SCOPE="${DEPLOY_TARGET_SCOPE:-auto}"
DEPLOY_CHANGED_FILES="${DEPLOY_CHANGED_FILES:-}"
DEPLOY_CHANGED_FILES_FROM="${DEPLOY_CHANGED_FILES_FROM:-}"
DEPLOY_FRONTEND_NEXT_REQUIRED="${DEPLOY_FRONTEND_NEXT_REQUIRED:-0}"
DEPLOY_SYNC_MODE="${DEPLOY_SYNC_MODE:-package-only}"
DEPLOY_DELTA_MAX_CHANGE_RATIO="${DEPLOY_DELTA_MAX_CHANGE_RATIO:-0.35}"
DEPLOY_GIT_REMOTE_URL="${DEPLOY_GIT_REMOTE_URL:-https://github.com/Xikal/tquant-trading-platform.git}"
DEPLOY_GIT_REF="${DEPLOY_GIT_REF:-${GITHUB_SHA:-HEAD}}"
DEPLOY_GIT_AUTH_TOKEN="${DEPLOY_GIT_AUTH_TOKEN:-}"
DEPLOY_PREBUILT_IMAGES_ENABLED="${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}"
DEPLOY_PREBUILT_WEB_IMAGE_REF="${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"
DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF="${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"
DEPLOY_PREBUILT_GO_BFF_IMAGE_REF="${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}"
DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF="${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}"
DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF="${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"
DEPLOY_WITH_ANALYTICS_WORKER="${DEPLOY_WITH_ANALYTICS_WORKER:-0}"
DEPLOY_EMBED_RUNTIME_SCHEDULER="${DEPLOY_EMBED_RUNTIME_SCHEDULER:-0}"
RUN_COMPILE="${RUN_COMPILE:-1}"
RUN_FRONTEND_BUILD="${RUN_FRONTEND_BUILD:-1}"
RUN_STRATEGY_TEST="${RUN_STRATEGY_TEST:-1}"
RUN_FULL_TESTS="${RUN_FULL_TESTS:-0}"
RUN_LATEST_DATA_ACCEPTANCE="${RUN_LATEST_DATA_ACCEPTANCE:-1}"
LATEST_DATA_ACCEPTANCE_REQUIRED="${LATEST_DATA_ACCEPTANCE_REQUIRED:-0}"
DEPLOY_PACKAGE_REQUIRED_PATHS="${DEPLOY_PACKAGE_REQUIRED_PATHS:-Dockerfile docker-compose.mysql.yml backend/app/main.py frontend-next/package.json frontend-next/src/index.tsx scripts/install_https_nginx.sh scripts/deploy_delta_package.py}"
DEPLOY_EFFECTIVE_SYNC_MODE="package-only"
DEPLOY_DELTA_CHANGED_COUNT=0
DEPLOY_DELTA_DELETED_COUNT=0
DEPLOY_DELTA_BYTES=0
DEPLOY_DELTA_FULL_BYTES=0
DEPLOY_DELTA_FALLBACK_REASON=""
DEPLOY_PACKAGE_PATH=""
DEPLOY_UPLOAD_SECONDS=0
DEPLOY_RESOLVED_UNITS=""

log() {
  printf '[deploy] %s\n' "$*"
}

file_size_bytes() {
  wc -c < "$1" | tr -d '[:space:]'
}

validate_deploy_sync_mode() {
  case "$DEPLOY_SYNC_MODE" in
    package-only|delta-package|git-inplace|git-clone)
      ;;
    *)
      log "invalid DEPLOY_SYNC_MODE=$DEPLOY_SYNC_MODE; expected package-only, delta-package, git-inplace, or git-clone"
      exit 2
      ;;
  esac
}

collect_changed_files() {
  if [[ -n "$DEPLOY_CHANGED_FILES_FROM" ]]; then
    sed '/^$/d' "$DEPLOY_CHANGED_FILES_FROM" | sort -u
    return 0
  fi
  if [[ -n "$DEPLOY_CHANGED_FILES" ]]; then
    printf '%s\n' "$DEPLOY_CHANGED_FILES" | tr ' ' '\n' | sed '/^$/d' | sort -u
    return 0
  fi
  if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi
  {
    if git -C "$ROOT_DIR" rev-parse --verify HEAD^ >/dev/null 2>&1; then
      git -C "$ROOT_DIR" diff --name-only HEAD^ HEAD
    fi
    git -C "$ROOT_DIR" diff --name-only
    git -C "$ROOT_DIR" diff --name-only --cached
    git -C "$ROOT_DIR" ls-files --others --exclude-standard
  } | sed '/^$/d' | sort -u
}

resolve_deploy_scope() {
  local changed_file_list
  local scope_json
  changed_file_list="$(mktemp "/tmp/gupiao-deploy-changed-files-XXXXXX")"
  collect_changed_files > "$changed_file_list"
  scope_json="$(python3 "$ROOT_DIR/scripts/deploy_scope.py" --scope "$DEPLOY_TARGET_SCOPE" --changed-files-from "$changed_file_list")" || {
    rm -f "$changed_file_list"
    log "deployment scope resolution failed"
    exit 2
  }
  rm -f "$changed_file_list"
  DEPLOY_RESOLVED_SCOPE="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["scope"])' <<< "$scope_json")"
  DEPLOY_RESOLVED_UNITS="$(python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)["units"]))' <<< "$scope_json")"
}

deploy_scope_has_unit() {
  local unit="$1"
  if [[ "$DEPLOY_RESOLVED_SCOPE" == "all" ]]; then
    return 0
  fi
  if [[ " ${DEPLOY_RESOLVED_UNITS} " == *" $unit "* ]]; then
    return 0
  fi
  [[ "$DEPLOY_RESOLVED_SCOPE" == "$unit" ]]
}

ensure_frontend_next_artifact() {
  if ! deploy_scope_has_unit frontend-next; then
    return 0
  fi
  if [[ -f "$ROOT_DIR/frontend-next/dist/index.html" ]]; then
    return 0
  fi
  if [[ "$DEPLOY_FRONTEND_NEXT_REQUIRED" == "1" ]]; then
    log "frontend-next scope requires frontend-next/dist/index.html"
    exit 2
  fi
  log "frontend-next scope requested but frontend-next/dist is missing; falling back to all"
  DEPLOY_RESOLVED_SCOPE=all
  DEPLOY_RESOLVED_UNITS=all
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
  if [[ "$RUN_FRONTEND_BUILD" == "1" ]] && deploy_scope_has_unit frontend-next; then
    log "build frontend-next"
    npm --prefix "$ROOT_DIR/frontend-next" run build
  fi
}

verify_package_contents() {
  local package_path="$1"
  local missing=0
  local required_path

  log "verify package contents"
  for required_path in $DEPLOY_PACKAGE_REQUIRED_PATHS; do
    if ! tar -tzf "$package_path" "./$required_path" >/dev/null 2>&1; then
      printf 'deploy package missing required path: %s\n' "$required_path" >&2
      missing=1
    fi
  done
  if [[ "$missing" != "0" ]]; then
    return 1
  fi
}

make_package() {
  if [[ "$DEPLOY_RESOLVED_SCOPE" == "frontend-next" ]]; then
    local frontend_next_package_path
    frontend_next_package_path="$(mktemp "/tmp/gupiao-frontend-next-hot-$(date +%Y%m%d%H%M%S)-XXXXXX")"
    log "create frontend-next hot package $frontend_next_package_path"
    test -f "$ROOT_DIR/frontend-next/dist/index.html"
    COPYFILE_DISABLE=1 tar \
      --no-xattrs \
      --exclude='._*' \
      --exclude='.DS_Store' \
      -czf "$frontend_next_package_path" -C "$ROOT_DIR/frontend-next" dist
    printf '%s\n' "$frontend_next_package_path"
    return 0
  fi

  if deploy_scope_has_unit frontend-next && [[ "$DEPLOY_RESOLVED_SCOPE" != "frontend-next" && "$DEPLOY_RESOLVED_SCOPE" != "all" ]]; then
    if [[ ! -f "$ROOT_DIR/frontend-next/dist/index.html" ]]; then
      log "combined frontend-next scope requires frontend-next/dist/index.html"
      return 1
    fi
  fi

  local package_path
  package_path="$(mktemp "/tmp/gupiao-deploy-$(date +%Y%m%d%H%M%S)-XXXXXX")"
  log "create package $package_path"
  local tar_excludes=(
    --exclude='.git'
    --exclude='.codex'
    --exclude='.continue'
    --exclude='.understand-anything'
    --exclude='.runtime'
    --exclude='.mysql-dist'
    --exclude='.mysql-local'
    --exclude='artifacts'
    --exclude='backups'
    --exclude='backend/.venv'
    --exclude='backend/.env'
    --exclude='backend/__pycache__'
    --exclude='backend/.pytest_cache'
    --exclude='backend/data'
    --exclude='backend/data/runtime.env'
    --exclude='backend/data/*.db'
    --exclude='backend/data/*.sqlite'
    --exclude='frontend'
    --exclude='frontend-next/node_modules'
    --exclude='frontend-next/test-results'
    --exclude='frontend-next/playwright-report'
    --exclude='frontend-next/*.tsbuildinfo'
    --exclude='rust/*/target'
    --exclude='rust/*/dist'
    --exclude='*.pyc'
    --exclude='*.pyo'
    --exclude='*.log'
    --exclude='._*'
    --exclude='.DS_Store'
  )
  if ! deploy_scope_has_unit frontend-next; then
    tar_excludes+=(--exclude='frontend-next/dist')
  fi
  COPYFILE_DISABLE=1 tar \
    --no-xattrs \
    "${tar_excludes[@]}" \
    -czf "$package_path" -C "$ROOT_DIR" .
  verify_package_contents "$package_path"
  printf '%s\n' "$package_path"
}

fetch_remote_deploy_manifest() {
  local output_path="$1"
  cloud_ssh "set -euo pipefail
if test -f '$CLOUD_PROJECT_DIR/.runtime/deploy-manifest.json'; then
  cat '$CLOUD_PROJECT_DIR/.runtime/deploy-manifest.json'
fi" > "$output_path"
  test -s "$output_path"
}

make_delta_package() {
  local remote_manifest="$1"
  local delta_path="$2"
  local local_manifest="$3"
  local summary_path="$4"

  python3 "$ROOT_DIR/scripts/deploy_delta_package.py" build \
    --root "$ROOT_DIR" \
    --previous "$remote_manifest" \
    --output "$delta_path" \
    --manifest-output "$local_manifest" \
    --summary-output "$summary_path" \
    --max-change-ratio "$DEPLOY_DELTA_MAX_CHANGE_RATIO"
}

load_delta_summary_env() {
  local summary_path="$1"
  local env_path
  env_path="$(mktemp "/tmp/gupiao-delta-summary-env-XXXXXX")"
  python3 "$ROOT_DIR/scripts/deploy_delta_package.py" summary-env --summary "$summary_path" > "$env_path"
  # shellcheck disable=SC1090
  source "$env_path"
  rm -f "$env_path"
}

prepare_deploy_package() {
  DEPLOY_EFFECTIVE_SYNC_MODE="$DEPLOY_SYNC_MODE"
  DEPLOY_DELTA_CHANGED_COUNT=0
  DEPLOY_DELTA_DELETED_COUNT=0
  DEPLOY_DELTA_BYTES=0
  DEPLOY_DELTA_FULL_BYTES=0
  DEPLOY_DELTA_FALLBACK_REASON=""

  if [[ "$DEPLOY_SYNC_MODE" != "delta-package" || "$DEPLOY_RESOLVED_SCOPE" == "frontend-next" ]] || deploy_scope_has_unit frontend-next; then
    DEPLOY_PACKAGE_PATH="$(make_package | tail -n 1)"
    DEPLOY_EFFECTIVE_SYNC_MODE="package-only"
    DEPLOY_DELTA_FULL_BYTES="$(file_size_bytes "$DEPLOY_PACKAGE_PATH")"
    if [[ "$DEPLOY_SYNC_MODE" == "delta-package" && ( "$DEPLOY_RESOLVED_SCOPE" == "frontend-next" || "$DEPLOY_RESOLVED_SCOPE" == *"frontend-next"* ) ]]; then
      DEPLOY_DELTA_FALLBACK_REASON="frontend_next_uses_hot_package"
    fi
    return 0
  fi

  local remote_manifest
  local delta_path
  local local_manifest
  local summary_path
  remote_manifest="$(mktemp "/tmp/gupiao-remote-deploy-manifest-XXXXXX.json")"
  delta_path="$(mktemp "/tmp/gupiao-delta-deploy-$(date +%Y%m%d%H%M%S)-XXXXXX.tgz")"
  local_manifest="$(mktemp "/tmp/gupiao-local-deploy-manifest-XXXXXX.json")"
  summary_path="$(mktemp "/tmp/gupiao-delta-summary-XXXXXX.json")"

  if ! fetch_remote_deploy_manifest "$remote_manifest"; then
    DEPLOY_DELTA_FALLBACK_REASON="missing_remote_manifest"
    rm -f "$remote_manifest" "$delta_path" "$local_manifest" "$summary_path"
    DEPLOY_PACKAGE_PATH="$(make_package | tail -n 1)"
    DEPLOY_EFFECTIVE_SYNC_MODE="package-only"
    DEPLOY_DELTA_FULL_BYTES="$(file_size_bytes "$DEPLOY_PACKAGE_PATH")"
    return 0
  fi

  if ! make_delta_package "$remote_manifest" "$delta_path" "$local_manifest" "$summary_path"; then
    DEPLOY_DELTA_FALLBACK_REASON="invalid_remote_manifest"
    rm -f "$remote_manifest" "$delta_path" "$local_manifest" "$summary_path"
    DEPLOY_PACKAGE_PATH="$(make_package | tail -n 1)"
    DEPLOY_EFFECTIVE_SYNC_MODE="package-only"
    DEPLOY_DELTA_FULL_BYTES="$(file_size_bytes "$DEPLOY_PACKAGE_PATH")"
    return 0
  fi
  load_delta_summary_env "$summary_path"
  if [[ -n "$DEPLOY_DELTA_FALLBACK_REASON" ]]; then
    rm -f "$remote_manifest" "$delta_path" "$local_manifest" "$summary_path"
    DEPLOY_PACKAGE_PATH="$(make_package | tail -n 1)"
    DEPLOY_EFFECTIVE_SYNC_MODE="package-only"
    if [[ "$DEPLOY_DELTA_FULL_BYTES" == "0" ]]; then
      DEPLOY_DELTA_FULL_BYTES="$(file_size_bytes "$DEPLOY_PACKAGE_PATH")"
    fi
    return 0
  fi
  DEPLOY_PACKAGE_PATH="$delta_path"
  DEPLOY_EFFECTIVE_SYNC_MODE="delta-package"
  rm -f "$remote_manifest" "$local_manifest" "$summary_path"
}

log_sync_metrics() {
  log "sync metrics: requested_mode=${DEPLOY_SYNC_MODE} sync_mode=${DEPLOY_EFFECTIVE_SYNC_MODE} changed_count=${DEPLOY_DELTA_CHANGED_COUNT} deleted_count=${DEPLOY_DELTA_DELETED_COUNT} delta_bytes=${DEPLOY_DELTA_BYTES} full_bytes=${DEPLOY_DELTA_FULL_BYTES} upload_seconds=${DEPLOY_UPLOAD_SECONDS} fallback_reason=${DEPLOY_DELTA_FALLBACK_REASON:-none}"
}

remote_deploy_from_git() {
  if [[ "$DEPLOY_RESOLVED_SCOPE" != "go" ]]; then
    return 1
  fi
  if [[ "$DEPLOY_SYNC_MODE" != "git-inplace" && "$DEPLOY_SYNC_MODE" != "git-clone" ]]; then
    return 1
  fi

  log "deploy via remote git sync ref ${DEPLOY_GIT_REF} scope ${DEPLOY_RESOLVED_SCOPE}"
  cloud_ssh env \
    CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" \
    CLOUD_COMPOSE_FILE="$CLOUD_COMPOSE_FILE" \
    BACKEND_API_COMPOSE_FILE="$BACKEND_API_COMPOSE_FILE" \
    FRONTEND_COMPOSE_FILE="$FRONTEND_COMPOSE_FILE" \
    DB_MIGRATION_COMPOSE_FILE="$DB_MIGRATION_COMPOSE_FILE" \
    RUNTIME_COMPOSE_FILE="$RUNTIME_COMPOSE_FILE" \
    GO_COMPOSE_FILE="$GO_COMPOSE_FILE" \
    CLOUD_USER="$CLOUD_USER" \
    CLOUD_KEEP_BACKUPS="$CLOUD_KEEP_BACKUPS" \
    CLOUD_AUTH_COOKIE_SECURE="${CLOUD_AUTH_COOKIE_SECURE:-}" \
    CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="${CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE:-}" \
    FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED="$FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED" \
    FRONTEND_NEXT_CUTOVER_PATHS="$FRONTEND_NEXT_CUTOVER_PATHS" \
    DATA_QUALITY_SLA_ENABLED="$DATA_QUALITY_SLA_ENABLED" \
    REMOTE_DEBIAN_APT_MIRROR="$REMOTE_DEBIAN_APT_MIRROR" \
    REMOTE_DEBIAN_APT_SECURITY_MIRROR="$REMOTE_DEBIAN_APT_SECURITY_MIRROR" \
    REMOTE_NODE_BASE_IMAGE="$REMOTE_NODE_BASE_IMAGE" \
    REMOTE_RUST_BASE_IMAGE="$REMOTE_RUST_BASE_IMAGE" \
    REMOTE_PYTHON_BASE_IMAGE="$REMOTE_PYTHON_BASE_IMAGE" \
    DEPLOY_RESOLVED_SCOPE="$DEPLOY_RESOLVED_SCOPE" \
    DEPLOY_COMPOSE_TOPOLOGY="$DEPLOY_COMPOSE_TOPOLOGY" \
    HTTPS_REQUIRED="$HTTPS_REQUIRED" \
    DEPLOY_GIT_REMOTE_URL="$DEPLOY_GIT_REMOTE_URL" \
    DEPLOY_GIT_REF="$DEPLOY_GIT_REF" \
    DEPLOY_GIT_AUTH_TOKEN="$DEPLOY_GIT_AUTH_TOKEN" \
    DEPLOY_PREBUILT_IMAGES_ENABLED="$DEPLOY_PREBUILT_IMAGES_ENABLED" \
    DEPLOY_PREBUILT_WEB_IMAGE_REF="$DEPLOY_PREBUILT_WEB_IMAGE_REF" \
    DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF="$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" \
    DEPLOY_PREBUILT_GO_BFF_IMAGE_REF="$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" \
    DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF="$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" \
    DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF="$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" \
    DEPLOY_WITH_ANALYTICS_WORKER="$DEPLOY_WITH_ANALYTICS_WORKER" \
    DEPLOY_EMBED_RUNTIME_SCHEDULER="$DEPLOY_EMBED_RUNTIME_SCHEDULER" \
    bash -s <<'REMOTE'
set -euo pipefail
TS=$(date +%Y%m%d%H%M%S)
REQUIRED_PATHS="Dockerfile docker-compose.mysql.yml backend/app/main.py frontend-next/package.json frontend-next/src/index.tsx scripts/install_https_nginx.sh scripts/deploy_delta_package.py"
DEPLOY_SCOPE="${DEPLOY_RESOLVED_SCOPE:-all}"

require_release_paths() {
  local root="$1"
  local path
  for path in $REQUIRED_PATHS; do
    if ! test -e "$root/$path"; then
      echo "remote git release missing required path: $path" >&2
      exit 1
    fi
  done
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  sed -i "/^${key}=/d" .env
  printf '%s=%s\n' "$key" "$value" >> .env
}

docker_compose_build() {
  local compose_file="$1"
  shift
  local log_file="/tmp/gupiao-docker-build-$TS.log"
  local attempt
  for attempt in 1 2 3; do
    if COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}" sudo -E docker compose -f "$compose_file" build "$@" 2>&1 | tee "$log_file"; then
      rm -f "$log_file"
      return 0
    fi
    if grep -Eqi 'TLS handshake timeout|failed to resolve source metadata|failed to do request|i/o timeout|connection reset by peer|temporary failure|context deadline exceeded|context canceled|no active session|DeadlineExceeded|BuildKit' "$log_file"; then
      if test "$attempt" -lt 3; then
        echo "docker build transient registry/buildkit failure; retrying attempt $((attempt + 1))/3" >&2
        sleep $((attempt * 5))
        continue
      fi
      echo "docker build transient failure persisted; retrying with classic builder" >&2
      COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}" DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 sudo -E docker compose -f "$compose_file" build "$@"
      rm -f "$log_file"
      return 0
    fi
    cat "$log_file" >&2
    rm -f "$log_file"
    return 1
  done
  cat "$log_file" >&2
  rm -f "$log_file"
  return 1
}

require_prebuilt_ref() {
  local name="$1"
  local value="$2"
  if test -z "$value"; then
    echo "prebuilt image mode requires $name" >&2
    exit 2
  fi
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
runtime_worker_services() {
  if embedded_scheduler_enabled; then
    printf 'runtime-worker'
  else
    printf 'runtime-scheduler runtime-worker'
  fi
}
app_runtime_services() {
  printf 'app '
  runtime_worker_services
}
web_image_containers() {
  printf 'tquant-app-mysql tquant-runtime-worker-mysql'
  if ! embedded_scheduler_enabled; then
    printf ' tquant-runtime-scheduler-mysql'
  fi
}
analytics_worker_services() {
  if with_analytics_worker; then
    printf ' %s' analytics-worker
  fi
}
stop_removed_backtest_worker() {
  sudo docker rm -f tquant-backtest-worker-mysql 2>/dev/null || true
}
stop_embedded_runtime_scheduler() {
  if embedded_scheduler_enabled; then
    sudo docker rm -f tquant-runtime-scheduler-mysql 2>/dev/null || true
  fi
}

use_prebuilt_app_images() {
  case "${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}" in
    1|true|yes)
      ;;
    auto)
      if test -z "${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"; then
        echo "prebuilt_images:app_unavailable_fallback_build"
        return 1
      fi
      if with_analytics_worker && test -z "${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"; then
        echo "prebuilt_images:analytics_unavailable_fallback_build"
        return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac
  require_prebuilt_ref DEPLOY_PREBUILT_WEB_IMAGE_REF "${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"
  if with_analytics_worker; then
    require_prebuilt_ref DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF "${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"
  fi
  echo "prebuilt_images:pull_app"
  sudo docker pull "$DEPLOY_PREBUILT_WEB_IMAGE_REF"
  sudo docker tag "$DEPLOY_PREBUILT_WEB_IMAGE_REF" tquant-web:mysql
  if with_analytics_worker; then
    sudo docker pull "$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF"
    sudo docker tag "$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" tquant-analytics:mysql
  fi
  echo "docker_build:skipped_prebuilt_app"
  return 0
}

use_prebuilt_go_images() {
  case "${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}" in
    1|true|yes)
      ;;
    auto)
      if test -z "${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}" || test -z "${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}" || test -z "${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"; then
        echo "prebuilt_images:go_unavailable_fallback_build"
        return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac
  require_prebuilt_ref DEPLOY_PREBUILT_GO_BFF_IMAGE_REF "${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}"
  require_prebuilt_ref DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF "${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}"
  require_prebuilt_ref DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF "${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"
  echo "prebuilt_images:pull_go"
  sudo docker pull "$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF"
  sudo docker pull "$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF"
  sudo docker pull "$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF"
  sudo docker tag "$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" tquant-go-bff:mysql
  sudo docker tag "$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" tquant-go-market-read:mysql
  sudo docker tag "$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" tquant-go-scan-worker:mysql
  echo "docker_build:skipped_prebuilt_go"
  return 0
}

git_network_retry() {
  local attempt
  for attempt in 1 2 3; do
    if GIT_HTTP_LOW_SPEED_LIMIT="${GIT_HTTP_LOW_SPEED_LIMIT:-1000}" \
      GIT_HTTP_LOW_SPEED_TIME="${GIT_HTTP_LOW_SPEED_TIME:-30}" \
      git -c "http.lowSpeedLimit=${GIT_HTTP_LOW_SPEED_LIMIT:-1000}" \
        -c "http.lowSpeedTime=${GIT_HTTP_LOW_SPEED_TIME:-30}" "$@"; then
      return 0
    fi
    if test "$attempt" -lt 3; then
      echo "git network failure; retrying attempt $((attempt + 1))/3" >&2
      sleep $((attempt * 5))
      continue
    fi
  done
  return 1
}

git_url="$DEPLOY_GIT_REMOTE_URL"
if test -n "${DEPLOY_GIT_AUTH_TOKEN:-}" && printf '%s' "$git_url" | grep -q '^https://github.com/'; then
  git_url="$(printf '%s' "$git_url" | sed "s#^https://#https://x-access-token:${DEPLOY_GIT_AUTH_TOKEN}@#")"
fi

cd /home/$CLOUD_USER
WORKTREE="/home/$CLOUD_USER/gupiao-git-worktree"
cleanup_git_remote_url() {
  if test -d "$CLOUD_PROJECT_DIR/.git"; then
    git -C "$CLOUD_PROJECT_DIR" remote set-url origin "$DEPLOY_GIT_REMOTE_URL" 2>/dev/null || true
  fi
  if test -d "$WORKTREE/.git"; then
    git -C "$WORKTREE" remote set-url origin "$DEPLOY_GIT_REMOTE_URL" 2>/dev/null || true
  fi
}
trap cleanup_git_remote_url EXIT

if test -d "$CLOUD_PROJECT_DIR/.git"; then
  cd "$CLOUD_PROJECT_DIR"
  git remote set-url origin "$git_url"
  git_network_retry fetch --prune --tags origin
  git checkout --detach "$DEPLOY_GIT_REF"
  git reset --hard "$DEPLOY_GIT_REF"
  git clean -fd -e .env -e .runtime -e backend/data
  cleanup_git_remote_url
  require_release_paths "$CLOUD_PROJECT_DIR"
  echo "deploy_sync:git-inplace"
else
  rm -rf "$WORKTREE"
  git_network_retry clone --no-checkout "$git_url" "$WORKTREE"
  git_network_retry -C "$WORKTREE" fetch --prune --tags origin
  git -C "$WORKTREE" checkout --detach "$DEPLOY_GIT_REF"
  cleanup_git_remote_url
  require_release_paths "$WORKTREE"
  if test -d "$CLOUD_PROJECT_DIR/.runtime"; then cp -a "$CLOUD_PROJECT_DIR/.runtime" "$WORKTREE/.runtime" || true; fi
  if test -f "$CLOUD_PROJECT_DIR/.env"; then cp -a "$CLOUD_PROJECT_DIR/.env" "$WORKTREE/.env" || true; fi
  PROJECT_PARENT=$(dirname "$CLOUD_PROJECT_DIR")
  sudo mkdir -p "$PROJECT_PARENT"
  if test -d "$CLOUD_PROJECT_DIR"; then
    sudo mv "$CLOUD_PROJECT_DIR" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS"
    sudo chown -R "$CLOUD_USER:$CLOUD_USER" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS" || true
  fi
  sudo mv "$WORKTREE" "$CLOUD_PROJECT_DIR"
  sudo chown -R "$CLOUD_USER:$CLOUD_USER" "$CLOUD_PROJECT_DIR"
  cd "$CLOUD_PROJECT_DIR"
  echo "deploy_sync:git-clone"
fi
touch .env
mkdir -p .runtime
python3 scripts/deploy_delta_package.py manifest --root . --output .runtime/deploy-manifest.json --quiet
echo "deploy_manifest:updated"
echo "deploy_scope:$DEPLOY_SCOPE"
DEPLOY_UNITS=" $DEPLOY_SCOPE "
case "$DEPLOY_SCOPE" in
  all)
    DEPLOY_UNITS=" all db-migration backend-api worker go frontend-next ops "
    ;;
  *)
    DEPLOY_UNITS=" $(printf '%s' "$DEPLOY_SCOPE" | tr ',' ' ') "
    ;;
esac
has_unit() {
  case "$DEPLOY_UNITS" in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}
frontend_web_compose_file() {
  if test -f "$FRONTEND_COMPOSE_FILE" && sudo docker compose -f "$FRONTEND_COMPOSE_FILE" ps frontend-web >/dev/null 2>&1; then
    printf '%s\n' "$FRONTEND_COMPOSE_FILE"
    return 0
  fi
  if test -f docker-compose.separated.yml && sudo docker compose -f docker-compose.separated.yml ps frontend-web >/dev/null 2>&1; then
    printf '%s\n' docker-compose.separated.yml
    return 0
  fi
  return 1
}
run_database_backup() {
  if test -f ./scripts/backup_database.sh; then
    BACKUP_TIME="${BACKUP_TIME:-02:20}" bash ./scripts/backup_database.sh || { echo "db_migration:backup_failed" >&2; exit 1; }
  else
    echo "db_migration:backup_script_missing" >&2
    exit 1
  fi
  echo "db_migration:backup_ok"
}
publish_frontend_next() {
  test -f frontend-next/dist/index.html
  previous_dir=""
  if sudo docker inspect tquant-app-mysql >/dev/null 2>&1 && sudo docker exec tquant-app-mysql test -d /app/frontend-next/dist/assets 2>/dev/null; then
    previous_dir="$(mktemp -d "/tmp/gupiao-frontend-next-prev-XXXXXX")"
    sudo docker cp tquant-app-mysql:/app/frontend-next/dist/assets "$previous_dir/assets" 2>/dev/null || true
  fi
  if test -n "$previous_dir" && test -d "$previous_dir/assets" && test -d frontend-next/dist/assets; then
    cp -a "$previous_dir/assets/." frontend-next/dist/assets/
  fi
  updated=0
  if frontend_web_compose="$(frontend_web_compose_file)"; then
    sudo docker compose -f "$frontend_web_compose" up -d --no-deps --force-recreate frontend-web
    echo "frontend_next:separated_frontend_web:$frontend_web_compose"
    updated=1
  fi
  if sudo docker inspect tquant-app-mysql >/dev/null 2>&1; then
    sudo docker exec -u root tquant-app-mysql sh -c 'rm -rf /app/frontend-next/dist && mkdir -p /app/frontend-next/dist'
    sudo docker cp frontend-next/dist/. tquant-app-mysql:/app/frontend-next/dist/
    sudo docker exec -u root tquant-app-mysql sh -c 'chmod -R a+rX /app/frontend-next/dist'
    echo "frontend_next:monolith_compat"
    updated=1
  fi
  if test "$updated" != "1"; then
    echo "frontend_next:no_running_target" >&2
    exit 1
  fi
  if test -n "$previous_dir"; then sudo rm -rf "$previous_dir"; fi
  echo "frontend_next:updated"
}
refresh_gateway_if_present() {
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    sudo docker compose -f "$FRONTEND_COMPOSE_FILE" up -d --no-deps --force-recreate gateway 2>/dev/null || true
    echo "gateway:refreshed"
  fi
}
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
upsert_env_value AUTH_COOKIE_SECURE "$AUTH_COOKIE_SECURE_VALUE"
upsert_env_value AUTH_ALLOW_INSECURE_HTTP_COOKIE false
upsert_env_value HTTPS_REQUIRED "$HTTPS_REQUIRED"
upsert_env_value WEB_RUNTIME_BACKGROUND_JOBS_ENABLED false
upsert_env_value FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED "$FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED"
upsert_env_value FRONTEND_NEXT_CUTOVER_PATHS "$FRONTEND_NEXT_CUTOVER_PATHS"
upsert_env_value MARKET_CLOSE_REVIEW_TIME "${MARKET_CLOSE_REVIEW_TIME:-15:05}"
if test -n "${DATA_QUALITY_SLA_ENABLED:-}"; then
  upsert_env_value DATA_QUALITY_SLA_ENABLED "$DATA_QUALITY_SLA_ENABLED"
fi
if embedded_scheduler_enabled; then
  upsert_env_value RUNTIME_WORKER_EMBED_SCHEDULER true
  upsert_env_value RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED false
fi
if test -n "$REMOTE_DEBIAN_APT_MIRROR"; then
  upsert_env_value DEBIAN_APT_MIRROR "$REMOTE_DEBIAN_APT_MIRROR"
fi
if test -n "$REMOTE_DEBIAN_APT_SECURITY_MIRROR"; then
  upsert_env_value DEBIAN_APT_SECURITY_MIRROR "$REMOTE_DEBIAN_APT_SECURITY_MIRROR"
fi
if test -n "$REMOTE_NODE_BASE_IMAGE"; then
  upsert_env_value NODE_BASE_IMAGE "$REMOTE_NODE_BASE_IMAGE"
fi
if test -n "$REMOTE_RUST_BASE_IMAGE"; then
  upsert_env_value RUST_BASE_IMAGE "$REMOTE_RUST_BASE_IMAGE"
fi
if test -n "$REMOTE_PYTHON_BASE_IMAGE"; then
  upsert_env_value PYTHON_BASE_IMAGE "$REMOTE_PYTHON_BASE_IMAGE"
fi

if has_unit db-migration && test "$DEPLOY_SCOPE" != all; then
  run_database_backup
  sudo docker compose -f "$DB_MIGRATION_COMPOSE_FILE" up --no-build --force-recreate --abort-on-container-exit --exit-code-from migration migration
  echo "db_migration:ok"
fi

if has_unit backend-api && test "$DEPLOY_SCOPE" != all; then
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    docker_compose_build "$BACKEND_API_COMPOSE_FILE" backend-api
    sudo docker compose -f "$BACKEND_API_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate backend-api
    echo "backend_api:updated"
  elif test "$DEPLOY_SCOPE" != all; then
    if ! use_prebuilt_app_images; then
      docker_compose_build "$CLOUD_COMPOSE_FILE" app
    fi
    sudo docker compose -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate app
    echo "backend_api:monolith_app_updated"
  fi
fi

if has_unit worker && test "$DEPLOY_SCOPE" != all; then
  if ! use_prebuilt_app_images; then
    docker_compose_build "$RUNTIME_COMPOSE_FILE" $(runtime_worker_services)
    if with_analytics_worker; then
      docker_compose_build "$RUNTIME_COMPOSE_FILE" analytics-worker
    fi
  fi
  stop_removed_backtest_worker
  stop_embedded_runtime_scheduler
  if with_analytics_worker; then
    sudo docker compose --profile analytics -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services) analytics-worker
  else
    sudo docker compose -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services)
  fi
  echo "workers:updated"
fi

if test "$DEPLOY_SCOPE" = all; then
  run_database_backup
  if ! use_prebuilt_app_images; then
    if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
      docker_compose_build "$BACKEND_API_COMPOSE_FILE" backend-api
    else
      docker_compose_build "$CLOUD_COMPOSE_FILE" app
    fi
    if with_analytics_worker; then
      docker_compose_build "$RUNTIME_COMPOSE_FILE" analytics-worker
    fi
  fi
  sudo docker compose -f "$DB_MIGRATION_COMPOSE_FILE" up --no-build --force-recreate --abort-on-container-exit --exit-code-from migration migration
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    sudo docker compose -f "$BACKEND_API_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate backend-api
    echo "backend_api:updated"
  else
    sudo docker rm -f tquant-app-mysql tquant-runtime-scheduler-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql 2>/dev/null || true
    if with_analytics_worker; then
      sudo docker rm -f tquant-analytics-worker-mysql 2>/dev/null || true
      stop_removed_backtest_worker
      stop_embedded_runtime_scheduler
      sudo docker compose --profile analytics -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate $(app_runtime_services) analytics-worker
    else
      stop_removed_backtest_worker
      stop_embedded_runtime_scheduler
      sudo docker compose -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate $(app_runtime_services)
    fi
    EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
    for container in $(web_image_containers); do
      ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
      if test "$ACTUAL_WEB_IMAGE" != "$EXPECTED_WEB_IMAGE"; then
        echo "$container is still running $ACTUAL_WEB_IMAGE; expected $EXPECTED_WEB_IMAGE" >&2
        exit 1
      fi
    done
    echo "web_image:updated"
  fi
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    if ! use_prebuilt_app_images; then
      docker_compose_build "$RUNTIME_COMPOSE_FILE" $(runtime_worker_services)
    fi
    stop_removed_backtest_worker
    stop_embedded_runtime_scheduler
    if with_analytics_worker; then
      sudo docker compose --profile analytics -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services) analytics-worker
    else
      sudo docker compose -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services)
    fi
    echo "workers:updated"
  fi
  if with_analytics_worker; then
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
  else
    echo "analytics_worker:skipped_on_demand"
  fi
  sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data && chown -R tquant:tquant /app/backend/data' || true
fi

if has_unit go; then
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
  if ! use_prebuilt_go_images; then
    docker_compose_build "$GO_COMPOSE_FILE" go-bff-gateway go-market-read-service go-scan-worker
  fi
  sudo docker compose -f "$GO_COMPOSE_FILE" up -d --no-build --force-recreate go-bff-gateway go-market-read-service go-scan-worker
  if test "$DEPLOY_SCOPE" = all && test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" != "separated"; then
    EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
    for container in $(web_image_containers); do
      ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
      if test "$ACTUAL_WEB_IMAGE" != "$EXPECTED_WEB_IMAGE"; then
        echo "$container changed away from web image after Go service deploy" >&2
        exit 1
      fi
    done
  fi
fi
if test "$DEPLOY_SCOPE" = all; then
  sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data/ml_models && chown -R tquant:tquant /app/backend/data' || true
fi
ls -dt /home/$CLOUD_USER/gupiao-deploy-backup-* 2>/dev/null | tail -n +$((CLOUD_KEEP_BACKUPS + 1)) | xargs -r sudo rm -rf
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
REMOTE
}

remote_deploy() {
  local package_path="$1"
  local remote_package="/home/${CLOUD_USER}/$(basename "$package_path")"
  local upload_seconds=0
  if [[ "$DEPLOY_RESOLVED_SCOPE" == "frontend-next" ]]; then
    log "upload frontend-next hot package to ${CLOUD_USER}@${CLOUD_HOST}:${remote_package}"
    local upload_start
    upload_start="$(date +%s)"
    if ! cloud_scp_to "$package_path" "$remote_package"; then
      return 1
    fi
    upload_seconds=$(( $(date +%s) - upload_start ))
    DEPLOY_DELTA_BYTES="$(file_size_bytes "$package_path")"
    log "hot update frontend-next dist without backend/db/worker restart"
    if ! cloud_ssh env \
      CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" \
      CLOUD_COMPOSE_FILE="$CLOUD_COMPOSE_FILE" \
      FRONTEND_COMPOSE_FILE="$FRONTEND_COMPOSE_FILE" \
      DEPLOY_COMPOSE_TOPOLOGY="$DEPLOY_COMPOSE_TOPOLOGY" \
      REMOTE_PACKAGE="$remote_package" \
      bash -s <<'REMOTE'
set -euo pipefail
TS=$(date +%Y%m%d%H%M%S)
WORK_DIR="/tmp/gupiao-frontend-next-hot-$TS"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
tar -xzf "$REMOTE_PACKAGE" -C "$WORK_DIR"
test -f "$WORK_DIR/dist/index.html"
cd "$CLOUD_PROJECT_DIR"
mkdir -p .runtime
if test -d frontend-next/dist; then
  rm -rf ".runtime/frontend-next-dist-backup-$TS"
  cp -a frontend-next/dist ".runtime/frontend-next-dist-backup-$TS" || true
fi
rm -rf frontend-next/dist
mkdir -p frontend-next/dist
cp -a "$WORK_DIR/dist/." frontend-next/dist/
if test -d ".runtime/frontend-next-dist-backup-$TS/assets" && test -d frontend-next/dist/assets; then
  cp -a ".runtime/frontend-next-dist-backup-$TS/assets/." frontend-next/dist/assets/
fi
chmod -R a+rX frontend-next/dist

frontend_web_compose_file() {
  if test -f "$FRONTEND_COMPOSE_FILE" && sudo docker compose -f "$FRONTEND_COMPOSE_FILE" ps frontend-web >/dev/null 2>&1; then
    printf '%s\n' "$FRONTEND_COMPOSE_FILE"
    return 0
  fi
  if test -f docker-compose.separated.yml && sudo docker compose -f docker-compose.separated.yml ps frontend-web >/dev/null 2>&1; then
    printf '%s\n' docker-compose.separated.yml
    return 0
  fi
  return 1
}

updated=0
if frontend_web_compose="$(frontend_web_compose_file)"; then
  sudo docker compose -f "$frontend_web_compose" up -d --no-deps --force-recreate frontend-web
  echo "frontend_next_hot:separated_frontend_web:$frontend_web_compose"
  updated=1
fi
if sudo docker inspect tquant-app-mysql >/dev/null 2>&1; then
  if sudo docker exec tquant-app-mysql test -d /app/frontend-next/dist/assets 2>/dev/null; then
    sudo docker cp tquant-app-mysql:/app/frontend-next/dist/assets "$WORK_DIR/container-assets" 2>/dev/null || true
    if test -d "$WORK_DIR/container-assets"; then
      mkdir -p frontend-next/dist/assets
      cp -a "$WORK_DIR/container-assets/." frontend-next/dist/assets/
    fi
  fi
  sudo docker exec -u root tquant-app-mysql sh -c 'rm -rf /app/frontend-next/dist && mkdir -p /app/frontend-next/dist'
  sudo docker cp frontend-next/dist/. tquant-app-mysql:/app/frontend-next/dist/
  sudo docker exec -u root tquant-app-mysql sh -c 'chmod -R a+rX /app/frontend-next/dist'
  echo "frontend_next_hot:monolith_compat"
  updated=1
fi
if test "$updated" != "1"; then
  echo "frontend_next_hot:no_running_target" >&2
  exit 1
fi
echo "frontend_next_hot:updated"
sudo rm -rf "$WORK_DIR"
rm -f "$REMOTE_PACKAGE"
REMOTE
    then
      return 1
    fi
    DEPLOY_UPLOAD_SECONDS="$upload_seconds"
    return 0
  fi

  if [[ "$DEPLOY_EFFECTIVE_SYNC_MODE" == "delta-package" ]]; then
    log "upload delta package to ${CLOUD_USER}@${CLOUD_HOST}:${remote_package}"
  else
    log "upload package to ${CLOUD_USER}@${CLOUD_HOST}:${remote_package}"
  fi
  local upload_start
  upload_start="$(date +%s)"
  if ! cloud_scp_to "$package_path" "$remote_package"; then
    return 1
  fi
  upload_seconds=$(( $(date +%s) - upload_start ))
  if [[ "$DEPLOY_EFFECTIVE_SYNC_MODE" == "delta-package" ]]; then
    DEPLOY_DELTA_BYTES="$(file_size_bytes "$package_path")"
  fi

  log "backup current release and deploy scope ${DEPLOY_RESOLVED_SCOPE}"
  if ! cloud_ssh env \
    CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" \
    CLOUD_COMPOSE_FILE="$CLOUD_COMPOSE_FILE" \
    BACKEND_API_COMPOSE_FILE="$BACKEND_API_COMPOSE_FILE" \
    FRONTEND_COMPOSE_FILE="$FRONTEND_COMPOSE_FILE" \
    DB_MIGRATION_COMPOSE_FILE="$DB_MIGRATION_COMPOSE_FILE" \
    RUNTIME_COMPOSE_FILE="$RUNTIME_COMPOSE_FILE" \
    GO_COMPOSE_FILE="$GO_COMPOSE_FILE" \
    CLOUD_USER="$CLOUD_USER" \
    CLOUD_KEEP_BACKUPS="$CLOUD_KEEP_BACKUPS" \
    CLOUD_AUTH_COOKIE_SECURE="${CLOUD_AUTH_COOKIE_SECURE:-}" \
    CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE="${CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE:-}" \
    FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED="$FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED" \
    FRONTEND_NEXT_CUTOVER_PATHS="$FRONTEND_NEXT_CUTOVER_PATHS" \
    DATA_QUALITY_SLA_ENABLED="$DATA_QUALITY_SLA_ENABLED" \
    REMOTE_PACKAGE="$remote_package" \
    DEPLOY_EFFECTIVE_SYNC_MODE="$DEPLOY_EFFECTIVE_SYNC_MODE" \
    DEPLOY_COMPOSE_TOPOLOGY="$DEPLOY_COMPOSE_TOPOLOGY" \
    REMOTE_DEBIAN_APT_MIRROR="$REMOTE_DEBIAN_APT_MIRROR" \
    REMOTE_DEBIAN_APT_SECURITY_MIRROR="$REMOTE_DEBIAN_APT_SECURITY_MIRROR" \
    REMOTE_NODE_BASE_IMAGE="$REMOTE_NODE_BASE_IMAGE" \
    REMOTE_RUST_BASE_IMAGE="$REMOTE_RUST_BASE_IMAGE" \
    REMOTE_PYTHON_BASE_IMAGE="$REMOTE_PYTHON_BASE_IMAGE" \
    DEPLOY_RESOLVED_SCOPE="$DEPLOY_RESOLVED_SCOPE" \
    HTTPS_REQUIRED="$HTTPS_REQUIRED" \
    DEPLOY_PREBUILT_IMAGES_ENABLED="$DEPLOY_PREBUILT_IMAGES_ENABLED" \
    DEPLOY_PREBUILT_WEB_IMAGE_REF="$DEPLOY_PREBUILT_WEB_IMAGE_REF" \
    DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF="$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" \
    DEPLOY_PREBUILT_GO_BFF_IMAGE_REF="$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" \
    DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF="$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" \
    DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF="$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" \
    DEPLOY_WITH_ANALYTICS_WORKER="$DEPLOY_WITH_ANALYTICS_WORKER" \
    DEPLOY_EMBED_RUNTIME_SCHEDULER="$DEPLOY_EMBED_RUNTIME_SCHEDULER" \
    bash -s <<'REMOTE'
set -euo pipefail
TS=$(date +%Y%m%d%H%M%S)
REQUIRED_PATHS="Dockerfile docker-compose.mysql.yml backend/app/main.py frontend-next/package.json frontend-next/src/index.tsx scripts/install_https_nginx.sh scripts/deploy_delta_package.py"
DEPLOY_SCOPE="${DEPLOY_RESOLVED_SCOPE:-all}"
SYNC_MODE="${DEPLOY_EFFECTIVE_SYNC_MODE:-package-only}"

require_release_paths() {
  local root="$1"
  local path
  for path in $REQUIRED_PATHS; do
    if ! test -e "$root/$path"; then
      echo "release package missing required path after extract: $path" >&2
      exit 1
    fi
  done
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  sed -i "/^${key}=/d" .env
  printf '%s=%s\n' "$key" "$value" >> .env
}

docker_compose_build() {
  local compose_file="$1"
  shift
  local log_file="/tmp/gupiao-docker-build-$TS.log"
  local attempt
  for attempt in 1 2 3; do
    if COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}" sudo -E docker compose -f "$compose_file" build "$@" 2>&1 | tee "$log_file"; then
      rm -f "$log_file"
      return 0
    fi
    if grep -Eqi 'TLS handshake timeout|failed to resolve source metadata|failed to do request|i/o timeout|connection reset by peer|temporary failure|context deadline exceeded|context canceled|no active session|DeadlineExceeded|BuildKit' "$log_file"; then
      if test "$attempt" -lt 3; then
        echo "docker build transient registry/buildkit failure; retrying attempt $((attempt + 1))/3" >&2
        sleep $((attempt * 5))
        continue
      fi
      echo "docker build transient failure persisted; retrying with classic builder" >&2
      COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}" DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 sudo -E docker compose -f "$compose_file" build "$@"
      rm -f "$log_file"
      return 0
    fi
    cat "$log_file" >&2
    rm -f "$log_file"
    return 1
  done
  cat "$log_file" >&2
  rm -f "$log_file"
  return 1
}

require_prebuilt_ref() {
  local name="$1"
  local value="$2"
  if test -z "$value"; then
    echo "prebuilt image mode requires $name" >&2
    exit 2
  fi
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
runtime_worker_services() {
  if embedded_scheduler_enabled; then
    printf 'runtime-worker'
  else
    printf 'runtime-scheduler runtime-worker'
  fi
}
app_runtime_services() {
  printf 'app '
  runtime_worker_services
}
web_image_containers() {
  printf 'tquant-app-mysql tquant-runtime-worker-mysql'
  if ! embedded_scheduler_enabled; then
    printf ' tquant-runtime-scheduler-mysql'
  fi
}
analytics_worker_services() {
  if with_analytics_worker; then
    printf ' %s' analytics-worker
  fi
}
stop_removed_backtest_worker() {
  sudo docker rm -f tquant-backtest-worker-mysql 2>/dev/null || true
}
stop_embedded_runtime_scheduler() {
  if embedded_scheduler_enabled; then
    sudo docker rm -f tquant-runtime-scheduler-mysql 2>/dev/null || true
  fi
}

use_prebuilt_app_images() {
  case "${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}" in
    1|true|yes)
      ;;
    auto)
      if test -z "${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"; then
        echo "prebuilt_images:app_unavailable_fallback_build"
        return 1
      fi
      if with_analytics_worker && test -z "${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"; then
        echo "prebuilt_images:analytics_unavailable_fallback_build"
        return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac
  require_prebuilt_ref DEPLOY_PREBUILT_WEB_IMAGE_REF "${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"
  if with_analytics_worker; then
    require_prebuilt_ref DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF "${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"
  fi
  echo "prebuilt_images:pull_app"
  sudo docker pull "$DEPLOY_PREBUILT_WEB_IMAGE_REF"
  sudo docker tag "$DEPLOY_PREBUILT_WEB_IMAGE_REF" tquant-web:mysql
  if with_analytics_worker; then
    sudo docker pull "$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF"
    sudo docker tag "$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" tquant-analytics:mysql
  fi
  echo "docker_build:skipped_prebuilt_app"
  return 0
}

use_prebuilt_go_images() {
  case "${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}" in
    1|true|yes)
      ;;
    auto)
      if test -z "${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}" || test -z "${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}" || test -z "${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"; then
        echo "prebuilt_images:go_unavailable_fallback_build"
        return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac
  require_prebuilt_ref DEPLOY_PREBUILT_GO_BFF_IMAGE_REF "${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}"
  require_prebuilt_ref DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF "${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}"
  require_prebuilt_ref DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF "${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"
  echo "prebuilt_images:pull_go"
  sudo docker pull "$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF"
  sudo docker pull "$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF"
  sudo docker pull "$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF"
  sudo docker tag "$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" tquant-go-bff:mysql
  sudo docker tag "$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" tquant-go-market-read:mysql
  sudo docker tag "$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" tquant-go-scan-worker:mysql
  echo "docker_build:skipped_prebuilt_go"
  return 0
}

DEPLOY_UNITS=" $DEPLOY_SCOPE "
case "$DEPLOY_SCOPE" in
  all)
    DEPLOY_UNITS=" all db-migration backend-api worker go frontend-next ops "
    ;;
  *)
    DEPLOY_UNITS=" $(printf '%s' "$DEPLOY_SCOPE" | tr ',' ' ') "
    ;;
esac
has_unit() {
  case "$DEPLOY_UNITS" in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}
frontend_web_compose_file() {
  if test -f "$FRONTEND_COMPOSE_FILE" && sudo docker compose -f "$FRONTEND_COMPOSE_FILE" ps frontend-web >/dev/null 2>&1; then
    printf '%s\n' "$FRONTEND_COMPOSE_FILE"
    return 0
  fi
  if test -f docker-compose.separated.yml && sudo docker compose -f docker-compose.separated.yml ps frontend-web >/dev/null 2>&1; then
    printf '%s\n' docker-compose.separated.yml
    return 0
  fi
  return 1
}
run_database_backup() {
  if test -f ./scripts/backup_database.sh; then
    BACKUP_TIME="${BACKUP_TIME:-02:20}" bash ./scripts/backup_database.sh || { echo "db_migration:backup_failed" >&2; exit 1; }
  else
    echo "db_migration:backup_script_missing" >&2
    exit 1
  fi
  echo "db_migration:backup_ok"
}
publish_frontend_next() {
  test -f frontend-next/dist/index.html
  previous_dir=""
  if sudo docker inspect tquant-app-mysql >/dev/null 2>&1 && sudo docker exec tquant-app-mysql test -d /app/frontend-next/dist/assets 2>/dev/null; then
    previous_dir="$(mktemp -d "/tmp/gupiao-frontend-next-prev-XXXXXX")"
    sudo docker cp tquant-app-mysql:/app/frontend-next/dist/assets "$previous_dir/assets" 2>/dev/null || true
  fi
  if test -n "$previous_dir" && test -d "$previous_dir/assets" && test -d frontend-next/dist/assets; then
    cp -a "$previous_dir/assets/." frontend-next/dist/assets/
  fi
  updated=0
  if frontend_web_compose="$(frontend_web_compose_file)"; then
    sudo docker compose -f "$frontend_web_compose" up -d --no-deps --force-recreate frontend-web
    echo "frontend_next:separated_frontend_web:$frontend_web_compose"
    updated=1
  fi
  if sudo docker inspect tquant-app-mysql >/dev/null 2>&1; then
    sudo docker exec -u root tquant-app-mysql sh -c 'rm -rf /app/frontend-next/dist && mkdir -p /app/frontend-next/dist'
    sudo docker cp frontend-next/dist/. tquant-app-mysql:/app/frontend-next/dist/
    sudo docker exec -u root tquant-app-mysql sh -c 'chmod -R a+rX /app/frontend-next/dist'
    echo "frontend_next:monolith_compat"
    updated=1
  fi
  if test "$updated" != "1"; then
    echo "frontend_next:no_running_target" >&2
    exit 1
  fi
  if test -n "$previous_dir"; then sudo rm -rf "$previous_dir"; fi
  echo "frontend_next:updated"
}
refresh_gateway_if_present() {
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    sudo docker compose -f "$FRONTEND_COMPOSE_FILE" up -d --no-deps --force-recreate gateway 2>/dev/null || true
    echo "gateway:refreshed"
  fi
}

cd /home/$CLOUD_USER
PROJECT_PARENT=$(dirname "$CLOUD_PROJECT_DIR")
sudo mkdir -p "$PROJECT_PARENT"
if test "$SYNC_MODE" = delta-package; then
  echo "deploy_sync:delta-package"
  if ! test -d "$CLOUD_PROJECT_DIR"; then
    echo "delta fallback required: release directory missing" >&2
    exit 42
  fi
  if ! test -f "$CLOUD_PROJECT_DIR/.runtime/deploy-manifest.json"; then
    echo "delta fallback required: manifest missing" >&2
    exit 42
  fi
  rm -rf gupiao-upload-delta-new
  mkdir gupiao-upload-delta-new
  cp -a "$CLOUD_PROJECT_DIR/." gupiao-upload-delta-new/
  tar -xzf "$REMOTE_PACKAGE" -C gupiao-upload-delta-new
  test -f gupiao-upload-delta-new/.deploy-delta/deploy-manifest.json
  test -f gupiao-upload-delta-new/.deploy-delta/deploy-delete-manifest.json
  python3 gupiao-upload-delta-new/scripts/deploy_delta_package.py apply-deletes \
    --root gupiao-upload-delta-new \
    --previous-manifest "$CLOUD_PROJECT_DIR/.runtime/deploy-manifest.json" \
    --delete-manifest gupiao-upload-delta-new/.deploy-delta/deploy-delete-manifest.json \
    --summary-output gupiao-upload-delta-new/.deploy-delta/delete-summary.json
  mkdir -p gupiao-upload-delta-new/.runtime
  cp gupiao-upload-delta-new/.deploy-delta/deploy-manifest.json gupiao-upload-delta-new/.runtime/deploy-manifest.json
  rm -rf gupiao-upload-delta-new/.deploy-delta
  require_release_paths gupiao-upload-delta-new
  sudo mv "$CLOUD_PROJECT_DIR" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS"
  sudo chown -R "$CLOUD_USER:$CLOUD_USER" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS" || true
  sudo mv gupiao-upload-delta-new "$CLOUD_PROJECT_DIR"
else
  echo "deploy_sync:package-only"
  rm -rf gupiao-upload-new
  mkdir gupiao-upload-new
  tar -xzf "$REMOTE_PACKAGE" -C gupiao-upload-new
  require_release_paths gupiao-upload-new
  if test -d "$CLOUD_PROJECT_DIR/.runtime"; then cp -a "$CLOUD_PROJECT_DIR/.runtime" gupiao-upload-new/.runtime || true; fi
  if test -f "$CLOUD_PROJECT_DIR/.env"; then cp -a "$CLOUD_PROJECT_DIR/.env" gupiao-upload-new/.env || true; fi
  if test -d "$CLOUD_PROJECT_DIR"; then
    sudo mv "$CLOUD_PROJECT_DIR" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS"
    sudo chown -R "$CLOUD_USER:$CLOUD_USER" "/home/$CLOUD_USER/gupiao-deploy-backup-$TS" || true
  fi
  sudo mv gupiao-upload-new "$CLOUD_PROJECT_DIR"
fi
sudo chown -R "$CLOUD_USER:$CLOUD_USER" "$CLOUD_PROJECT_DIR"
cd "$CLOUD_PROJECT_DIR"
touch .env
mkdir -p .runtime
if test "$SYNC_MODE" != delta-package; then
  python3 scripts/deploy_delta_package.py manifest --root . --output .runtime/deploy-manifest.json --quiet
fi
echo "deploy_manifest:updated"
echo "deploy_scope:$DEPLOY_SCOPE"
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
upsert_env_value AUTH_COOKIE_SECURE "$AUTH_COOKIE_SECURE_VALUE"
upsert_env_value AUTH_ALLOW_INSECURE_HTTP_COOKIE false
upsert_env_value HTTPS_REQUIRED "$HTTPS_REQUIRED"
upsert_env_value WEB_RUNTIME_BACKGROUND_JOBS_ENABLED false
upsert_env_value FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED "$FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED"
upsert_env_value FRONTEND_NEXT_CUTOVER_PATHS "$FRONTEND_NEXT_CUTOVER_PATHS"
upsert_env_value MARKET_CLOSE_REVIEW_TIME "${MARKET_CLOSE_REVIEW_TIME:-15:05}"
if test -n "${DATA_QUALITY_SLA_ENABLED:-}"; then
  upsert_env_value DATA_QUALITY_SLA_ENABLED "$DATA_QUALITY_SLA_ENABLED"
fi
if embedded_scheduler_enabled; then
  upsert_env_value RUNTIME_WORKER_EMBED_SCHEDULER true
  upsert_env_value RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED false
fi
if test -n "$REMOTE_DEBIAN_APT_MIRROR"; then
  upsert_env_value DEBIAN_APT_MIRROR "$REMOTE_DEBIAN_APT_MIRROR"
fi
if test -n "$REMOTE_DEBIAN_APT_SECURITY_MIRROR"; then
  upsert_env_value DEBIAN_APT_SECURITY_MIRROR "$REMOTE_DEBIAN_APT_SECURITY_MIRROR"
fi
if test -n "$REMOTE_NODE_BASE_IMAGE"; then
  upsert_env_value NODE_BASE_IMAGE "$REMOTE_NODE_BASE_IMAGE"
fi
if test -n "$REMOTE_RUST_BASE_IMAGE"; then
  upsert_env_value RUST_BASE_IMAGE "$REMOTE_RUST_BASE_IMAGE"
fi
if test -n "$REMOTE_PYTHON_BASE_IMAGE"; then
  upsert_env_value PYTHON_BASE_IMAGE "$REMOTE_PYTHON_BASE_IMAGE"
fi

if has_unit db-migration && test "$DEPLOY_SCOPE" != all; then
  run_database_backup
  sudo docker compose -f "$DB_MIGRATION_COMPOSE_FILE" up --no-build --force-recreate --abort-on-container-exit --exit-code-from migration migration
  echo "db_migration:ok"
fi

if has_unit backend-api && test "$DEPLOY_SCOPE" != all; then
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    docker_compose_build "$BACKEND_API_COMPOSE_FILE" backend-api
    sudo docker compose -f "$BACKEND_API_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate backend-api
    echo "backend_api:updated"
  elif test "$DEPLOY_SCOPE" != all; then
    if ! use_prebuilt_app_images; then
      docker_compose_build "$CLOUD_COMPOSE_FILE" app
    fi
    sudo docker compose -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate app
    echo "backend_api:monolith_app_updated"
  fi
fi

if has_unit worker && test "$DEPLOY_SCOPE" != all; then
  if ! use_prebuilt_app_images; then
    docker_compose_build "$RUNTIME_COMPOSE_FILE" $(runtime_worker_services)
    if with_analytics_worker; then
      docker_compose_build "$RUNTIME_COMPOSE_FILE" analytics-worker
    fi
  fi
  stop_removed_backtest_worker
  stop_embedded_runtime_scheduler
  if with_analytics_worker; then
    sudo docker compose --profile analytics -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services) analytics-worker
  else
    sudo docker compose -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services)
  fi
  echo "workers:updated"
fi

if test "$DEPLOY_SCOPE" = all; then
  run_database_backup
  if ! use_prebuilt_app_images; then
    if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
      docker_compose_build "$BACKEND_API_COMPOSE_FILE" backend-api
    else
      docker_compose_build "$CLOUD_COMPOSE_FILE" app
    fi
    if with_analytics_worker; then
      docker_compose_build "$RUNTIME_COMPOSE_FILE" analytics-worker
    fi
  fi
  sudo docker compose -f "$DB_MIGRATION_COMPOSE_FILE" up --no-build --force-recreate --abort-on-container-exit --exit-code-from migration migration
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    sudo docker compose -f "$BACKEND_API_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate backend-api
    echo "backend_api:updated"
  else
    sudo docker rm -f tquant-app-mysql tquant-runtime-scheduler-mysql tquant-runtime-worker-mysql tquant-backtest-worker-mysql 2>/dev/null || true
    if with_analytics_worker; then
      sudo docker rm -f tquant-analytics-worker-mysql 2>/dev/null || true
      stop_removed_backtest_worker
      stop_embedded_runtime_scheduler
      sudo docker compose --profile analytics -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate $(app_runtime_services) analytics-worker
    else
      stop_removed_backtest_worker
      stop_embedded_runtime_scheduler
      sudo docker compose -f "$CLOUD_COMPOSE_FILE" up -d --no-build --force-recreate $(app_runtime_services)
    fi
    EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
    for container in $(web_image_containers); do
      ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
      if test "$ACTUAL_WEB_IMAGE" != "$EXPECTED_WEB_IMAGE"; then
        echo "$container is still running $ACTUAL_WEB_IMAGE; expected $EXPECTED_WEB_IMAGE" >&2
        exit 1
      fi
    done
    echo "web_image:updated"
  fi
  if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated"; then
    if ! use_prebuilt_app_images; then
      docker_compose_build "$RUNTIME_COMPOSE_FILE" $(runtime_worker_services)
    fi
    stop_removed_backtest_worker
    stop_embedded_runtime_scheduler
    if with_analytics_worker; then
      sudo docker compose --profile analytics -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services) analytics-worker
    else
      sudo docker compose -f "$RUNTIME_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate $(runtime_worker_services)
    fi
    echo "workers:updated"
  fi
  if with_analytics_worker; then
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
  else
    echo "analytics_worker:skipped_on_demand"
  fi
  sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data && chown -R tquant:tquant /app/backend/data' || true
fi

if has_unit go; then
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
  if ! use_prebuilt_go_images; then
    docker_compose_build "$GO_COMPOSE_FILE" go-bff-gateway go-market-read-service go-scan-worker
  fi
  sudo docker compose -f "$GO_COMPOSE_FILE" up -d --no-build --force-recreate go-bff-gateway go-market-read-service go-scan-worker
  if test "$DEPLOY_SCOPE" = all && test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" != "separated"; then
    EXPECTED_WEB_IMAGE=$(sudo docker image inspect tquant-web:mysql --format '{{.Id}}')
    for container in $(web_image_containers); do
      ACTUAL_WEB_IMAGE=$(sudo docker inspect "$container" --format '{{.Image}}')
      if test "$ACTUAL_WEB_IMAGE" != "$EXPECTED_WEB_IMAGE"; then
        echo "$container changed away from web image after Go service deploy" >&2
        exit 1
      fi
    done
  fi
fi

if has_unit frontend-next && test "$DEPLOY_SCOPE" != all; then
  publish_frontend_next
fi

if test "$DEPLOY_SCOPE" = all; then
  publish_frontend_next
fi

if has_unit ops || test "$DEPLOY_SCOPE" = all; then
  refresh_gateway_if_present
fi

if test "$DEPLOY_SCOPE" = all; then
  sudo docker exec -u root tquant-app-mysql sh -c 'mkdir -p /app/backend/data/ml_models && chown -R tquant:tquant /app/backend/data' || true
fi
ls -dt /home/$CLOUD_USER/gupiao-deploy-backup-* 2>/dev/null | tail -n +$((CLOUD_KEEP_BACKUPS + 1)) | xargs -r sudo rm -rf
rm -f "$REMOTE_PACKAGE"
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
REMOTE
  then
    return 1
  fi
  DEPLOY_UPLOAD_SECONDS="$upload_seconds"
}

remote_configure_ops() {
  if [[ "$DEPLOY_RESOLVED_SCOPE" != "all" && "${DEPLOY_FORCE_OPS_CONFIG:-0}" != "1" ]] && ! deploy_scope_has_unit ops; then
    log "skip HTTPS/backup cron refresh for scope ${DEPLOY_RESOLVED_SCOPE}"
    return 0
  fi

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
  elif [[ "$REFRESH_HTTPS_CONFIG" == "1" ]]; then
    log "refresh remote nginx config when HTTPS site already exists"
    cloud_ssh "set -euo pipefail
cd '$CLOUD_PROJECT_DIR'
if test -n '$CLOUD_DOMAIN' -a -f /etc/nginx/sites-available/weisilianghua.conf; then
  sudo REQUIRE_EMAIL=0 DOMAIN='$CLOUD_DOMAIN' APP_PORT='$CLOUD_APP_PORT' ./scripts/install_https_nginx.sh
fi"
  else
    log "skip HTTPS/nginx config refresh"
  fi
}

verify_remote() {
  log "wait for container health"
  cloud_ssh env CLOUD_APP_PORT="$CLOUD_APP_PORT" CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" DEPLOY_WITH_ANALYTICS_WORKER="$DEPLOY_WITH_ANALYTICS_WORKER" DEPLOY_EMBED_RUNTIME_SCHEDULER="$DEPLOY_EMBED_RUNTIME_SCHEDULER" bash -s <<'REMOTE'
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
  for _ in $(seq 1 40); do
    status=$(sudo docker inspect "$name" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || echo none)
    echo "$name health:$status"
    case "$status" in
      healthy|running)
        return 0
        ;;
    esac
    sleep 3
  done
  echo "$name did not become healthy" >&2
  dump_container_diagnostics "$name"
  exit 1
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
for name in tquant-app-mysql tquant-runtime-worker-mysql; do
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
  sudo docker exec tquant-analytics-worker-mysql python - <<'PY'
import duckdb, pyarrow  # noqa: F401
from app.core.database import ping_database

ping_database()
print("analytics_worker_readyz:ok")
PY
else
  echo "analytics_worker:skipped_on_demand"
fi
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
REMOTE
}

verify_frontend_next_remote() {
  log "verify frontend-next static deployment"
  cloud_ssh env CLOUD_PROJECT_DIR="$CLOUD_PROJECT_DIR" DEPLOY_COMPOSE_TOPOLOGY="$DEPLOY_COMPOSE_TOPOLOGY" bash -s <<'REMOTE'
set -euo pipefail
cd "$CLOUD_PROJECT_DIR"
test -f frontend-next/dist/index.html
if sudo docker inspect tquant-frontend-web >/dev/null 2>&1; then
  STATUS=starting
  for _ in $(seq 1 30); do
    STATUS=$(sudo docker inspect tquant-frontend-web --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')
    echo "tquant-frontend-web health:$STATUS"
    case "$STATUS" in healthy|running) break ;; esac
    sleep 2
  done
  case "$STATUS" in healthy|running) ;; *) exit 1 ;; esac
  sudo docker exec tquant-frontend-web wget -qO- http://127.0.0.1/ >/tmp/frontend_next_home.html
  sudo docker exec tquant-frontend-web wget -qO- http://127.0.0.1/next/ >/tmp/frontend_next_route.html
else
  sudo docker inspect tquant-app-mysql >/dev/null
  sudo docker exec tquant-app-mysql test -f /app/frontend-next/dist/index.html
fi
echo "frontend_next_static:ok"
REMOTE
}

verify_backend_api_remote() {
  log "verify backend API deployment"
  cloud_ssh env CLOUD_APP_PORT="$CLOUD_APP_PORT" BACKEND_API_PORT="$BACKEND_API_PORT" DEPLOY_COMPOSE_TOPOLOGY="$DEPLOY_COMPOSE_TOPOLOGY" bash -s <<'REMOTE'
set -euo pipefail
if test "${DEPLOY_COMPOSE_TOPOLOGY:-monolith}" = "separated" && sudo docker inspect tquant-backend-api >/dev/null 2>&1; then
  STATUS=starting
  for _ in $(seq 1 30); do
    STATUS=$(sudo docker inspect tquant-backend-api --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')
    echo "tquant-backend-api health:$STATUS"
    case "$STATUS" in healthy|running) break ;; esac
    sleep 2
  done
  case "$STATUS" in healthy|running) ;; *) exit 1 ;; esac
  curl -sS -f --max-time 10 "http://127.0.0.1:${BACKEND_API_PORT:-18091}/readyz" >/tmp/gupiao_readyz.json
else
  STATUS=starting
  for _ in $(seq 1 30); do
    STATUS=$(sudo docker inspect tquant-app-mysql --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')
    echo "tquant-app-mysql health:$STATUS"
    case "$STATUS" in healthy|running) break ;; esac
    sleep 2
  done
  case "$STATUS" in healthy|running) ;; *) exit 1 ;; esac
  curl -sS -f --max-time 10 "http://127.0.0.1:${CLOUD_APP_PORT}/readyz" >/tmp/gupiao_readyz.json
fi
python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
print('backend_api_readyz:ok')
PY
REMOTE
}

verify_worker_remote() {
  log "verify worker deployment"
  cloud_ssh env DEPLOY_WITH_ANALYTICS_WORKER="$DEPLOY_WITH_ANALYTICS_WORKER" DEPLOY_EMBED_RUNTIME_SCHEDULER="$DEPLOY_EMBED_RUNTIME_SCHEDULER" bash -s <<'REMOTE'
set -euo pipefail
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
for name in tquant-runtime-worker-mysql; do
  STATUS=$(sudo docker inspect "$name" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || echo none)
  echo "$name health:$STATUS"
  case "$STATUS" in healthy|running) ;; *) exit 1 ;; esac
done
if embedded_scheduler_enabled; then
  echo "runtime_scheduler:embedded"
else
  STATUS=$(sudo docker inspect tquant-runtime-scheduler-mysql --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || echo none)
  echo "tquant-runtime-scheduler-mysql health:$STATUS"
  case "$STATUS" in healthy|running) ;; *) exit 1 ;; esac
fi
sudo docker rm -f tquant-backtest-worker-mysql 2>/dev/null || true
if with_analytics_worker; then
  STATUS=$(sudo docker inspect tquant-analytics-worker-mysql --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || echo none)
  echo "tquant-analytics-worker-mysql health:$STATUS"
  case "$STATUS" in healthy|running) ;; *) exit 1 ;; esac
  sudo docker exec tquant-analytics-worker-mysql python - <<'PY'
import duckdb, pyarrow  # noqa: F401
from app.core.database import ping_database

ping_database()
print("analytics_worker_readyz:ok")
PY
else
  echo "analytics_worker:skipped_on_demand"
fi
echo "workers:ok"
REMOTE
}

verify_deploy_scope_remote() {
  case "$DEPLOY_RESOLVED_SCOPE" in
    frontend-next)
      verify_frontend_next_remote
      return 0
      ;;
    backend-api)
      verify_backend_api_remote
      return 0
      ;;
    worker)
      verify_worker_remote
      return 0
      ;;
    db-migration)
      verify_backend_api_remote
      return 0
      ;;
    go)
      verify_go_remote
      return 0
      ;;
  esac
  if deploy_scope_has_unit backend-api; then
    verify_backend_api_remote
  fi
  if deploy_scope_has_unit worker; then
    verify_worker_remote
  fi
  if deploy_scope_has_unit frontend-next; then
    verify_frontend_next_remote
  fi
  if deploy_scope_has_unit go; then
    verify_go_remote
  fi
  if ! deploy_scope_has_unit backend-api && ! deploy_scope_has_unit worker && ! deploy_scope_has_unit frontend-next && ! deploy_scope_has_unit go; then
    verify_remote
  fi
}

verify_go_remote() {
  log "verify go services"
  cloud_ssh bash -s <<'REMOTE'
set -euo pipefail
dump_container_diagnostics() {
  local name="$1"
  echo "diagnostics:$name" >&2
  sudo docker inspect "$name" --format '{{json .State}}' 2>/dev/null >&2 || true
  sudo docker logs --tail=120 "$name" 2>/dev/null >&2 || true
}
for name in tquant-go-bff-gateway tquant-go-market-read-service tquant-go-scan-worker; do
  for _ in $(seq 1 30); do
    STATUS=$(sudo docker inspect "$name" --format '{{.State.Health.Status}}' 2>/dev/null || echo none)
    echo "$name health:$STATUS"
    if test "$STATUS" = healthy; then
      break
    fi
    sleep 2
  done
  if test "$STATUS" != healthy; then
    echo "$name did not become healthy" >&2
    dump_container_diagnostics "$name"
    exit 1
  fi
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

verify_https_remote() {
  if [[ -z "$CLOUD_DOMAIN" ]]; then
    return 0
  fi
  log "verify HTTPS nginx SNI loopback"
  cloud_ssh env CLOUD_DOMAIN="$CLOUD_DOMAIN" VERIFY_PUBLIC_DOMAIN="$VERIFY_PUBLIC_DOMAIN" bash -s <<'REMOTE'
set -euo pipefail
curl -k -sS -f --max-time 10 --resolve "${CLOUD_DOMAIN}:443:127.0.0.1" "https://${CLOUD_DOMAIN}/readyz" >/tmp/gupiao_https_sni_readyz.json
python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_https_sni_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
print('https_sni_loopback:ok')
PY
if test "$VERIFY_PUBLIC_DOMAIN" = "1"; then
  curl -k -sS -f --max-time 10 "https://${CLOUD_DOMAIN}/readyz" >/tmp/gupiao_public_domain_readyz.json
  python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_public_domain_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
print('public_domain:ok')
PY
else
  if curl -k -sS -f --max-time 10 "https://${CLOUD_DOMAIN}/readyz" >/tmp/gupiao_public_domain_readyz.json; then
    python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_public_domain_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
print('public_domain:ok')
PY
  else
    echo "public_domain:warning"
  fi
fi
REMOTE
}

verify_latest_data_remote() {
  if [[ "$RUN_LATEST_DATA_ACCEPTANCE" != "1" ]]; then
    return 0
  fi
  if [[ "$DEPLOY_RESOLVED_SCOPE" != "all" && "${RUN_LATEST_DATA_ACCEPTANCE_FORCE:-0}" != "1" ]]; then
    log "skip latest low-buy data closure for scope ${DEPLOY_RESOLVED_SCOPE}"
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
  validate_deploy_sync_mode
  require_cloud_host
  require_https_config
  resolve_deploy_scope
  log "resolved deploy scope: ${DEPLOY_RESOLVED_SCOPE}"
  log "requested deploy sync mode: ${DEPLOY_SYNC_MODE}"
  run_local_checks
  ensure_frontend_next_artifact
  local package_path=""
  if remote_deploy_from_git; then
    DEPLOY_EFFECTIVE_SYNC_MODE="$DEPLOY_SYNC_MODE"
    log "remote git sync deploy completed"
  else
    if [[ "$DEPLOY_RESOLVED_SCOPE" != "frontend-next" && ( "$DEPLOY_SYNC_MODE" == "git-inplace" || "$DEPLOY_SYNC_MODE" == "git-clone" ) ]] && ! deploy_scope_has_unit frontend-next; then
      log "remote git sync unavailable; falling back to package upload"
      DEPLOY_DELTA_FALLBACK_REASON="remote_git_sync_unavailable"
    fi
    prepare_deploy_package
    package_path="$DEPLOY_PACKAGE_PATH"
    if ! remote_deploy "$package_path"; then
      if [[ "$DEPLOY_EFFECTIVE_SYNC_MODE" != "delta-package" ]]; then
        return 1
      fi
      log "delta package deploy failed; falling back to full package upload"
      rm -f "$package_path"
      DEPLOY_DELTA_FALLBACK_REASON="remote_delta_apply_failed"
      DEPLOY_EFFECTIVE_SYNC_MODE="package-only"
      DEPLOY_PACKAGE_PATH="$(make_package | tail -n 1)"
      package_path="$DEPLOY_PACKAGE_PATH"
      DEPLOY_DELTA_FULL_BYTES="$(file_size_bytes "$package_path")"
      remote_deploy "$package_path"
    fi
  fi
  log_sync_metrics
  remote_configure_ops
  verify_deploy_scope_remote
  verify_https_remote
  verify_latest_data_remote
  if [[ -n "$package_path" ]]; then
    rm -f "$package_path"
  fi
  log "done: http://${CLOUD_HOST}:${CLOUD_APP_PORT} / https://${CLOUD_DOMAIN}"
}

main "$@"
