# B6 Independent Runtime Online Acceptance And Delta Upload

Date: 2026-06-04

## Scope

- B6 is the only deployment batch in the B0-B6 plan.
- Web remains a lightweight request/task-submit/status process.
- Runtime worker, runtime scheduler, analytics worker, and backtest worker run as independent modular-monolith processes.
- Delta upload is added as an upload acceleration path. `package-only` remains the automatic fallback.
- Remote GitHub clone/fetch remains disabled by default; `git-inplace` and `git-clone` are explicit opt-in modes only.

## Local Implementation

- `DEPLOY_SYNC_MODE=delta-package` added.
- `DEPLOY_SYNC_MODE=package-only` retained as fallback and explicit disable switch.
- Local deploy manifest includes relative path, sha256, size, and mode for publishable files.
- Last successful remote manifest is stored at `.runtime/deploy-manifest.json`.
- Delta package contains changed/new files plus:
  - `.deploy-delta/deploy-manifest.json`
  - `.deploy-delta/deploy-delete-manifest.json`
  - `.deploy-delta/deploy-delta-manifest.json`
- Remote application copies the current release to staging, applies changed files, applies manifest-bounded safe deletes, validates required paths, then atomically replaces the release.
- Automatic fallback triggers:
  - missing remote manifest
  - unsafe delete path
  - critical path change
  - change ratio above threshold
  - remote delta staging/apply failure
- Protected delete boundaries:
  - `.env`
  - `.runtime`
  - `backend/data`
  - databases
  - backups
  - uploaded artifacts
  - runtime data

## Independent Runtime Acceptance

| Role | Entrypoint | Health / claim check |
|---|---|---|
| Web/API | `scripts/run_platform_component.sh web` | `/readyz`; `RUNTIME_BACKGROUND_JOBS_ENABLED=false` |
| Runtime worker | `scripts/run_platform_component.sh runtime-worker` | `RuntimeTaskQueue.claim_next(... RUNTIME_WORKER_TASK_TYPES)` and heartbeat |
| Runtime scheduler | `scripts/run_platform_component.sh scheduler` | `RUNTIME_BACKGROUND_ROLE=scheduler`; scheduled enqueue loop only outside Web |
| Analytics worker | `scripts/run_platform_component.sh analytics-worker` | `duckdb`/`pyarrow` import, DB ping, analytics task registry claim |
| Backtest worker | `scripts/run_platform_component.sh backtest-worker` | queued backtest + research worker `run_once` path |

## Local Tests

Passed:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_cloud_deploy_scripts.py -q
```

Result: 34 passed, 1 warning.

```bash
DEPLOY_SYNC_MODE=delta-package scripts/one_click_cloud_deploy.sh --dry-run
```

Result: parsed with `sync_mode=delta-package`; no cloud connection required in dry-run.

```bash
DEPLOY_SYNC_MODE=delta-package scripts/one_click_cloud_deploy.sh --dry-run
DEPLOY_SYNC_MODE=package-only scripts/one_click_cloud_deploy.sh --dry-run
```

Result: both sync modes parsed and printed dry-run summaries.

Pending B6 commit gate:

```bash
git diff --check
git status --short
```

## Online Acceptance

Updated in A1 follow-up review with traceable online evidence.

| Check | Result |
|---|---|
| `git push origin HEAD:main` | done for `1824b363a3bfdf4b2900fe4c2e881ab4e6bf1335` |
| GitHub Actions deploy job | success, run `26939035586`, deploy job `79476390009` |
| Deploy sync mode | requested `delta-package`, effective `package-only` |
| Delta changed count | `0` |
| Delta deleted count | `0` |
| Delta bytes | `0` |
| Full bytes | `6477745` |
| Upload seconds | `397` |
| Fallback reason | `invalid_remote_manifest` |
| Web readyz | `{"status":"ok","checks":{"database":true,"frontend_dist":true,"analytics_dependencies":true}}` |
| runtime-worker health | `healthy` |
| runtime-scheduler health | `healthy` |
| analytics-worker health | `healthy`; DuckDB `1.5.3`, PyArrow `22.0.0`, DB ping returned no error |
| backtest-worker health | container running; no Docker healthcheck configured |
| Online performance round 1 | `docs/reports/gupiao-cloud-performance-2026-06-04-162901.json`, `ok=true` |
| Online performance round 2 | `docs/reports/gupiao-cloud-performance-2026-06-04-163020.json`, `ok=true` |

Current remote manifest check:

```text
manifest_ok version=1 file_count=2343 total_size=47777433
```

The final B6 deployment still fell back because the remote manifest available
at that deploy step was invalid. After that deployment, the remote manifest is
valid and can be used by the next delta-package attempt.

## Production Sorting Impact

No production ranking is changed by B6.

- No `strategy_policy.py` change.
- No new `production_score` source.
- No replacement of low-buy, priority board, front-row weighted, or strategy tracking sort order.
- Delta deployment and independent worker health checks only affect release transport and runtime process verification.

## Rollback

- Disable delta upload: `DEPLOY_SYNC_MODE=package-only ./scripts/deploy_cloud_server.sh`.
- Restart individual processes:
  - `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate app`
  - `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker`
  - `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-scheduler`
  - `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker`
  - `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate backtest-worker`
- Release rollback follows `docs/operations/deployment-topology-runbook.md`: stop write-heavy workers, restore DB/release backup, restart Web and workers after `/readyz` and DB checks pass.
