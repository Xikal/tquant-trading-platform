# Documentation Index

## Current Operational Documents

- `README.md`
- `docs/engineering-conventions.md`
- `docs/operations/market-data-provider-runbook.md`
- `docs/operations/observability-warning-budget-runbook.md`
- `docs/operations/phase4-phase5-rollout.md`
- `docs/operations/schema-index-runbook.md`
- `docs/operations/ui-regression-checklist.md`
- `docs/high-roi-platform-expansion-runbook-2026-05-30.md`
- `docs/superpowers/plans/2026-05-30-trust-and-data-quality-expansion.md`
- `PRODUCTION_RUNBOOK.md`
- `DEVELOPMENT_GUIDE.md`

## Current Product And Strategy References

- `TRADING_QUANT_LEAD_PLAYBOOK.md`
- `PROJECT_PLAN.md`
- `PRODUCT_STAGE_ACCEPTANCE.md`
- `docs/low-buy-strategy-mechanism.md`
- `docs/market-trading-enhancement-requirements-2026-05-25.md`
- `docs/market-trading-enhancement-execution-plan-2026-05-25.md`
- `docs/prelaunch-review-adoption-plan-2026-05-26.md`
- `docs/strategy-core-midcap-vwap-ma5-retrace.md`
- `docs/strategy-late-session-strong-support-next-day-sell.md`
- `docs/strategy-sector-mainline-first-divergence-low-buy.md`

## Architecture And Refactor History

These files are kept as historical decision records. Do not treat them as current implementation truth without checking code and latest reports.

- `FINAL_DELIVERY.md`
- `IMPLEMENTATION_PLAN.md`
- `OPTIMIZATION_PLAN.md`
- `APP_API_SPEC.md`
- `ARCHITECTURE.md`
- `全方位评估报告-2026-05-01.md`
- `策略体系重组方案.md`
- `docs/frontend-bff-microservices-evolution-plan-2026-05-19.md`
- `docs/microservices-independent-deployment-design-2026-05-20.md`
- `docs/backend-final-refactor-master-plan-2026-05-21.md`
- `docs/backend-final-refactor-optimization-plan-2026-05-21.md`
- `docs/backend-final-refactor-pragmatic-plan-2026-05-21.md`
- `docs/backend-go-rust-refactor-final-plan-2026-05-22.md`
- `docs/backend-refactor-runtime-runbook-2026-05-22.md`
- `docs/remaining-architecture-debt-executable-plan-2026-05-24.md`

Archived historical evidence lives under `docs/archive/`; only the current entries above should be treated as active references.

## Reports And Evidence

- `docs/reports/full-project-audit-2026-05-25.md`
- `docs/reports/full-regression-2026-05-27.md`
- `docs/reports/observability-warning-budget-2026-05-27.md`
- `docs/reports/repository-cleanup-2026-05-27.md`
- `docs/reports/project-conventions-remediation-2026-05-31.md`
- `docs/reports/strategy_24m_duckdb_report.md`
- `docs/reports/go-rust-performance-acceptance-2026-05-27.json`
- `docs/reports/gupiao-cloud-performance-2026-05-27-120241.json`
- `docs/reports/gupiao-cloud-performance-2026-05-27-124403.json`
- `docs/reports/gupiao-go-rust-runtime-performance-2026-05-27.json`
- `docs/reports/rust-bench-baseline.json`

## Artifact Governance

- New large machine-readable analytics outputs must go under `backend/data/analytics/reports`, an external `artifacts/` directory, or object storage; do not add new large JSON files directly under `docs/reports`.
- Human-readable Markdown summaries may stay in `docs/reports` when they are current evidence or release records.
- The generated DuckDB strategy report has a tracked Markdown summary at `docs/reports/strategy_24m_duckdb_report.md`; its JSON companion belongs at `backend/data/analytics/reports/strategy_24m_duckdb_report.json`.
- Data quality repair dry-run/apply JSON, SLA exports and large machine-readable repair evidence belong under `backend/data/analytics/reports`, `backups/data_quality`, an external `artifacts/` directory, or object storage; do not place them directly under `docs/reports`.
- `docs/reports/*-backtest-*.json`, `docs/reports/*-performance-*.json`, report zips, and analytics parquet/report JSON are ignored by default to avoid accidental repository bloat.

## Cleanup Policy

- `.runtime/`, `__pycache__/`, `.pytest_cache/`, logs, local SQLite files, mobile screenshots and generated smoke artifacts are local-only.
- `frontend/*.tsbuildinfo` is TypeScript incremental build cache and must not be tracked.
- Keep only cloud performance reports that are referenced by a persistent report or represent the latest post-deploy verification.
- Before deleting a document or report, check references with `rg` and confirm it is not used by code, CI, deployment, tests or audit records.
- Reference audit used for this cleanup pass: `rg --fixed-strings <basename> .` for each candidate report; files with live references in docs, scripts, tests, CI, or page code must be kept.
