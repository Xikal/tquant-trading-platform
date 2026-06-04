# Platform Modular Architecture Phase 7 Acceptance

Date: 2026-06-04.

Scope: Phase 7 only. This pass documents and guards independent operation for
Web, runtime worker, scheduler, analytics worker, and backtest worker. It does
not deploy the application.

## Added Local Component Entrypoint

New script:

```text
scripts/run_platform_component.sh
```

Supported components:

- `web`
- `runtime-worker`
- `scheduler`
- `analytics-worker`
- `backtest-worker`

Each component supports `--print-command`, allowing CI/tests/operators to verify
the exact entrypoint without starting a process.

`scripts/dev_start_all.sh` now reuses this component entrypoint for local Web +
runtime-worker startup.

## Added Runbooks

New operation documents:

- `docs/operations/deployment-topology-runbook.md`
- `docs/operations/worker-runbook.md`

They cover:

- process roles and production compose services
- local commands
- health checks
- worker heartbeat / queue-age checks
- analytics dependency checks
- restart matrix
- rollback order
- boundaries that keep heavy work out of Web request paths

`PRODUCTION_RUNBOOK.md` now links both documents and explicitly describes the
independent `runtime-scheduler` role.

## Existing Deployment Structure Confirmed

Current production compose already separates:

- `app`
- `runtime-worker`
- `runtime-scheduler`
- `analytics-worker`
- `backtest-worker`
- `mysql`
- `redis`
- Go read/BFF/scan services

This phase adds operator-facing structure and tests rather than rewriting the
compose topology.

## Non-Changes

This phase intentionally does not:

- deploy to production
- add a new microservice split
- change Docker image build strategy
- change strategy scoring or ranking
- change `strategy_policy`
- change backtest or paper-trading semantics
- move DuckDB/Parquet into production fact sourcing
- enable Web background loops

## Validation Commands

Commands:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_cloud_deploy_scripts.py -q
scripts/run_platform_component.sh web --print-command
scripts/run_platform_component.sh runtime-worker --print-command
scripts/run_platform_component.sh scheduler --print-command
scripts/run_platform_component.sh analytics-worker --print-command
scripts/run_platform_component.sh backtest-worker --print-command
git diff --check
```

Actual result:

```text
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_cloud_deploy_scripts.py -q:
24 passed, 1 warning

scripts/run_platform_component.sh web --print-command: passed
scripts/run_platform_component.sh runtime-worker --print-command: passed
scripts/run_platform_component.sh scheduler --print-command: passed
scripts/run_platform_component.sh analytics-worker --print-command: passed
scripts/run_platform_component.sh backtest-worker --print-command: passed

git diff --check: passed
```

## Phase 7 Verdict

Phase 7 is accepted as an independent-operation baseline:

- Web and worker roles are documented.
- Local single-component commands exist.
- Worker runbooks define health, restart, and rollback checks.
- Production runbook points operators to the new topology and worker docs.
- Existing production compose separation remains unchanged.

No deployment was performed.
