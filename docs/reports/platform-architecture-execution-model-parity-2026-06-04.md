# Execution Model Parity Local Readiness - 2026-06-04

Status: local code and tests only. Not deployed, not committed, not pushed.

## Scope

- Backtest persisted previews now require a real five-session daily forward path before building Execution Model parity payloads.
- If a trade has no forward daily bars, partial bars, invalid bars, suspension, or delisting in the forward path, the preview is blocked instead of synthesizing return_1d...return_5d from final return.
- The persisted preview keeps `replacement_enabled=false` and `final_fact_source=portfolio_backtest_metrics`.
- The Backtest UI labels this payload as `Preview · 非事实源` and displays `forward_path_status`.

## Boundaries

- Production sorting and production admission are unchanged.
- `strategy_policy.py` is untouched.
- Strategy Engine remains Shadow.
- Execution Model remains Preview; it does not replace persisted backtest facts.
- DuckDB/Parquet are not used as production fact sources.

## Local Verification

- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_execution_model_forward_path_parity.py backend/tests/test_execution_model_backtest_golden.py backend/tests/test_execution_model_paper_golden.py backend/tests/test_execution_model_boundary.py backend/tests/test_backtest_engine_regression.py -q`
  - Result: `11 passed, 1 warning`

Online validation is pending explicit user authorization.
