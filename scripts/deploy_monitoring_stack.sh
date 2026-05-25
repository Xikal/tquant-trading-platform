#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${CLOUD_HOST:-}"
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

if [[ -z "$REMOTE_HOST" ]]; then
  echo "CLOUD_HOST is required. Example: CLOUD_HOST=<server-ip-or-domain> $0" >&2
  exit 2
fi

ssh_opts=(-o StrictHostKeyChecking=no -i "${SSH_KEY}")

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "cd '${REMOTE_DIR}' && bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail
mkdir -p .runtime/prometheus
if [[ ! -f .env ]]; then
  echo ".env not found in remote deploy dir" >&2
  exit 3
fi
admin_token="$(grep -E '^ADMIN_API_TOKEN=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r' || true)"
if [[ -z "${admin_token}" ]]; then
  admin_token="$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  sed -i '/^ADMIN_API_TOKEN=/d' .env
  printf 'ADMIN_API_TOKEN=%s\n' "${admin_token}" >> .env
fi
umask 077
tmp_token="$(mktemp)"
printf '%s' "${admin_token}" > "${tmp_token}"
sudo install -m 0444 "${tmp_token}" .runtime/prometheus/tquant_admin_token
rm -f "${tmp_token}"
REMOTE_SCRIPT

grafana_password_b64="$(printf '%s' "${GRAFANA_PASSWORD}" | base64 | tr -d '\n')"
ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && umask 077 && printf '%s' '${grafana_password_b64}' | base64 -d > .runtime/grafana_admin_password"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && sudo env GRAFANA_ADMIN_PASSWORD=\"\$(printf '%s' '${grafana_password_b64}' | base64 -d)\" docker compose -f docker-compose.monitoring.yml up -d"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && sudo docker compose -f docker-compose.mysql.yml up -d app runtime-worker backtest-worker"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "curl -fsS http://127.0.0.1:${PROMETHEUS_PORT:-19090}/-/ready >/dev/null && curl -fsS http://127.0.0.1:${GRAFANA_PORT:-13000}/api/health >/dev/null"

ssh "${ssh_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "python3 - <<'PY'
import json
import sys
import urllib.request

url = 'http://127.0.0.1:${PROMETHEUS_PORT:-19090}/api/v1/targets'
with urllib.request.urlopen(url, timeout=8) as response:
    payload = json.loads(response.read().decode('utf-8'))

targets = payload.get('data', {}).get('activeTargets', [])
matches = [
    target
    for target in targets
    if target.get('labels', {}).get('job') == 'tquant-api'
]
if not matches:
    print('Prometheus target tquant-api is missing', file=sys.stderr)
    sys.exit(4)
down = [target for target in matches if target.get('health') != 'up']
if down:
    details = [
        {
            'health': target.get('health'),
            'scrapeUrl': target.get('scrapeUrl'),
            'lastError': target.get('lastError'),
        }
        for target in down
    ]
    print('Prometheus target tquant-api is not up: ' + json.dumps(details, ensure_ascii=False), file=sys.stderr)
    sys.exit(5)
PY"

echo "monitoring stack deployed and verified"
