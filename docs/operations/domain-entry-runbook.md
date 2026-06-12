# Domain Entry Runbook

## Scope

Use this runbook for domain, TLS, SNI, nginx, CDN/WAF, and public entry issues. It is separate from cloud resource-contention work. Do not mix domain-entry changes with scheduler cutover, worker tuning, MySQL tuning, Docker cleanup, or strategy changes.

## Protected Boundaries

- Do not edit `backend/app/services/low_buy/strategy_policy.py`.
- Do not change `production_score`.
- Do not change priority-board ordering or response semantics.
- Do not restart MySQL, Redis, Web/API, Go hot-read, Go scan, or core runtime-worker as part of domain diagnosis.
- Do not reload nginx, change DNS, or switch CDN/WAF until the current read-only checks and backup plan are recorded.

## Current Known Symptom

The 2026-06-12 D7 review found that direct IP HTTPS can return `200`, while `https://weisilianghua.cloud/readyz` can reset during TLS ClientHello from at least one external client path. Server-side curls to the same domain returned `200`, so this should be treated as a public entry/SNI/network path issue, not as a FastAPI, MySQL, runtime-worker, or Docker resource issue.

Evidence report:

- `docs/reports/domain-entry-tls-reset-review-2026-06-12.md`

## Read-Only Diagnosis

Run these from a local external client:

```bash
curl -vk --max-time 15 https://weisilianghua.cloud/readyz
curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 --max-time 15 https://weisilianghua.cloud/readyz
curl -k -v --max-time 15 https://43.143.243.97/readyz
```

Run these on the server:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
date
curl -vk --max-time 15 https://weisilianghua.cloud/readyz
curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 --max-time 15 https://weisilianghua.cloud/readyz
curl -k -v --max-time 15 https://43.143.243.97/readyz
sudo nginx -t
sudo nginx -T 2>/dev/null | grep -n "server_name .*weisilianghua.cloud" || true
sudo nginx -T 2>/dev/null | grep -n "ssl_certificate" || true
'
```

Expected interpretation:

- Domain reset locally but IP HTTPS works: public domain/SNI path issue.
- Domain works server-side but resets externally: external network, cloud security, edge, WAF/CDN, or SNI path issue.
- Duplicate `server_name` blocks: nginx cleanup candidate, but requires backup and review before reload.
- `nginx -t` failure: P1 config risk; do not reload.

## Authorized Fix Plan

Only run this plan after explicit authorization.

1. Back up nginx enabled-site and available-site files.
2. Capture current cert paths and server blocks.
3. Consolidate duplicate `server_name weisilianghua.cloud www.weisilianghua.cloud` blocks into one canonical TLS server block.
4. Keep the canonical block pointed at the existing upstream port and certificate unless cert evidence proves otherwise.
5. Run `sudo nginx -t`.
6. Reload nginx only after `nginx -t` passes.
7. Re-test from at least two external networks plus server-side curl.
8. If resets remain, check cloud security group, CDN/WAF, domain ICP/edge policy, and TCP 443 path with the cloud vendor.

## Example Backup And Review Commands

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_DIR="$HOME/nginx-domain-entry-backup-$STAMP"
mkdir -p "$BACKUP_DIR"
sudo cp -a /etc/nginx/sites-enabled "$BACKUP_DIR/sites-enabled"
sudo cp -a /etc/nginx/sites-available "$BACKUP_DIR/sites-available"
sudo nginx -T > "$BACKUP_DIR/nginx-T.txt" 2>&1
echo "$BACKUP_DIR"
'
```

Do not reload from this step. It only captures state for review.

## Post-Change Verification

```bash
curl -vk --max-time 15 https://weisilianghua.cloud/readyz
curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 --max-time 15 https://weisilianghua.cloud/readyz
curl -k -v --max-time 15 https://43.143.243.97/readyz
curl -sS -o /tmp/monitor.html -w "monitor %{http_code} %{time_total}\n" --max-time 20 https://weisilianghua.cloud/next/monitor
```

Acceptance:

- `/readyz` returns `200` through domain and direct IP.
- `/next/monitor` returns `200` through domain.
- No TLS reset from the tested external networks.
- No nginx syntax error.
- No container, DB, scheduler, worker, or strategy change was mixed into the domain-entry operation.

## Rollback

If nginx behavior regresses after an authorized edit:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
BACKUP_DIR="$HOME/nginx-domain-entry-backup-YYYYMMDDHHMMSS"
sudo rm -rf /etc/nginx/sites-enabled /etc/nginx/sites-available
sudo cp -a "$BACKUP_DIR/sites-enabled" /etc/nginx/sites-enabled
sudo cp -a "$BACKUP_DIR/sites-available" /etc/nginx/sites-available
sudo nginx -t
sudo systemctl reload nginx
'
```

Rollback should only restore nginx files captured immediately before the domain-entry change.

## Operations Not Included

- No Docker restart/recreate/remove.
- No `.env` change.
- No database write or schema change.
- No scheduler cutover.
- No worker tuning.
- No strategy or priority-board semantic change.
