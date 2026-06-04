# Analytics Manifest Lifecycle Local Readiness - 2026-06-04

Status: local code and tests only. Not deployed, not committed, not pushed.

## Scope

- Daily bars Parquet manifests now include lifecycle fields:
  - `manifest_id`
  - `dataset_version`
  - `generated_at`
  - `valid_until`
  - `superseded_by`
  - `status`
- Writing a new latest manifest marks the previous concrete manifest file as `stale` and records `superseded_by`; old artifacts are not deleted.
- Strategy 24M DuckDB report writes update `backend/data/analytics/reports/index.json` when run against the default analytics root, or `<output_root>/reports/index.json` in local tests.

## Boundaries

- DuckDB/Parquet remain analytics/report-layer inputs only.
- The 24M coverage math and report metrics are unchanged.
- Production sorting, low-buy priority boards, strategy tracking, and `strategy_policy.py` are untouched.

## Local Verification

Planned command:

`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_manifest_lifecycle.py backend/tests/test_analytics_report_versioning.py backend/tests/test_analytics_layer.py backend/tests/test_analytics_worker.py backend/tests/test_analytics_worker_handlers.py -q`

Online validation is pending explicit user authorization.
