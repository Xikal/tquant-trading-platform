#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${CLOUD_HOST:-43.143.243.97}"
REMOTE_USER="${CLOUD_USER:-ubuntu}"
REMOTE_DIR="${CLOUD_REMOTE_DIR:-/home/ubuntu/gupiao-upload}"
SSH_KEY="${CLOUD_SSH_KEY:-/Users/j/Downloads/gupiao.pem}"
GRAFANA_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-}"
if [[ -z "${GRAFANA_PASSWORD}" ]]; then
  GRAFANA_PASSWORD="$(openssl rand -base64 24 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
fi

ssh_opts=(-o StrictHostKeyChecking=no -i "${SSH_KEY}")

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "cd '${REMOTE_DIR}' && bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail
mkdir -p .runtime/prometheus
if [[ ! -f .env ]]; then
  echo ".env not found in remote deploy dir" >&2
  exit 3
fi
admin_token="$(grep -E '^ADMIN_API_TOKEN=' .env | tail -n 1 | cut -d= -f2- | tr -d '\r')"
if [[ -z "${admin_token}" ]]; then
  echo "ADMIN_API_TOKEN is empty; cannot scrape protected /metrics" >&2
  exit 4
fi
umask 077
printf '%s' "${admin_token}" > .runtime/prometheus/tquant_admin_token
REMOTE_SCRIPT

grafana_password_b64="$(printf '%s' "${GRAFANA_PASSWORD}" | base64 | tr -d '\n')"
ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && umask 077 && printf '%s' '${grafana_password_b64}' | base64 -d > .runtime/grafana_admin_password"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && GRAFANA_ADMIN_PASSWORD=\"\$(printf '%s' '${grafana_password_b64}' | base64 -d)\" sudo docker compose -f docker-compose.monitoring.yml up -d"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "curl -fsS http://127.0.0.1:${PROMETHEUS_PORT:-19090}/-/ready >/dev/null && curl -fsS http://127.0.0.1:${GRAFANA_PORT:-13000}/api/health >/dev/null"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "curl -fsS http://127.0.0.1:${PROMETHEUS_PORT:-19090}/api/v1/targets | grep -q 'tquant-api'"

echo "monitoring stack deployed and verified"
