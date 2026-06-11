# Daily Bar Coverage Read Model Optimization - 2026-06-12

## Scope

This is a D6 local implementation step for `docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md`.

The change reduces MySQL pressure from daily-bar coverage queries without changing strategy policy, `production_score`, priority-board ordering, or low-buy scoring semantics.

## Change

`backend/app/repositories/low_buy/daily_history.py` now builds a small repository-local coverage read model for recent daily-bar dates:

1. Fetch recent distinct `trade_date` candidates first.
2. Count stock rows only for those candidate dates through `trade_date IN (...)`.
3. Reuse the counted values inside the same repository instance for `latest_complete_trade_date()` and `stock_count_by_trade_date()`.

This replaces the previous hot path where `latest_complete_trade_date()` grouped over `daily_bar_snapshots` with `trade_date <= max_trade_date`, which production evidence showed could scan large date ranges.

## Why This Is Low Risk

| Area | Decision |
|---|---|
| Schema | No new table, index, migration, or DB write. |
| Strategy semantics | Unchanged. |
| `production_score` | Unchanged. |
| Priority board ordering | Unchanged. |
| Raw history fetch | `fetch_rows`, `fetch_rows_for_symbols`, and `fetch_light_rows_for_symbols` behavior unchanged. |
| Fallback | If no candidate dates exist, the coverage read model returns empty and callers keep existing fallback behavior. |

## Evidence

The new repository test verifies the query shape:

- `latest_complete_trade_date()` returns the same complete latest date.
- `stock_count_by_trade_date()` reuses the repository-local coverage count.
- The coverage query uses `trade_date IN (...)` for recent candidate dates instead of an unbounded `trade_date <= ... GROUP BY` range.

## Validation

```text
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_repositories.py::LowBuyRepositoryTests::test_daily_history_coverage_queries_only_count_recent_candidate_dates
1 passed, 1 LibreSSL warning

PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_repositories.py backend/tests/test_low_buy_trade_date_read_paths.py backend/tests/test_latest_data_close_refresh.py
26 passed, 1 LibreSSL warning

PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_repositories.py backend/tests/test_low_buy_trade_date_read_paths.py backend/tests/test_latest_data_close_refresh.py backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
58 passed, 1 LibreSSL warning

PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
74 passed, 1 LibreSSL warning

git diff --check
PASS
```

## Not Executed

- No online deploy.
- No `.env` change.
- No container restart.
- No DB write.
- No schema/index change.
- No Docker cleanup.
- No scheduler embed.
- No nginx/systemd change.

## Next Step

Run the full required D6 regression set and then decide whether to deploy this small read-path optimization in a controlled backend/runtime rollout. Online deployment remains a separate action even though the user has broadly authorized the project goal; D5 scheduler embed still requires the complete trading-day gate.
