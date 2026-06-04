# Platform Architecture Review Baseline

Status: A0 baseline frozen  
Date: 2026-06-04  
Scope: follow-up development baseline for the modular architecture review

## Worktree Gate

Command:

```bash
git status --short
```

Result before A0 edits:

```text
?? docs/platform-architecture-review-followup-development-plan-2026-06-04.md
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

Both files are treated as user-provided plan inputs. They are not cleaned,
rewritten, or included in implementation scope unless the user explicitly asks.

## Required Documents Read

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/architecture/current-boundary-map.md`
- `docs/platform-architecture-review-followup-development-plan-2026-06-04.md`
- `docs/reports/platform-next-stage-baseline-2026-06-04.md`
- `docs/reports/platform-next-stage-b1-web-heavy-task-migration-2026-06-04.md`
- `docs/reports/platform-next-stage-b2-analytics-production-chain-2026-06-04.md`
- `docs/reports/platform-next-stage-b3-strategy-engine-integration-2026-06-04.md`
- `docs/reports/platform-next-stage-b4-execution-model-integration-2026-06-04.md`
- `docs/reports/platform-next-stage-b5-frontend-information-denoising-2026-06-04.md`
- `docs/reports/platform-next-stage-b6-independent-runtime-online-acceptance-2026-06-04.md`

## Current Completion Boundary

### Completed Architecture Baseline

- Modular monolith remains the architecture direction; no broad microservice
  split is in scope.
- Web request paths are bounded to lightweight reads, task submission, task
  status, cached read models, or explicitly queued heavy work.
- `RuntimeTaskQueue` is the durable task boundary for long-running work.
- Runtime worker, runtime scheduler, analytics worker, and backtest worker have
  independent startup paths.
- Analytics has Parquet export, manifest generation, quality checks, DuckDB
  report queries, and worker handlers.
- OpenAPI export and frontend generated types are the contract source of truth.
- Frontend workspace page responsibilities are documented and surfaced through
  the denoised page hierarchy.

### Partially Completed, Not Replacement

- Strategy Engine has `outputs`, `gates`, and the low-buy adapter, but it remains
  a Shadow/parity layer. It is not the production ranking service.
- Execution Model has event objects, shared helper rules, and max5/max10 preview
  parity, but it remains a preview path.
- Worker operation is deployable and test-covered, but the UI/operational
  observability surface is still incomplete.
- B6 online acceptance ran after implementation, but the B6 Markdown report still
  contained pending rows before this follow-up phase.

### Explicitly Not Replaced

- `strategy_engine_adapter_enabled=false`
- `execution_model_shared_rules_enabled=false`
- `replacement_enabled=false` in Execution Model preview payloads
- `strategy_policy.py` production admission semantics are unchanged.
- Low-buy, priority board, front-row weighted, and strategy tracking production
  sort order are not replaced.
- DuckDB/Parquet remains analytics/reporting only and is not a production
  trading fact source.

## Follow-Up Scope

A1-A7 will only harden and expose the already-built architecture:

1. Replace pending online acceptance evidence with current traceable checks.
2. Fix 24-month analytics coverage semantics so `coverage_pct` cannot exceed
   `100`.
3. Expose Strategy Engine Shadow diagnostics without changing sorting.
4. Expose Execution Model preview/parity without changing fact sources.
5. Continue frontend API wrapper convergence toward generated OpenAPI types.
6. Add Worker queue and heartbeat observability.
7. Produce online performance and stability comparison reports.

## Non-Goals

- No deployment in this follow-up unless explicitly requested.
- No microservice split.
- No production sorting replacement.
- No `strategy_policy.py` production admission rewrite.
- No Web request path heavy task execution.
- No fake scores, fake data, or silent data-quality success.

## A0 Verification

Required commands:

```bash
git diff --check
git status --short
```

This A0 report is documentation-only and intentionally introduces no code
behavior change.
