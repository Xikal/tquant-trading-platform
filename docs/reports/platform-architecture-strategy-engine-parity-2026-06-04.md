# Strategy Engine Shadow Parity Local Readiness - 2026-06-04

Status: local code and tests only. Not deployed, not committed, not pushed.

## Scope

- Added a standalone Strategy Engine parity tracker for cumulative Shadow comparison.
- The tracker aggregates sample count, distinct trading days, missing rate, zero-score rate, match rate, score-delta distributions, and per-strategy breakdowns.
- The report status stays `insufficient_history` until at least 30 trading days are present.
- Local tests cover a 30 trading-day fixture and enforce the explicit boundary note: `非生产采纳依据，仅长期对照`.

## Boundaries

- Strategy Engine remains Shadow.
- `replacement_enabled=false`.
- `production_adoption_allowed=false`.
- The tracker does not write or sort `priority_board`.
- `strategy_policy.py` and `participates_in_priority_board` semantics are untouched.
- `near_entry`, `research_only`, `watch_only`, Shadow, and Paper remain outside production gates.

## Local Verification

Planned command:

`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_engine_parity_tracker.py backend/tests/test_strategy_engine_boundary.py backend/tests/test_strategy_engine_production_gate_guards.py backend/tests/test_strategy_engine_adapter_golden.py -q`

Online validation and real 30-day production shadow accumulation are pending explicit user authorization.
