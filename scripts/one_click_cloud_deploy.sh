#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

DEFAULT_CLOUD_HOST="${DEFAULT_CLOUD_HOST:-43.143.243.97}"
DEFAULT_CLOUD_USER="${DEFAULT_CLOUD_USER:-ubuntu}"
DEFAULT_CLOUD_DOMAIN="${DEFAULT_CLOUD_DOMAIN:-weisilianghua.cloud}"
DEFAULT_CLOUD_CERT_EMAIL="${DEFAULT_CLOUD_CERT_EMAIL:-admin@${DEFAULT_CLOUD_DOMAIN}}"
DEFAULT_CLOUD_SSH_KEY="${DEFAULT_CLOUD_SSH_KEY:-$HOME/Downloads/gupiao.pem}"

usage() {
  cat <<'EOF'
Usage: scripts/one_click_cloud_deploy.sh [--full] [--verify-only] [--refresh-https-config] [--configure-https] [--public-domain-verify]

One-click defaults:
  host   43.143.243.97
  user   ubuntu
  key    ~/Downloads/gupiao.pem
  domain weisilianghua.cloud

Override with CLOUD_HOST, CLOUD_USER, CLOUD_SSH_KEY, CLOUD_DOMAIN, CLOUD_CERT_EMAIL.
Additional args are passed through to scripts/quick_cloud_deploy.sh.
EOF
}

args=()
explicit_mode=0
explicit_key=0
for arg in "$@"; do
  case "$arg" in
    --help|-h)
      usage
      exit 0
      ;;
    --full|--fast-risk-accepted|--verify-only)
      explicit_mode=1
      args+=("$arg")
      ;;
    --key)
      explicit_key=1
      args+=("$arg")
      ;;
    *)
      args+=("$arg")
      ;;
  esac
done

if [[ "$explicit_mode" == "0" ]]; then
  args=(--fast-risk-accepted "${args[@]}")
fi

export CLOUD_HOST="${CLOUD_HOST:-$DEFAULT_CLOUD_HOST}"
export CLOUD_USER="${CLOUD_USER:-$DEFAULT_CLOUD_USER}"
export CLOUD_SSH_KEY="${CLOUD_SSH_KEY:-$DEFAULT_CLOUD_SSH_KEY}"
export CLOUD_DOMAIN="${CLOUD_DOMAIN:-$DEFAULT_CLOUD_DOMAIN}"
export CLOUD_CERT_EMAIL="${CLOUD_CERT_EMAIL:-$DEFAULT_CLOUD_CERT_EMAIL}"
export CLOUD_SSH_TIMEOUT="${CLOUD_SSH_TIMEOUT:-2400}"
export CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-15}"

if [[ "$explicit_key" == "0" && ! -f "$CLOUD_SSH_KEY" ]]; then
  echo "[one-click-deploy] ssh key not found: $CLOUD_SSH_KEY" >&2
  echo "[one-click-deploy] set CLOUD_SSH_KEY or pass --key to quick_cloud_deploy.sh." >&2
  exit 2
fi

printf '[one-click-deploy] target=%s@%s domain=%s mode=%s\n' \
  "$CLOUD_USER" "$CLOUD_HOST" "$CLOUD_DOMAIN" "${args[*]:-safe}"

exec "$ROOT_DIR/scripts/quick_cloud_deploy.sh" "${args[@]}"
