# Platform Modular Architecture Phase 2 Acceptance

Date: 2026-06-04.

Scope: Phase 2 only. This verifies the current DuckDB/Parquet analysis layer as
an independent reporting layer. It does not change production ranking,
strategy policy, scoring formulas, paper trading behavior or deployment.

## Implemented Baseline

Phase 2 capabilities are already present in the codebase and were verified in
this pass:

- `backend/app/services/analytics/quality.py`
  - checks 24-month `daily_bars` coverage
  - returns explicit `fail` blockers when data is insufficient
  - can enqueue `data_backfill_24m` instead of fabricating data
- `backend/app/services/analytics/exporters.py`
  - exports `daily_bars` to partitioned Parquet
  - writes Manifest metadata with hashes, row counts and quality summary
- `backend/app/services/analytics/manifest.py`
  - writes versioned Manifest and `daily_bars.latest.json`
- `backend/app/services/analytics/duckdb_repository.py`
  - provides DuckDB read-only query access over analysis artifacts
- `backend/app/services/analytics/report_queries.py`
  - generates a 24-month strategy report from Manifest and Parquet
  - returns `blocked_by_data` or `blocked_by_validation_inputs` when required
    data or validation evidence is missing
- `backend/scripts/export_analytics_parquet.py`
  - CLI entrypoint for Parquet export
- `backend/scripts/run_duckdb_strategy_report.py`
  - CLI entrypoint for DuckDB strategy report generation
- `backend/app/services/tasks/analytics_handlers.py`
  - worker handlers for `analytics_export_daily_bars`,
    `analytics_quality_check`, `strategy_24m_duckdb_report` and
    `backtest_all_strategies_24m`

## Local Export Evidence

Command:

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. \
  backend/.venv/bin/python backend/scripts/export_analytics_parquet.py \
  --months 24 \
  --end-date 2026-06-04 \
  --output-root /tmp/gupiao-analytics-phase2
```

Result: passed.

Summary:

| Metric | Value |
| --- | ---: |
| dataset_version | `daily_bars_20260604034302` |
| period_start | `2024-06-04` |
| period_end | `2026-06-04` |
| actual_start | `2024-06-04` |
| actual_end | `2026-05-29` |
| Parquet files | 24 |
| row_count | 2,341,194 |
| symbol_count | 4,976 |
| actual_days | 481 |
| expected_days | 355 |
| complete_trade_day_count | 481 |
| duplicate_rows | 0 |
| invalid_ohlc_rows | 0 |
| quality.status | `ok` |
| blockers | none |
| backfill_task_id | null |

Manifest:

```text
/tmp/gupiao-analytics-phase2/manifests/daily_bars_20260604034302.json
```

Parquet output:

```text
/tmp/gupiao-analytics-phase2/parquet/daily_bars/
```

## DuckDB Report Evidence

Command:

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. \
  backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --manifest /tmp/gupiao-analytics-phase2/manifests/daily_bars_20260604034302.json \
  --output-root /tmp/gupiao-analytics-phase2 \
  --output-md /tmp/gupiao-analytics-phase2/reports/strategy_24m_duckdb_report.md \
  --output-json /tmp/gupiao-analytics-phase2/reports/strategy_24m_duckdb_report.json
```

Result: passed.

Output:

```json
{"status":"ok","output_md":"/tmp/gupiao-analytics-phase2/reports/strategy_24m_duckdb_report.md","output_json":"/tmp/gupiao-analytics-phase2/reports/strategy_24m_duckdb_report.json"}
```

## Data Insufficiency Behavior

Existing tests verify the required failure path:

- incomplete 24-month data returns `quality.status == "fail"`
- blockers include concrete daily bar coverage reasons
- `create_backfill_task=True` creates `data_backfill_24m`
- export still records failure quality in Manifest instead of pretending data is
  complete
- DuckDB report returns blocked statuses when data or validation evidence is
  missing

This satisfies the boundary that missing data must be explicit and must not
create fake bars, fake scores or fake reports.

## Test Evidence

Command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_layer.py \
  backend/tests/test_analytics_worker.py \
  backend/tests/test_strategy_24m_duckdb_report.py \
  -q
```

Result:

```text
13 passed, 1 warning
```

The warning is the existing local `urllib3` LibreSSL warning.

## Environment Note

The first export attempt without `DATABASE_URL` failed because the local default
configuration tried to connect to `localhost` MySQL and the local MySQL service
was not running. The Phase 2 verification was rerun with the project local
SQLite database:

```text
DATABASE_URL=sqlite:///backend/data/t_quant.db
```

That rerun passed. This is an environment selection issue, not a Parquet or
DuckDB logic failure.

## Phase 2 Verdict

Phase 2 is accepted for the current architecture baseline:

- Parquet export can generate a 24-month `daily_bars` analysis dataset.
- Manifest generation works and includes quality metadata.
- DuckDB strategy report generation works from the Manifest.
- Insufficient data paths are explicit and can enqueue backfill.
- DuckDB/Parquet remain analysis/report artifacts and are not production
  trading fact sources.

No deployment was performed.
