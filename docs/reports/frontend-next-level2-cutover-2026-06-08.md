# frontend-next Level 2 Cutover Report - 2026-06-08

## Scope

- Authorization: Level 2 cutover for `/monitor/market`, `/paper`, `/strategy-tracking`, `/analysis`, `/playbook`, `/backtest`, `/data`, `/settings`.
- Existing Level 1 page kept enabled: `/monitor`.
- Final remote flag: `FRONTEND_NEXT_CUTOVER_PATHS=monitor,monitor/market,paper,strategy-tracking,analysis,playbook,backtest,data,settings`.
- Deployment scope: frontend-next routing/cutover allowlist only. No production strategy semantics were changed.

## Pre-Cutover Gates

All required gates passed before widening beyond `/monitor`:

- New frontend validation: `api:check`, `typecheck`, `lint`, full unit tests, build, and e2e passed.
- Old frontend validation: `api:check`, `typecheck`, `lint`, tests, and build passed.
- `api:cutover-readiness -- --strict`: passed with 6 probes, 0 failures.
- `write:readiness`: passed with 13 contracts, 0 blocked contracts, rollback evidence ok.
- `write:rollback -- --all --isolated`: passed; isolated smoke user and lifecycle fixture were cleaned.
- `request:trace`: passed with 9 routes, 0 failures.
- `perf:compare`: passed.
- `visual:consistency`: passed with 9 pages, 4 viewports, 36 captures, 0 failures.
- Online `readyz`, container health, disk, and memory checks passed.

## Batch Cutover

### Batch 1

Enabled paths:

- `/monitor`
- `/monitor/market`
- `/paper`

Validation:

- `readyz`: ok.
- `request:trace`: ok, 9 routes, 0 failures.
- `/monitor/market` and `/paper` root paths matched the corresponding `/next/*` request budgets.

### Batch 2

Enabled paths:

- `/monitor`
- `/monitor/market`
- `/paper`
- `/strategy-tracking`
- `/analysis`
- `/playbook`

Validation:

- `readyz`: ok after startup retry.
- `request:trace`: ok, 9 routes, 0 failures.
- `/strategy-tracking`, `/analysis`, and `/playbook` root paths matched the corresponding `/next/*` request budgets.

### Batch 3

Enabled paths:

- `/monitor`
- `/monitor/market`
- `/paper`
- `/strategy-tracking`
- `/analysis`
- `/playbook`
- `/backtest`
- `/data`
- `/settings`

Validation:

- `readyz`: ok after startup retry.
- `request:trace`: ok, 9 routes, 0 failures.
- `/backtest`, `/data`, and `/settings` root paths matched the corresponding `/next/*` request budgets.

## Final Verification

### API And Writes

- `api:cutover-readiness -- --strict`: passed with official remote `ADMIN_API_TOKEN`, 6 probes, 0 failures.
- A local rerun without admin token returned 403 for `/api/settings` and `/api/settings/factor-weights`; this was credential scope, not an API regression. The official-token rerun passed.
- `write:readiness`: passed with 13 contracts, 12 production-ready contracts, 0 blocked contracts, 1 cutover-excluded contract, 30 covered write operations, 7 uncovered write operations, rollback evidence ok.
- Isolated rollback smoke leftovers: `smoke_users=0`, `smoke_lifecycle=0`.

### Request Trace

Final `request:trace` passed with 9 routes and 0 failures.

Root path API request counts after cutover:

| Route | API count | Unique API count |
| --- | ---: | ---: |
| `/monitor` | 2 | 2 |
| `/monitor/market` | 2 | 2 |
| `/paper` | 2 | 2 |
| `/strategy-tracking` | 2 | 2 |
| `/analysis` | 1 | 1 |
| `/playbook` | 6 | 6 |
| `/backtest` | 2 | 2 |
| `/data` | 1 | 1 |
| `/settings` | 2 | 2 |

### Performance

Final `perf:compare` passed.

| Route | Elapsed ms | API count | Notes |
| --- | ---: | ---: | --- |
| `/next/monitor` | 849 | 2 | ok |
| `/next/monitor/market` | 657 | 2 | ok |
| `/next/paper` | 711 | 2 | ok |
| `/next/strategy-tracking` | 2498 | 2 | ok, BFF strategy request about 1837 ms |

`/next/strategy-tracking` remains the slowest measured route, but it stayed within the verification command's pass criteria and made no forbidden legacy strategy-tracking API calls.

### Visual And DOM

- `visual:consistency`: passed, 36 captures, 0 failures.
- Root DOM smoke opened all 9 routes successfully.
- `/data` correctly showed the admin permission guard for a non-admin smoke user.

### Online Health

Remote host: `43.143.243.97`.

- `readyz`: ok.
- App container: healthy.
- Analytics worker, Go BFF, market read service, scan worker, MySQL, Redis, runtime workers: running; health checks healthy where defined.
- Root disk: `59G` total, `33G` used, `25G` available, `57%`.
- Memory: `3723M` total, `3062M` used, `661M` available.
- Swap: `1987M` total, `995M` used.

## Rollback

Rollback Level 2 only, keeping Level 1 `/monitor`:

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sed -i 's|^FRONTEND_NEXT_CUTOVER_PATHS=.*|FRONTEND_NEXT_CUTOVER_PATHS=monitor|' .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate app
curl -f http://127.0.0.1:18090/readyz
```

Rollback all frontend-next cutover, including Level 1:

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sed -i 's|^FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=.*|FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false|' .env
sed -i 's|^FRONTEND_NEXT_CUTOVER_PATHS=.*|FRONTEND_NEXT_CUTOVER_PATHS=|' .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate app
curl -f http://127.0.0.1:18090/readyz
```

Old frontend assets remain built into the deployed image, so the rollback path keeps the old frontend available.

## Impact Statement

- `strategy_policy.py`: not changed.
- Production strategy semantics, `production_score`, and `priority_board` sorting/meaning: not changed.
- Worker/WASM behavior: no strategy judgment added; cutover work is routing/display-layer only.
- Old frontend production code: not changed for this Level 2 cutover.
- Backend change reason: minimal routing/config support was required so Level 2 pages could be controlled by an explicit allowlist rather than a single `/monitor` flag.
- Platform feature impact: no known functional regression from the final checks. Admin-only `/data` remains permission guarded for non-admin users.
