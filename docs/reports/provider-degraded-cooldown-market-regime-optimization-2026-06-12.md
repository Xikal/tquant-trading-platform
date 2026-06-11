# Provider Degraded Cooldown Market Regime Optimization - 2026-06-12

## Scope

This D6 change reduces scheduler pressure when market data providers are already circuit-open or repeatedly failing. It affects market-regime refresh behavior only; it does not change low-buy production policy, `production_score`, priority-board ordering, or strategy semantics.

The first implementation was local-only. It was later promoted through a scheduler-only online rollout after D5 remained blocked by provider warnings. No online `.env`, database schema, production data, nginx/systemd, MySQL, Redis, Web/API, Go service, or core `runtime-worker` change was made in this provider-degraded rollout.

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

`MarketProviderRouter` exposes `all_providers_circuit_open(operation)`, a read-only circuit snapshot check. `MarketRegimeMixin.get_market_regime()` uses it for `fetch_board_breadth_frame`:

- If all providers for board breadth are circuit-open and a persisted market-regime snapshot exists, return that cached snapshot and avoid live provider calls.
- If all providers are circuit-open and no persisted snapshot exists, return a lightweight `warming` snapshot and avoid live provider calls.
- If circuits are not all open, first-run and half-open recovery probes still use the existing live provider path.
- If a live call is attempted but returns no board frame, the code now prefers a persisted snapshot before doing further provider-backed emotion/limit-down work.
- If a live board-breadth call fails, the process records a short degraded cooldown and subsequent calls prefer cached/warming snapshots instead of immediately repeating the provider fallback chain.
- Concurrent callers share an in-process probe guard, so a second market-regime refresh does not launch another live board-breadth probe while one is already in flight.

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
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py backend/tests/test_cloud_resource_gate_observation.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

Results:

- Targeted provider/regime tests: `3 passed`
- Market regime related tests: `18 passed`
- Wider market/provider tests: `19 passed`
- Follow-up market regime/provider regression: `26 passed`
- Plan-required platform/runtime/deploy/gate regression: `81 passed`
- Low-buy / priority-board / production-scoring guard: `32 passed`

## Risk

When every provider is circuit-open, market regime may briefly use cached or lightweight `warming` state until the circuit window expires. This is safer than repeated live fallback bursts under provider outage, and the returned snapshot remains explicitly marked cached/warming rather than pretending to be fresh live data.

## Scheduler-Only Online Rollout

This mitigation was deployed to the standalone scheduler only because the repeated provider work originated in scheduler-side market-regime prewarm. The rollout intentionally kept app/API, core `runtime-worker`, MySQL, Redis, Go hot-read/scan services, frontend/nginx, DB data, volumes, nginx/systemd, and cleanup paths untouched.

| Item | Evidence |
|---|---|
| Initial backup | `/home/ubuntu/gupiao-upload/.runtime/manual-hotfix-backups/provider-cooldown-20260612021554` |
| Follow-up backups | `provider-cooldown-v2-20260612022004`, `provider-cooldown-v3-20260612022348`, `provider-cooldown-v4-20260612022738` under `.runtime/manual-hotfix-backups/` |
| Uploaded sources | first rollout: `backend/app/services/market/providers/router.py`, `backend/app/services/market/regime.py`; follow-ups: `backend/app/services/market/regime.py` |
| Build | `sudo docker compose -f docker-compose.mysql.yml build runtime-scheduler` |
| Recreate | `sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-scheduler` |
| Scope check | `worker_unchanged=yes`, `app_unchanged=yes`, `mysql_unchanged=yes` |
| D5 status after rollout | still blocked: `full_trading_day_observation_incomplete`, `scheduler_provider_warnings_present`, `runtime_nonterminal_task_count=2` |

## Post-Rollout Gate Snapshot

Latest gate collector after the final scheduler-only rollout:

```text
generated_at=2026-06-11T18:29:46Z
host_time=2026-06-12 02:29:42 CST
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2
warnings=scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, mysql_slow_queries=48
```

Resource and availability evidence:

| Area | Evidence |
|---|---|
| Host | load `0.54 / 0.73 / 0.65`; memory available `1392MiB`; swap used `33.47%` |
| Scheduler | `261.1MiB / 640MiB`, CPU sample `15.70%`, healthy |
| Worker | `294.8MiB / 768MiB`, healthy |
| MySQL | `849.3MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=48` |
| HTTP/pages | `/readyz` `200`; `/next/monitor`, `/next/monitor/market`, `/next/strategy-tracking`, `/next/analysis`, `/next/backtest`, `/next/data`, `/next/settings` all `200` |
| Residual warning | final scheduler logs no longer showed the earlier intraday fallback chain, but board-breadth provider warnings still appeared |

## Operations Not Executed

- No online `.env` change in this provider rollout.
- No MySQL/Redis/Web/API/Go/core `runtime-worker` restart.
- No scheduler embed cutover.
- No standalone scheduler stop.
- No DB write.
- No schema/index change.
- No nginx/systemd change.
- No Docker cleanup/image prune/volume prune.
- No production strategy, `production_score`, or priority-board ordering change.

## Next

Run the plan-required regression set before commit:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

D5 scheduler embed remains closed until full trading-day observation proves provider pressure, worker RSS, MySQL, swap, and runtime queue dedupe are stable. The next safe action is a full trading-day collector run, not stopping `runtime-scheduler`.
