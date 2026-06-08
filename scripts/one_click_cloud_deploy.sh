#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-$ROOT_DIR/.env.deploy.local}"

DEFAULT_CLOUD_USER="${DEFAULT_CLOUD_USER:-ubuntu}"
DEFAULT_CLOUD_DOMAIN="${DEFAULT_CLOUD_DOMAIN:-weisilianghua.cloud}"
DEFAULT_DEPLOY_MODE="${DEFAULT_DEPLOY_MODE:-safe}"

usage() {
  cat <<'EOF'
Usage: scripts/one_click_cloud_deploy.sh [--safe|--fast|--full|--verify-only] [--scope <auto|frontend-next|frontend-legacy|backend-api|db-migration|worker|go|ops|all>] [quick deploy options]

Config:
  Reads .env.deploy.local by default when present. Override with DEPLOY_ENV_FILE.
  Required: CLOUD_HOST plus CLOUD_SSH_KEY or CLOUD_PASSWORD.
  Optional: CLOUD_USER, CLOUD_DOMAIN, CLOUD_CERT_EMAIL, CLOUD_PROJECT_DIR.

Modes:
  --safe   Default. Run quick deploy with local compile/build gates and auto scope.
  --fast   Explicit emergency path; maps to --fast-risk-accepted.
  --full   Run full local checks and latest-data acceptance.
  --scope  Override target selection. auto is default; frontend-next deploys static assets only.
  --frontend-next-required
           Fail instead of falling back when frontend-next dist is missing.
  --changed-files-from <file>
           Pass newline-separated changed files to auto scope resolver.
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
           Choose deploy sync mode. delta-package falls back to package-only.
  --verify-only
  --dry-run

One-click defaults refresh HTTPS/nginx config and verify the default public entry.
The public entry defaults to https://<CLOUD_HOST>; CLOUD_DOMAIN is kept for
certificate/nginx configuration and can still be verified explicitly with
--public-domain-verify.
Additional args are passed through to scripts/quick_cloud_deploy.sh.
EOF
}

load_deploy_env() {
  if [[ ! -f "$DEPLOY_ENV_FILE" ]]; then
    return 0
  fi
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV_FILE"
  set +a
  printf '[one-click-deploy] env=%s\n' "$DEPLOY_ENV_FILE"
}

require_connection_config() {
  if [[ -z "${CLOUD_HOST:-}" ]]; then
    echo "[one-click-deploy] CLOUD_HOST is required. Put it in .env.deploy.local or export it." >&2
    exit 2
  fi
  if [[ -z "${CLOUD_SSH_KEY:-}" && -z "${CLOUD_PASSWORD:-}" ]]; then
    echo "[one-click-deploy] CLOUD_SSH_KEY or CLOUD_PASSWORD is required." >&2
    exit 2
  fi
  if [[ -n "${CLOUD_SSH_KEY:-}" && ! -f "$CLOUD_SSH_KEY" ]]; then
    echo "[one-click-deploy] ssh key not found: $CLOUD_SSH_KEY" >&2
    echo "[one-click-deploy] set CLOUD_SSH_KEY in .env.deploy.local or pass --key to quick_cloud_deploy.sh." >&2
    exit 2
  fi
}

load_deploy_env

args=()
explicit_mode=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --safe)
      explicit_mode=1
      shift
      ;;
    --fast)
      explicit_mode=1
      args+=(--fast-risk-accepted)
      shift
      ;;
    --full|--fast-risk-accepted|--verify-only)
      explicit_mode=1
      args+=("$1")
      shift
      ;;
    --host)
      CLOUD_HOST="${2:?missing host}"
      args+=("$1" "$2")
      shift 2
      ;;
    --user)
      CLOUD_USER="${2:?missing user}"
      args+=("$1" "$2")
      shift 2
      ;;
    --key)
      CLOUD_SSH_KEY="${2:?missing key}"
      args+=("$1" "$2")
      shift 2
      ;;
    --project-dir)
      CLOUD_PROJECT_DIR="${2:?missing project dir}"
      args+=("$1" "$2")
      shift 2
      ;;
    --scope)
      args+=("$1" "${2:?missing scope}")
      shift 2
      ;;
    --changed-files-from|--compose-topology|--backend-api-compose-file|--frontend-compose-file|--db-migration-compose-file|--runtime-compose-file|--go-compose-file)
      args+=("$1" "${2:?missing value}")
      shift 2
      ;;
    --frontend-next-required)
      args+=("$1")
      shift
      ;;
    --sync-mode)
      DEPLOY_SYNC_MODE="${2:?missing sync mode}"
      args+=("$1" "$2")
      shift 2
      ;;
    --port)
      CLOUD_APP_PORT="${2:?missing port}"
      args+=("$1" "$2")
      shift 2
      ;;
    --public-base-url)
      CLOUD_PUBLIC_BASE_URL="${2:?missing public base url}"
      args+=("$1" "$2")
      shift 2
      ;;
    --dry-run)
      ONE_CLICK_DEPLOY_DRY_RUN=1
      shift
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ "$explicit_mode" == "0" ]]; then
  case "$DEFAULT_DEPLOY_MODE" in
    safe)
      ;;
    fast)
      args=(--fast-risk-accepted "${args[@]}")
      ;;
    full)
      args=(--full "${args[@]}")
      ;;
    *)
      echo "[one-click-deploy] invalid DEFAULT_DEPLOY_MODE=$DEFAULT_DEPLOY_MODE" >&2
      exit 2
      ;;
  esac
fi

args_text="${args[*]-}"

if [[ "$explicit_mode" == "0" || "$args_text" != *"--verify-only"* ]]; then
  if [[ "$args_text" != *"--refresh-https-config"* && "$args_text" != *"--configure-https"* ]]; then
    args+=(--refresh-https-config)
  fi
fi

export CLOUD_USER="${CLOUD_USER:-$DEFAULT_CLOUD_USER}"
export CLOUD_DOMAIN="${CLOUD_DOMAIN:-$DEFAULT_CLOUD_DOMAIN}"
export CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-admin@${CLOUD_DOMAIN}}"
export CLOUD_PUBLIC_BASE_URL="${CLOUD_PUBLIC_BASE_URL:-https://${CLOUD_HOST:-}}"
export CLOUD_SSH_TIMEOUT="${CLOUD_SSH_TIMEOUT:-2400}"
export CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-30}"
export DEPLOY_SYNC_MODE="${DEPLOY_SYNC_MODE:-package-only}"

if [[ "${ONE_CLICK_DEPLOY_DRY_RUN:-0}" == "1" ]]; then
  CLOUD_HOST="${CLOUD_HOST:-dry-run-host}"
  if [[ -z "${CLOUD_SSH_KEY:-}" && -z "${CLOUD_PASSWORD:-}" ]]; then
    CLOUD_PASSWORD="dry-run-password"
  fi
else
  require_connection_config
fi

printf '[one-click-deploy] target=%s@%s domain=%s mode=%s sync_mode=%s ssh=%s\n' \
  "$CLOUD_USER" "$CLOUD_HOST" "$CLOUD_DOMAIN" "${args[*]:-safe}" \
  "$DEPLOY_SYNC_MODE" \
  "$(if [[ -n "${CLOUD_SSH_KEY:-}" ]]; then printf 'key'; elif [[ -n "${CLOUD_PASSWORD:-}" ]]; then printf 'password'; else printf 'none'; fi)"

if [[ "${ONE_CLICK_DEPLOY_DRY_RUN:-0}" == "1" ]]; then
  printf '[one-click-deploy] dry-run sync_mode=%s args=%s\n' "$DEPLOY_SYNC_MODE" "${args[*]:-safe}"
  exit 0
fi

DEPLOY_SYNC_MODE="$DEPLOY_SYNC_MODE" exec "$ROOT_DIR/scripts/quick_cloud_deploy.sh" "${args[@]}"
