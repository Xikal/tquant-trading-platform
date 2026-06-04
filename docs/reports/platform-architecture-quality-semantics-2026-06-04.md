# Platform Architecture Quality Semantics

Status: A2 completed  
Date: 2026-06-04  
Scope: 24-month analytics quality coverage semantics

## Problem

The previous 24M quality payload could report `coverage_pct > 100` when the
local dataset contained more trade days than the minimum required window. That
was mathematically explainable but product-facing misleading.

Observed example:

```text
required/expected trade days: 354
actual trade days: 483
old raw actual/required ratio: 136%+
```

## Change

`coverage_pct` is now a capped completeness percentage:

```text
coverage_pct = min(100, actual_trade_days / required_trade_days * 100)
```

Extra coverage is not hidden. It is reported separately as:

```text
over_coverage_trade_days = max(actual_trade_days - required_trade_days, 0)
```

## New Preferred Fields

The existing legacy fields remain for compatibility:

- `expected_days`
- `actual_days`
- `missing_days`
- `complete_trade_day_count`

The preferred report and manifest fields are:

- `required_trade_days`
- `actual_trade_days`
- `complete_trade_days`
- `missing_trade_days`
- `over_coverage_trade_days`
- `coverage_status`
- `coverage_pct`
- `complete_coverage_pct`
- `required_start`
- `required_end`
- `actual_start`
- `actual_end`

## Manifest And Report Behavior

- Parquet export writes the new coverage fields to both `manifest.coverage` and
  `manifest.quality`.
- DuckDB report generation normalizes legacy manifests that do not yet contain
  the new fields.
- Markdown reports show required, actual, complete, missing, extra, and capped
  coverage explicitly.
- Data-quality blockers still create or reference backfill tasks; no blocked,
  stale, partial, or no_data case is silently promoted.

## Verification

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_layer.py \
  backend/tests/test_analytics_worker.py \
  backend/tests/test_analytics_worker_handlers.py \
  -q
```

Result:

```text
12 passed, 1 warning
```

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --output-md /tmp/tquant_strategy_24m_duckdb_quality_check.md \
  --output-json /tmp/tquant_strategy_24m_duckdb_quality_check.json
```

Result:

```text
{"status": "ok", "output_md": "/tmp/tquant_strategy_24m_duckdb_quality_check.md", "output_json": "/tmp/tquant_strategy_24m_duckdb_quality_check.json"}
```

Generated report quality sample:

```text
required_trade_days=354
actual_trade_days=483
complete_trade_days=483
missing_trade_days=0
over_coverage_trade_days=129
coverage_pct=100.0
coverage_status=ok
```

Markdown evidence:

```text
Manifest 覆盖：required=354，actual=483，complete=483，missing=0，extra=129，coverage=100.00%
```

## Production Impact

No production trading fact source changed. DuckDB/Parquet remains an analytics
and reporting layer only.
