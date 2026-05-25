#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/cloud_ssh_lib.sh"

CLOUD_HOST="${CLOUD_HOST:-}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_PROJECT_DIR="${CLOUD_PROJECT_DIR:-/home/ubuntu/gupiao-upload}"
KEEP_BACKUPS="${KEEP_BACKUPS:-3}"
KEEP_REPORT_DIRS="${KEEP_REPORT_DIRS:-1}"
APPLY="${APPLY:-0}"
PRUNE_DOCKER="${PRUNE_DOCKER:-1}"

log() {
  printf '[cleanup] %s\n' "$*"
}

require_cloud_host() {
  if [[ -n "$CLOUD_HOST" ]]; then
    return 0
  fi
  log "CLOUD_HOST is required. Example: CLOUD_HOST=<server-ip-or-domain> $0"
  exit 2
}

remote_script() {
  cat <<'SH'
set -euo pipefail

PROJECT_DIR="${CLOUD_PROJECT_DIR}"
KEEP_BACKUPS="${KEEP_BACKUPS}"
KEEP_REPORT_DIRS="${KEEP_REPORT_DIRS}"
APPLY="${APPLY}"
PRUNE_DOCKER="${PRUNE_DOCKER}"

run_or_echo() {
  if [[ "$APPLY" == "1" ]]; then
    echo "+ $*"
    eval "$@"
  else
    echo "[dry-run] $*"
  fi
}

echo "[disk before]"
df -h /
echo
echo "[largest home entries]"
du -sh /home/ubuntu/* 2>/dev/null | sort -h | tail -30
echo
echo "[docker usage]"
sudo docker system df || true
echo

echo "[cleanup candidates]"
find /home/ubuntu -maxdepth 1 -type f \( -name 'gupiao-deploy-*.tgz' -o -name 'gupiao_remote_verify*.sh' \) -print

echo
echo "[remove upload packages and temporary verify scripts]"
run_or_echo "find /home/ubuntu -maxdepth 1 -type f \\( -name 'gupiao-deploy-*.tgz' -o -name 'gupiao_remote_verify*.sh' \\) -delete"

echo
echo "[keep latest deploy backups]"
mapfile -t OLD_BACKUPS < <(ls -dt /home/ubuntu/gupiao-deploy-backup-* 2>/dev/null | tail -n +"$((KEEP_BACKUPS + 1))" || true)
printf '%s\n' "${OLD_BACKUPS[@]}"
if [[ "${#OLD_BACKUPS[@]}" -gt 0 ]]; then
  if [[ "$APPLY" == "1" ]]; then
    rm -rf "${OLD_BACKUPS[@]}"
  else
    printf '[dry-run] rm -rf %s\n' "${OLD_BACKUPS[@]}"
  fi
fi

echo
echo "[remove legacy hot-patch upload backups]"
mapfile -t LEGACY_UPLOAD_BACKUPS < <(find /home/ubuntu -maxdepth 1 -type d \( -name 'gupiao-upload.prev*' -o -name 'gupiao-upload-backup-*' \) -print | sort || true)
printf '%s\n' "${LEGACY_UPLOAD_BACKUPS[@]}"
if [[ "${#LEGACY_UPLOAD_BACKUPS[@]}" -gt 0 ]]; then
  if [[ "$APPLY" == "1" ]]; then
    rm -rf "${LEGACY_UPLOAD_BACKUPS[@]}"
  else
    printf '[dry-run] rm -rf %s\n' "${LEGACY_UPLOAD_BACKUPS[@]}"
  fi
fi

echo
echo "[keep latest report directories by family]"
for pattern in backtest_reports baseline_reports full_backfill_reports full_backfill_v2_reports; do
  mapfile -t OLD_DIRS < <(ls -dt /home/ubuntu/${pattern}* 2>/dev/null | tail -n +"$((KEEP_REPORT_DIRS + 1))" || true)
  if [[ "${#OLD_DIRS[@]}" -gt 0 ]]; then
    printf '%s\n' "${OLD_DIRS[@]}"
    if [[ "$APPLY" == "1" ]]; then
      rm -rf "${OLD_DIRS[@]}"
    else
      printf '[dry-run] rm -rf %s\n' "${OLD_DIRS[@]}"
    fi
  fi
done

echo
echo "[docker prune build cache and dangling images]"
if [[ "$PRUNE_DOCKER" == "1" ]]; then
  run_or_echo "sudo docker builder prune -f"
  run_or_echo "sudo docker image prune -f"
fi

echo
echo "[safety checks]"
test -d "$PROJECT_DIR"
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
curl -sS -f --max-time 10 http://127.0.0.1:18090/readyz >/tmp/gupiao_cleanup_readyz.json
python3 - <<'PY'
import json
payload = json.load(open('/tmp/gupiao_cleanup_readyz.json', encoding='utf-8'))
assert payload.get('status') == 'ok', payload
assert payload.get('checks', {}).get('database') is True, payload
print('readyz:ok')
PY

echo
echo "[disk after]"
df -h /
echo
echo "[largest home entries after]"
du -sh /home/ubuntu/* 2>/dev/null | sort -h | tail -30
SH
}

main() {
  require_cloud_host
  log "mode: $([[ "$APPLY" == "1" ]] && echo apply || echo dry-run)"
  local local_script remote_path
  local_script="$(mktemp /tmp/gupiao-cloud-cleanup-XXXXXX)"
  remote_path="/home/${CLOUD_USER}/gupiao-cloud-cleanup.sh"
  remote_script >"$local_script"
  chmod +x "$local_script"
  cloud_scp_to "$local_script" "$remote_path"
  cloud_ssh "CLOUD_PROJECT_DIR='$CLOUD_PROJECT_DIR' KEEP_BACKUPS='$KEEP_BACKUPS' KEEP_REPORT_DIRS='$KEEP_REPORT_DIRS' APPLY='$APPLY' PRUNE_DOCKER='$PRUNE_DOCKER' bash '$remote_path'; rm -f '$remote_path'"
  rm -f "$local_script"
}

main "$@"
