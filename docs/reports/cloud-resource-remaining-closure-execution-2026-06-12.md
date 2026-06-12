# Cloud Resource Remaining Closure Execution - 2026-06-12

## Scope

This follow-up closes the repository-side gaps for the remaining cloud resource contention plan. It does not execute any production write, deployment, Docker action, DB action, nginx/systemd/DNS/CDN change, or D5 scheduler cutover.

## Completed In This Pass

| Item | Result | Evidence |
|---|---|---|
| Remaining gate audit | Added `scripts/audit_cloud_resource_remaining_closure.py` to classify open work from local reports and source guards. | `docs/reports/cloud-resource-remaining-closure-audit-2026-06-12.md` |
| Old frontend guard closure | Updated runbooks so `frontend-hot`, `frontend-legacy`, and `/__legacy/*` remain retired production paths. | `legacy_frontend.retirement_guard=complete` |
| Optional worker runbook closure | Documented that analytics/backtest/ML/factor work stays out of the small-host always-on profile and runs only on demand. | `optional_workers.on_demand_runbook=complete` |
| SLA requeue closure tracking | Audit now records the deployed `DATA_QUALITY_SLA_ENABLED=false` fix as complete. | `data_quality_sla.non_core_requeue=complete` |

## Current Remaining State

From the generated audit:

| Requirement | Status | Why not complete now |
|---|---|---|
| Full trading-day D5 observation | `observation_required` | Missing formal checkpoints: `10:30`, `11:30`, `13:05`, `15:10`, `15:30`. |
| Scheduler embed cutover | `blocked` | D5 is not ready; retained blockers include historical OOM, worker memory `99.96%`, provider warnings, and nonterminal task counts. |
| MySQL root cause | `needs_investigation` | Budget is ok, but slow-query warnings remain in D5 snapshots. |
| Domain TLS/SNI reset | `needs_authorization` | Requires domain/nginx/DNS/CDN/WAF maintenance path or provider ticket; resource work cannot resolve it. |
| Provider scheduler warning residual | `needs_investigation` | Provider cooldown guard exists, but D5 summary still includes scheduler provider warning lines. |
| Historical failed RuntimeTask noise | `needs_authorization` | Requires DB-write authorization and backup confirmation before archive/marking/cleanup. |

## Acceptance Evidence

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_resource_remaining_closure_audit.py
python3 scripts/audit_cloud_resource_remaining_closure.py \
  --json-output docs/reports/cloud-resource-remaining-closure-audit-2026-06-12.json \
  --markdown-output docs/reports/cloud-resource-remaining-closure-audit-2026-06-12.md \
  --fail-on-blocked
python3 scripts/audit_legacy_routes.py --strict
```

Expected result:

- Remaining audit exits `42` while D5 remains blocked.
- Legacy route audit returns `finding_count=0`.
- Audit summary has `partial=0`.

## Next Authorized Actions

1. Collect a valid full trading-day checkpoint set on the next trading day.
2. After D5 is ready, decide whether to authorize scheduler embed cutover.
3. Run MySQL slow-query/index/p95 review before any schema/index or machine-size change.
4. Run the domain-entry maintenance plan separately from resource work.
5. Prepare RuntimeTask historical failure archive/marking only after DB-write authorization.

## Operations Not Executed

- No deployment or cutover.
- No Docker restart/recreate/remove.
- No `.env` change.
- No DB write or schema/index change.
- No nginx/systemd/DNS/CDN change.
- No MySQL/Redis/Go/frontend-web action.
- No scheduler stop or D5 embed.
- No strategy semantics, `production_score`, or priority-board口径 change.
- No `backend/app/services/low_buy/strategy_policy.py` change.
