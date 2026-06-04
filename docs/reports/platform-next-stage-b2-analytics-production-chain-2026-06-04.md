# Platform Next Stage B2 Analytics Production Chain

Date: 2026-06-04

Scope: B2 only. This batch operationalizes the 24-month `daily_bars` Parquet
export, Manifest, quality check, DuckDB strategy report, and analytics
worker/scheduler chain. DuckDB/Parquet remain analysis and report artifacts, not
production trading fact sources.

## Worktree Gate

Initial B2 status after B1 commit:

```text
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

The untracked plan file remains user-provided authority input and is not staged
by B2.

## Implementation

Updated analytics export Manifest fields:

- `dataset` and `dataset_key`
- `date_range.months`, `date_range.start`, `date_range.end`
- `row_count`, `symbol_count`
- `coverage.expected_days`, `coverage.actual_days`, `coverage.missing_days`
- `coverage.complete_trade_day_count`, `coverage.coverage_pct`,
  `coverage.complete_coverage_pct`
- `source.latest_db_updated_at`
- `quality.status` for legacy compatibility
- `quality.canonical_status` and top-level `quality_status`
- `artifact_paths`

Added canonical data states for analytics quality:

- `ok`
- `no_data`
- `stale`
- `partial`
- `blocked`

Worker behavior:

- `analytics_export_daily_bars` returns `ok`, canonical `status`, Manifest, and
  linked `backfill_task_id`.
- `analytics_quality_check` can consume an explicit Manifest or run a live DB
  check.
- `strategy_24m_duckdb_report` writes Markdown and JSON artifacts even when the
  report is `blocked_by_data`; the task succeeds with `ok=false` so operations
  can inspect the blocked report rather than seeing only a retry/failure row.

Scheduler behavior:

- Added `analytics_24m_report_schedule_enabled=false` and
  `analytics_24m_report_interval_hours=24`.
- When enabled in scheduler role, `_enqueue_analytics_24m_report_once()` submits
  `strategy_24m_duckdb_report` with `manifest=latest`.
- No Web background loop is added.

CLI behavior:

- `backend/scripts/export_analytics_parquet.py` exits successfully when it writes
  a Manifest, including explicit blocked/no_data/stale/partial Manifests.
- `backend/scripts/run_duckdb_strategy_report.py` reuses the latest Manifest when
  present and exits successfully when it writes a report, including
  `blocked_by_data` reports.

## Local Manifest Sample

Acceptance command was first run without a `DATABASE_URL` override and failed
because `backend/data/runtime.env` points to local MySQL:

```text
mysql+pymysql://root:db-secret@localhost/app
```

Local MySQL was not running. The command was rerun with the project SQLite DB:

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. \
  backend/.venv/bin/python backend/scripts/export_analytics_parquet.py \
  --dataset daily_bars \
  --months 24 \
  --output-root /tmp/gupiao-analytics-acceptance \
  --no-create-backfill-task
```

Result: pass.

Manifest summary:

| Metric | Value |
| --- | ---: |
| dataset_version | `daily_bars_20260604063805` |
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
| quality_status | `ok` |
| backfill_task_id | null |

Manifest:

```text
/tmp/gupiao-analytics-acceptance/manifests/daily_bars_20260604063805.json
```

## Blocked / No Data Sample

Unit coverage creates an empty test DB and verifies:

- `check_daily_bars_24m_quality(...).as_dict()["canonical_status"] == "no_data"`
- `create_backfill_task=True` enqueues `data_backfill_24m`
- `analytics_quality_check` can consume a Manifest and return `status=no_data`
- `strategy_24m_duckdb_report` records `status=blocked_by_data`, `ok=false`, and
  Markdown/JSON artifacts

This preserves the rule that missing 24-month data must not silently pass and
must not generate fake bars.

## DuckDB Report Sample

Command:

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. \
  backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --months 24 \
  --output-root /tmp/gupiao-analytics-acceptance \
  --output-md /tmp/gupiao-strategy-24m-duckdb-report.md \
  --output-json /tmp/gupiao-strategy-24m-duckdb-report.json
```

Result:

```json
{"status": "ok", "output_md": "/tmp/gupiao-strategy-24m-duckdb-report.md", "output_json": "/tmp/gupiao-strategy-24m-duckdb-report.json"}
```

## Tests

B2 targeted tests:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_production_chain.py \
  backend/tests/test_analytics_worker_handlers.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  -q
```

Result:

```text
18 passed, 1 warning
```

Existing analytics regression:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_layer.py \
  backend/tests/test_analytics_worker.py \
  backend/tests/test_strategy_24m_duckdb_report.py \
  backend/tests/test_platform_modular_architecture_phase3.py \
  -q
```

Result:

```text
17 passed, 1 warning
```

The warning is the existing local `urllib3` LibreSSL warning.

## Production Sorting Verdict

B2 does not change production sorting or trading facts. It only improves the
analysis/report worker chain and data-quality states. `strategy_policy`,
priority board, low-buy scoring, front-row weighted scoring, `production_score`,
and paper-trading facts are unchanged.

