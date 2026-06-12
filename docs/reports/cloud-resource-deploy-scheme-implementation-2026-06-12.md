# Cloud Resource Deploy Scheme Implementation - 2026-06-12

## Scope

This pass implements the repository-side deployment guard for the current cloud
resource plan. It does not execute a production deployment, Docker restart,
Docker remove, `.env` write, DB write, nginx/systemd/DNS change, or D5 scheduler
cutover.

## Implemented

| Area | Result | Evidence |
|---|---|---|
| D5 scheduler embed gate | Added a local JSON gate that blocks embedded scheduler deployment unless `d5_ready=true`, `full_trading_day_complete=true`, no missing checkpoints, and no D5 blockers. | `scripts/verify_d5_scheduler_embed_gate.py` |
| Direct deploy path | `scripts/deploy_cloud_server.sh` runs the gate before local checks, package upload, remote sync, or remote Docker actions when `DEPLOY_EMBED_RUNTIME_SCHEDULER` is enabled. | `verify_d5_scheduler_embed_gate` |
| Quick deploy path | `scripts/quick_cloud_deploy.sh` runs the same gate for both deploy and verify-only paths when `--embed-runtime-scheduler` is enabled. | `--d5-gate-summary` |
| Runbooks | Scheduler embed cutover now uses the guarded quick deploy path instead of manual `.env` and `docker rm` commands as the default route. | `docs/operations/deployment-topology-runbook.md`, `docs/operations/cloud-core-worker-resource-runbook.md`, `docs/operations/worker-runbook.md` |
| Regression tests | Added gate behavior tests and deploy-script structure checks. | `backend/tests/test_d5_scheduler_embed_gate.py`, `backend/tests/test_cloud_deploy_scripts.py` |

## Current D5 State

The current local D5 summary is still blocked:

- Summary: `docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json`
- Missing checkpoints: `10:30`, `11:30`, `13:05`, `15:10`, `15:30`
- Blockers: `full_trading_day_observation_incomplete`, `kernel_oom_logs_present`,
  `runtime_nonterminal_task_count=1`, `runtime_nonterminal_task_count=2`,
  `runtime_nonterminal_task_count=4`, `runtime_worker_memory_pct=99.96`,
  `runtime_worker_signal_logs_present`, `scheduler_provider_warning_lines=160`

Therefore the deployment scheme is implemented, but the production scheduler
embed/cutover must remain blocked until a fresh full trading-day checkpoint set
passes.

## Authorized Command After D5 Passes

Use this only after D5 is ready and the operator explicitly authorizes the
worker-scope deployment:

```bash
DEPLOY_D5_GATE_SUMMARY=docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json \
scripts/quick_cloud_deploy.sh --scope worker --embed-runtime-scheduler
```

Expected gate behavior before D5 passes:

```bash
python3 scripts/verify_d5_scheduler_embed_gate.py \
  --summary docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json \
  --fail-on-blocked
```

The command exits `42` and prints `status=blocked`.

## Operations Not Executed

- No deployment or cutover.
- No Docker restart/recreate/remove.
- No `.env` change.
- No DB write or schema/index change.
- No nginx/systemd/DNS/CDN change.
- No scheduler stop or D5 embed.
- No strategy semantics, `production_score`, or priority-board口径 change.
- No `backend/app/services/low_buy/strategy_policy.py` change.
