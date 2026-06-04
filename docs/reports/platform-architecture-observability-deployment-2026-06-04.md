# Platform Architecture Observability Deployment Prep · 2026-06-04

## Status

Local preparation only. No production deploy was executed, no containers were
restarted, and no remote write operation was performed. Online verification is
pending explicit user authorization.

## Scope Completed Locally

- `GET /api/runtime-tasks/summary` remains a read-only queue summary endpoint.
- `GET /api/runtime-tasks/workers` returns component heartbeats and running task
  ownership.
- `GET /api/runtime-tasks/failures` returns recent failed RuntimeTask rows.
- `GET /api/runtime-tasks/artifacts` extracts task artifact paths from payload
  and result JSON.
- Data Console renders queue summary, worker heartbeat, failures and artifact
  paths via `WorkerObservabilityPanel`.
- The expected independent components are:
  `runtime-worker`, `runtime-scheduler`, `analytics-worker`, and
  `backtest-worker`.

## Deployment Boundary

This report does not claim online availability. The W3 deployment step is
blocked by the explicit no-deploy instruction. After authorization, validation
should run read-only GET checks against:

```bash
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/summary" | jq .
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/workers" | jq '.items[]|{component,worker_id,heartbeat_age_seconds,status}'
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/failures?limit=10" | jq .
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/artifacts?limit=20" | jq .
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" "$BASE/metrics" | rg "bff_partial_timeout|market_read_unresolved|market_read_fallback|local_quote_cache"
```

## Regression Thresholds

- `monitor_bff` p95 should be at or below 500 ms after BFF aggregate rollout.
- `priority_board` p95 should be at or below 500 ms after workerized refresh
  and cache warmup.
- `market_read.unresolved` and `market_read.fallback` should be monitored as
  warning indicators, not hidden by frontend fallback.

## Boundary Proof

This preparation does not modify production ranking, `strategy_policy.py`,
`participates_in_priority_board`, `production_score`, Strategy Engine Shadow
behavior, or Execution Model Preview behavior.
