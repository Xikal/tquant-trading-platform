# Provider Degraded Cooldown Market Regime Optimization - 2026-06-12

## Scope

This D6 change reduces scheduler pressure when market data providers are already circuit-open. It affects market-regime refresh behavior only; it does not change low-buy production policy, `production_score`, priority-board ordering, or strategy semantics.

No online configuration, container operation, database schema, or production data was changed.

## Evidence

The D6 MySQL/runtime root-cause review recorded repeated scheduler-side provider warnings:

- `market provider circuit open`
- EastMoney spot page failures
- AkShare HTML decode failures
- provider timeout/fallback bursts while D5 scheduler embed was still closed

Those bursts make scheduler embed riskier because moving scheduler work into runtime-worker would combine provider pressure with the core worker.

## Change

Files changed:

- `backend/app/services/market/providers/router.py`
- `backend/app/services/market/regime.py`

`MarketProviderRouter` now exposes `all_providers_circuit_open(operation)`, a read-only circuit snapshot check. `MarketRegimeMixin.get_market_regime()` uses it for `fetch_board_breadth_frame`:

- If all providers for board breadth are circuit-open and a persisted market-regime snapshot exists, return that cached snapshot and avoid live provider calls.
- If all providers are circuit-open and no persisted snapshot exists, return a lightweight `warming` snapshot and avoid live provider calls.
- If circuits are not all open, first-run and half-open recovery probes still use the existing live provider path.
- If a live call is attempted but returns no board frame, the code now prefers a persisted snapshot before doing further provider-backed emotion/limit-down work.

This is a read-through degraded guard, not a permanent disable switch.

## Behavior Kept

- Fresh live market-regime snapshots still persist when provider data is available.
- `get_market_regime_fast()` continues to use cache/persisted/lightweight behavior.
- Market-regime quality still reports cached/warming status through existing `snapshot_source` and quality tag helpers.
- Strategy scoring, priority-board sorting, and production signal semantics are unchanged.

## Verification

Executed locally:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_market_regime_strategy_p2.py::MarketRegimeStrategyP2Tests::test_market_regime_uses_persisted_snapshot_when_live_provider_unavailable backend/tests/test_market_regime_strategy_p2.py::MarketRegimeStrategyP2Tests::test_market_regime_skips_live_provider_when_breadth_circuit_open backend/tests/test_v4_remaining_contracts.py::test_provider_router_reports_all_providers_circuit_open_only_when_every_provider_open
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py::test_provider_router_reports_all_providers_circuit_open_only_when_every_provider_open
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_v4_remaining_contracts.py backend/tests/test_market_routes.py backend/tests/test_market_data_quality_fields.py
```

Results:

- Targeted provider/regime tests: `3 passed`
- Market regime related tests: `18 passed`
- Wider market/provider tests: `19 passed`

## Risk

When every provider is circuit-open, market regime may briefly use cached or lightweight `warming` state until the circuit window expires. This is safer than repeated live fallback bursts under provider outage, and the returned snapshot remains explicitly marked cached/warming rather than pretending to be fresh live data.

## Operations Not Executed

- No online `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop or embed cutover.
- No DB write.
- No schema/index change.
- No nginx/systemd change.
- No cleanup.
- No deployment or cutover.

## Next

Run the plan-required regression set before commit:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

D5 scheduler embed remains closed until full trading-day observation proves provider pressure, worker RSS, MySQL, swap, and runtime queue dedupe are stable.
