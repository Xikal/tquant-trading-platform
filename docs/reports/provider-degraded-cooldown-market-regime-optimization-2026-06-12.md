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

## 2026-06-12 Configurable Cooldown Follow-Up

### Reason

Follow-up read-only scheduler logs showed `fetch_board_breadth_frame` provider warnings still repeating roughly every 90-135 seconds. The previous in-process degraded guard worked, but its 60 second cooldown was shorter than the scheduler market-regime prewarm interval and too short for the current EastMoney/OpenBB/AkShare board-breadth outage pattern.

### Change

Files changed:

- `backend/app/core/config.py`
- `backend/app/services/market/regime.py`
- `backend/tests/test_market_regime_strategy_p2.py`

The hard-coded market-regime provider degraded cooldown was replaced with declared runtime setting:

```text
MARKET_REGIME_PROVIDER_DEGRADED_COOLDOWN_SECONDS=300
```

Default behavior is now 300 seconds. Invalid or unavailable settings fall back to 300 seconds. This aligns degraded board-breadth retry cadence with the existing `runtime_market_regime_refresh_interval_seconds=300` default and reduces repeated scheduler-side provider fallback pressure.

### Behavior Kept

- Live provider data is still used when available.
- Half-open recovery still happens after the cooldown.
- Cached/warming snapshots remain explicitly marked as cached/warming.
- No low-buy production policy, `production_score`, priority-board ordering, or strategy semantics changed.

### Local Verification

Executed locally:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

Results:

- Market regime / provider contracts: `28 passed`
- Plan-required platform/runtime/deploy regression: `75 passed`
- Low-buy / priority-board / production-scoring guard: `32 passed`

### Planned Online Scope

If online provider warnings remain active, the safe rollout scope is scheduler-only:

- Upload `backend/app/core/config.py` and `backend/app/services/market/regime.py`.
- Build `runtime-scheduler`.
- Recreate `runtime-scheduler` only.

Not included:

- No `.env` change.
- No app/API restart.
- No core `runtime-worker` restart.
- No MySQL/Redis/Go/frontend/nginx change.
- No DB write.
- No Docker cleanup.
- No D5 scheduler embed or standalone scheduler stop.

### Scheduler-Only Rollout Evidence

Because the 15 minute pre-check still showed `38` scheduler provider warning lines, the configurable cooldown change was promoted to the standalone scheduler only.

| Item | Evidence |
|---|---|
| Time | `2026-06-12 03:10 CST` |
| Backup | `/home/ubuntu/gupiao-upload/.runtime/manual-hotfix-backups/provider-cooldown-v5-20260612031024` |
| Uploaded sources | `backend/app/core/config.py`, `backend/app/services/market/regime.py` |
| Build | `sudo docker compose -f docker-compose.mysql.yml build runtime-scheduler` |
| Recreate | `sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-scheduler` |
| Scheduler before | `2026-06-11T18:27:50.700769863Z restart=0 healthy` |
| Scheduler after | `2026-06-11T19:10:38.732100058Z restart=0 healthy` |
| Worker unchanged | `2026-06-11T16:33:27.439851625Z restart=0 healthy` before and after |
| App unchanged | `2026-06-11T15:40:10.021531795Z restart=0 healthy` before and after |
| MySQL unchanged | `2026-06-11T15:42:42.993726302Z restart=0 oom=false healthy` before and after |
| Runtime setting | `market_regime_provider_degraded_cooldown_seconds=300.0`, default `300.0` |
| `/readyz` | `200`, `0.003822s` immediately after rollout |

Six minute post-rollout observation:

| Checkpoint | Provider warning count since scheduler restart | Interpretation |
|---|---:|---|
| `03:11 CST` | `8` | initial startup probe |
| `03:12 CST` | `8` | no 90s repeat |
| `03:13 CST` | `8` | no 90s repeat |
| `03:14 CST` | `8` | no 90s repeat |
| `03:15 CST` | `8` | no 90s repeat |
| `03:16 CST` | `11` | single recovery probe after roughly 5 minutes |
| `03:17 CST` | `13` | same recovery probe completed |

This confirms the active warning cadence changed from roughly 90-135 seconds to the intended 300 second degraded-retry cadence. The gate collector still reports `scheduler_provider_warnings_present` because its 30 minute log window includes the initial startup and 5 minute recovery probe. D5 scheduler embed remains closed until a full trading-day gate passes.

Additional latest gate evidence:

```text
generated_at=2026-06-11T19:17:37Z
host_time=2026-06-12 03:17:33 CST
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete, scheduler_provider_warnings_present
warnings=scheduler_provider_warnings_present, mysql_slow_queries=51
```

### Gate Evaluation Follow-Up

The D5 gate collector previously treated any scheduler provider log line as a D5 blocker. After the cooldown rollout, that was too coarse: a single scheduled recovery probe every 300 seconds is expected and does not represent sustained provider pressure. The evaluator now distinguishes:

- `scheduler_provider_warning_lines=<n>`: D5 blocker when provider log lines in the collection window are at or above `scheduler_provider_warning_blocking_lines`, default `20`.
- `scheduler_provider_warning_lines_observed=<n>`: warning only when low-frequency provider recovery probes are present below the blocking threshold.

This keeps D5 conservative for sustained provider failure bursts while allowing controlled cooldown recovery probes to be observed without permanently blocking scheduler embed readiness.

Latest collector after this evaluator change:

```text
generated_at=2026-06-11T19:22:37Z
host_time=2026-06-12 03:22:33 CST
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete
warnings=scheduler_provider_warning_lines_observed=18, mysql_slow_queries=51
```

The full trading-day requirement is still incomplete, so D5 embedded scheduler remains closed.

## 2026-06-12 Exponential Backoff Follow-Up

### Reason

Follow-up scheduler log review showed the fixed `300` second degraded cooldown still allowed one full `fetch_board_breadth_frame` provider recovery probe on every scheduler market-regime tick during sustained provider outage. Each probe can still traverse local, EastMoney, AkShare, and OpenBB before returning cached/warming state, so a two-hour D5 collector window can still exceed the sustained provider pressure threshold.

### Change

Files changed:

- `backend/app/core/config.py`
- `backend/app/services/market/regime.py`
- `backend/tests/test_market_regime_strategy_p2.py`
- `docker-compose.mysql.yml`
- `.env.deploy.local.example`
- `scripts/verify_platform_budget.py`
- `backend/tests/test_platform_budget_verifier.py`

The market-regime degraded guard now tracks consecutive failed board-breadth probes per operation and applies bounded exponential backoff:

```text
MARKET_REGIME_PROVIDER_DEGRADED_COOLDOWN_SECONDS=300
MARKET_REGIME_PROVIDER_DEGRADED_COOLDOWN_MAX_SECONDS=1800
MARKET_REGIME_PROVIDER_DEGRADED_BACKOFF_FACTOR=2
```

Default retry cadence under sustained provider outage becomes approximately:

| Consecutive failed probe | Cooldown |
|---:|---:|
| 1 | `300s` |
| 2 | `600s` |
| 3 | `1200s` |
| 4+ | `1800s` |

The failure counter resets after a successful live board-breadth frame. Invalid or missing settings fall back to safe defaults. Compose now passes the three setting values to `app`, `runtime-worker`, and `runtime-scheduler`, and the platform budget verifier includes them in the safe read-only environment snapshot.

### Behavior Kept

- Live provider data is still used when available.
- Cached/warming snapshots remain explicitly marked as cached/warming.
- Provider recovery is delayed during sustained outage, not disabled permanently.
- No low-buy production policy, `production_score`, priority-board ordering, or strategy semantics changed.
- D5 scheduler embed remains closed until full trading-day gate passes.

### Local Verification

Executed locally:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_resource_gate_observation.py backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

Results:

- Market regime / provider contracts: `30 passed`
- Plan-required platform/runtime/deploy/gate regression: `85 passed`
- Low-buy / priority-board / production-scoring guard: `32 passed`

### Operations Not Executed

- No online `.env` change.
- No online deploy in the local-code verification step above.
- No container restart/recreate/remove in the local-code verification step above.
- No D5 scheduler embed.
- No standalone scheduler stop.
- No DB write.
- No schema/index change.
- No MySQL/Redis/Web/API/Go/frontend/nginx change.
- No Docker cleanup.

## 2026-06-12 Scheduler-Only Online Backoff Rollout

### Pre-Check

Before the rollout, a read-only online check showed the platform was available but scheduler board-breadth provider pressure was still sustained:

| Area | Evidence |
|---|---|
| Time | `2026-06-12 03:56 CST` |
| `/readyz` | `200`, `0.003658s` |
| Host | load `0.43 / 0.34 / 0.27`; memory available `1389MiB`; swap used `653MiB / 1987MiB` |
| Scheduler | `tquant-runtime-scheduler-mysql` healthy; `252.1MiB / 640MiB`; started `2026-06-11T19:10:38Z` |
| Worker | healthy; `273.5MiB / 768MiB`; started `2026-06-11T16:33:27Z` |
| App | healthy; `60.05MiB / 768MiB`; started `2026-06-11T15:40:10Z` |
| MySQL | healthy; `860.5MiB / 1.5GiB`; started `2026-06-11T15:42:42Z` |
| Scheduler provider warnings | `30` lines in the previous 30 minutes, repeating roughly every scheduler market-regime tick |

### Scope

Because the pressure originated in scheduler-side market-regime prewarm, the rollout was intentionally scheduler-only.

| Item | Evidence |
|---|---|
| Backup | `/home/ubuntu/gupiao-upload/.runtime/manual-hotfix-backups/provider-backoff-20260612035652` |
| Uploaded sources | `backend/app/core/config.py`, `backend/app/services/market/regime.py`, `docker-compose.mysql.yml`, `scripts/verify_platform_budget.py` |
| Build | `sudo docker compose -f docker-compose.mysql.yml build runtime-scheduler` |
| Recreate | `sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-scheduler` |
| Scheduler after | started `2026-06-11T19:57:06.919385169Z`, restart `0`, healthy |
| Worker unchanged | started `2026-06-11T16:33:27.439851625Z` before and after |
| App unchanged | started `2026-06-11T15:40:10.021531795Z` before and after |
| MySQL unchanged | started `2026-06-11T15:42:42.993726302Z` before and after |
| Redis/Go unchanged | Redis and Go service start times unchanged in final inspect |
| Runtime setting | `300.0 1800.0 2.0` inside `tquant-runtime-scheduler-mysql` |
| `/readyz` after rollout | `200`, `0.005372s` immediately after recreate |

### Short Observation

Board-breadth provider warning cadence after the scheduler-only rollout:

| Checkpoint | Count since scheduler restart | Interpretation |
|---|---:|---|
| `03:57 CST` | `5` | initial startup probe |
| `03:59 CST` | `5` | no 90s repeat |
| `04:00 CST` | `5` | no short repeat |
| `04:02 CST` | `5` | no immediate fixed-tick repeat |
| `04:03 CST` | `10` | second failed probe after roughly 5 minutes |
| `04:04-04:12 CST` | `10` | no third probe on the old 5 minute cadence |
| `04:13 CST` | `15` | third failed probe after roughly 10 minutes, matching backoff |
| `04:14 CST` | `15` | stable after third probe |

Resources remained stable in the same window:

| Container | Observed range |
|---|---|
| `tquant-runtime-scheduler-mysql` | about `250-296MiB / 640MiB`; transient CPU spikes returned to idle |
| `tquant-runtime-worker-mysql` | about `276-296MiB / 768MiB` |
| `tquant-mysql` | about `862-863MiB / 1.5GiB` |
| `/readyz` | always `200` in the short observation loop |

### Gate Refresh

The formal collector after the scheduler-only rollout reported:

```text
status=warning
blocking=none
warnings=scheduler_provider_warning_lines_observed=18, mysql_slow_queries=55
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete
```

The provider warning condition is no longer a D5 blocker in the fresh 30 minute window, but D5 remains closed because the required full trading-day observation is still incomplete.

Live platform budget verifier after the rollout:

```text
status=ok
warnings=none
blocking=none
```

### Operations Not Executed In This Rollout

- No online `.env` change.
- No app/API restart.
- No core `runtime-worker` restart.
- No MySQL/Redis/Go/frontend/nginx change.
- No DB write.
- No schema/index change.
- No Docker cleanup.
- No D5 scheduler embed.
- No standalone scheduler stop.
