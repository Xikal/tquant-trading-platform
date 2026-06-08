# frontend-next Level 1 Cutover Report - 2026-06-07

## Scope

- Authorization: Level 1 cutover for `/monitor`.
- Allowed: deploy/cutover only after all gates pass.
- Rollback requirement: keep old `frontend/` available and make `/monitor` return to old frontend by turning off `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED`.
- Final state: not cut over. `/monitor` is still served by the old frontend. `/next/monitor` remains available for shadow usage.

## Local Gate Results

All local pre-cutover gates completed successfully after the compose env passthrough fix:

- `frontend-next`: `npm run api:check` passed.
- `frontend-next`: `npm run typecheck` passed.
- `frontend-next`: `npm run lint` passed.
- `frontend-next`: `npm test -- --run` passed, 86 tests.
- `frontend-next`: `npm run build` passed.
- `frontend-next`: `npm run e2e` passed, 45 tests.
- `frontend-next`: `npm run api:cutover-readiness` passed, 6 probes, 0 failures.
- `frontend-next`: `npm run write:readiness` passed, 13 contracts, 0 blocked, rollback evidence ok.
- `frontend-next`: `npm run write:rollback -- --all --isolated` passed.
- `frontend-next`: `npm run request:trace` passed, 9 routes, 0 failures.
- `frontend-next`: `npm run perf:compare` passed.
- `frontend-next`: `npm run visual:consistency` passed, 36 captures, 0 failures.
- `frontend`: `npm run api:check` passed.
- `frontend`: `npm run typecheck` passed.
- `frontend`: `npm run lint` passed.
- `frontend`: `npm test -- --run` passed, 299 tests.
- `frontend`: `npm run build` passed.

Note: old frontend `api:check` regenerated `frontend/src/generated/api-types.ts`; it was restored so old `frontend/` production code is not left modified.

## Deployment Attempt

Initial remote verify-only passed:

```bash
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false ./scripts/quick_cloud_deploy.sh \
  --verify-only --performance-verify \
  --host 43.143.243.97 --user ubuntu --key /Users/j/Downloads/gupiao.pem \
  --port 18090 --public-base-url http://43.143.243.97:18090
```

First deploy attempt:

```bash
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=true DEPLOY_SYNC_MODE=package-only ./scripts/quick_cloud_deploy.sh \
  --scope all --performance-verify \
  --host 43.143.243.97 --user ubuntu --key /Users/j/Downloads/gupiao.pem \
  --port 18090 --public-base-url http://43.143.243.97:18090
```

Result: stopped. The deploy command exited with code 1 during online `performance-verify`.

Evidence:

- Report: `docs/reports/gupiao-cloud-performance-2026-06-07-231755.json`
- Failure: `priority_board p95_ms=1590.177`, threshold `500`.

Additional finding from the first attempt:

- `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=true` was written to remote `.env`.
- `docker-compose.mysql.yml` did not pass `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED` into the app container, so `/monitor` still served the old frontend.
- Fixed locally by adding `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED: ${FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED:-false}` to the app container environment and adding `test_frontend_next_monitor_cutover_flag_reaches_web_container`.

Second remote performance verify-only after reset also failed, so no second cutover deploy was attempted:

- Report: `docs/reports/gupiao-cloud-performance-2026-06-07-232405.json`
- Failures:
  - `market_pulse`: statuses include `error:TimeoutError`, p95 `22.24`, threshold `500`.
  - `watchlist_signals`: statuses include `error:TimeoutError`, p95 `234.282`, threshold `600`.

## Current Remote State

Verified after stopping cutover:

- Remote `.env`: `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false`.
- `/readyz`: ok.
- `/monitor`: HTTP 200, old frontend assets under `/assets/*`.
- `/next/monitor`: HTTP 200, new frontend assets under `/next/assets/*`.
- `/next/assets/index-9E_rcgKO.js`: HTTP 200, `application/javascript`.

## Files Changed For This Level 1 Attempt

- `docker-compose.mysql.yml`: passes the Level 1 cutover flag into the app container.
- `backend/tests/test_cloud_deploy_scripts.py`: verifies the deploy scripts write/export the flag and compose injects it into the web container.

Other repository changes from previous frontend-next work remain in the worktree and were not reverted.

## Old Frontend And Backend Impact

- Old `frontend/`: validation passed; no old frontend production source is intentionally modified by this Level 1 attempt.
- Backend: already contains the frontend-next static route/readiness support from the cutover preparation work; this attempt added only compose env passthrough.
- Strategy semantics: no changes to `strategy_policy.py`, production ranking, `production_score`, or `priority_board`口径.
- Platform runtime impact: no Level 1 cutover is active. `/monitor` remains old frontend.

## Rollback

Current rollback state is already active:

```bash
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false
```

If a future deploy enables the flag and must be rolled back:

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sed -i '/^FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=/d' .env
printf 'FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false\n' >> .env
sudo docker compose -f docker-compose.mysql.yml up -d --force-recreate app
curl -f http://127.0.0.1:18090/readyz
curl -f http://127.0.0.1:18090/monitor
```

## Remaining Blockers

1. Execute the runtime Level 1 switch only after the user confirms the final activation window.
2. After enabling, verify:
   - `/monitor` returns new frontend `/next/assets/*`.
   - `/next/monitor` still works.
   - `/assets/*` old frontend rollback assets still work.
   - `frontend_next.monitor_cutover_enabled=false` or `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false` reverts `/monitor` to old frontend.

## 2026-06-08 Performance Remediation And Re-Verification

### Root Cause

The failed online verification was not caused by frontend-next rendering. It was caused by request-path backend long tails during deploy/cold-resource windows:

- `/api/watchlist/signals` still used per-symbol live analysis on the request thread.
- `/api/market/pulse` could enqueue refresh tasks using the request DB session.
- `/api/screeners/low-buy/priority-board` cache-only reads were correct, but the first cold read after deploy still paid DB/cache warmup cost.
- The small cloud host was at 90% disk before cleanup; online Docker builds and cache rebuilds amplified cold-start I/O and latency.

### Fixes Applied

- `backend/app/services/watchlist_signal_service.py`: added `list_signals_for_rows`, a non-blocking snapshot read path for user watchlists.
- `backend/app/api/routes/watchlist.py`: `/api/watchlist/signals` now reads cached snapshots/fallbacks and schedules background refresh instead of doing live analysis.
- `backend/app/services/app_mobile/watchlist.py`: user watchlist cards now use the same non-blocking snapshot path.
- `backend/app/api/routes/market.py`: market pulse refresh task enqueue now runs in a throttled background thread with a fresh session, so stale snapshot reads do not block on task writes.
- `backend/app/api/routes/bff.py`: BFF market pulse fallback also uses async enqueue.
- `backend/app/services/frontend_next_cutover.py`: added runtime `/monitor` cutover setting backed by `system_settings`, with environment fallback.
- `backend/app/main.py`: `/monitor` cutover and `readyz` now consult the runtime switch.
- `scripts/measure_cloud_go_rust_performance.py`: added API prewarm, per-sample status/latency details, and explicit `refresh=cache` for priority board verification.

### Cloud Cleanup

Before redeploying, safe cleanup was run on `43.143.243.97`:

- Root disk before cleanup: `59G` total, `51G` used, `6.1G` free, `90%`.
- Cleaned only stopped containers, dangling images, Docker build cache, and oversized JSON logs.
- Docker volumes were not pruned. MySQL/Redis/Grafana/Prometheus data volumes were preserved.
- Root disk after cleanup: `59G` total, `46G` used, `12G` free, `81%`.

After the verified deploy/build, root disk settled at `86%` with `8.1G` free. Docker build cache was back to about `5.96GB`; this is usable cache, but the long-term fix is to stop building heavy images on the small production host and use prebuilt images or a larger build runner.

### Local Re-Verification

Commands run:

```bash
backend/.venv/bin/pytest backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_frontend_next_cutover_service.py backend/tests/test_watchlist_signal_service.py backend/tests/test_market_routes.py::MarketRouteTests::test_market_pulse_sync_returns_placeholder_and_queues_refresh_when_snapshot_missing backend/tests/test_market_pulse_cache_fast_path.py::test_market_pulse_sync_reads_cached_snapshot_without_recomputing backend/tests/test_cloud_performance_script.py backend/tests/test_bff_routes.py backend/tests/test_bff_monitor_workspace.py backend/tests/test_app_mobile_service.py backend/tests/test_cloud_deploy_scripts.py::test_frontend_next_monitor_cutover_flag_reaches_web_container -q
backend/.venv/bin/python -m py_compile backend/app/api/routes/watchlist.py backend/app/services/watchlist_signal_service.py backend/app/api/routes/market.py backend/app/api/routes/bff.py backend/app/services/app_mobile/watchlist.py backend/app/services/frontend_next_cutover.py scripts/measure_cloud_go_rust_performance.py
git diff --check
```

Results:

- Pytest: `49 passed`.
- Python compile: passed.
- `git diff --check`: passed.
- Ruff was not available in `backend/.venv`; no ruff result was produced.

### Online Re-Verification

Deploy command:

```bash
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false DEPLOY_SYNC_MODE=package-only ./scripts/quick_cloud_deploy.sh \
  --scope all --performance-verify --performance-rounds 3 \
  --host 43.143.243.97 --user ubuntu --key /Users/j/Downloads/gupiao.pem \
  --port 18090 --public-base-url http://43.143.243.97:18090
```

Result: deploy and all three online performance rounds passed.

Performance reports:

| Report | readyz p95 | monitor_bff p95 | market_pulse p95 | priority_board p95 | watchlist_signals p95 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `docs/reports/gupiao-cloud-performance-2026-06-07-235748.json` | 15.012 ms | 46.429 ms | 13.216 ms | 65.706 ms | 42.707 ms | pass |
| `docs/reports/gupiao-cloud-performance-2026-06-07-235900.json` | 9.168 ms | 21.979 ms | 17.964 ms | 73.494 ms | 51.259 ms | pass |
| `docs/reports/gupiao-cloud-performance-2026-06-08-000012.json` | 7.336 ms | 30.266 ms | 28.294 ms | 103.424 ms | 24.109 ms | pass |

All measured statuses were `[200]`; failures were empty in all three reports.

The first post-restart prewarm still showed cold-start cost in round 1 (`market_pulse` about `4.7s`, `priority_board` about `5.4s`, BFF cold log about `7.2s`). Those calls were outside the measurement window and were absorbed by the new prewarm step. For a real cutover window, the required sequence is now:

1. Deploy with `/monitor` still on old frontend.
2. Run online prewarm/performance gates.
3. Only after the gates pass, enable the runtime `/monitor` switch.
4. Verify `/monitor` new assets.
5. Keep immediate rollback to old frontend available.

### Current Remote State After Re-Verification

- `.env`: `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false`.
- `system_settings.frontend_next.monitor_cutover_enabled`: missing, so environment fallback keeps `/monitor` on old frontend.
- `/readyz`: ok.
- `/monitor`: HTTP 200 and serves old frontend `/assets/*`.
- `/next/monitor`: HTTP 200 and serves new frontend `/next/assets/*`.
- No backend strategy semantics changed; `strategy_policy.py`, production sorting, `production_score`, and `priority_board`口径 were not changed.

### Updated Cutover Readiness

The online performance blocker is resolved. The code is ready for a controlled Level 1 activation step, but this report leaves `/monitor` on the old frontend. To activate Level 1, set `system_settings.frontend_next.monitor_cutover_enabled=true` or deploy with `FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=true`, then verify and keep rollback ready.
