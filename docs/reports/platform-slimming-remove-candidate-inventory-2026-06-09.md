# 平台瘦身 Remove Candidate Inventory（2026-06-09）

## 规则

- 本清单只标记状态，不删除代码、不停任务、不改 API 契约。
- P0 模块标为 `protected`，不得误归档。
- `remove_candidate` 仅表示后续可进入删除评估；真实删除需要用户单独授权、线上零调用证据、契约降级期、测试和恢复路径。
- research/shadow/ML/factor/agent 不接入生产排序。

## P0 Protected

| 模块 | 路径/入口 | 状态 | 保护原因 |
|---|---|---|---|
| low_buy production scoring | `backend/app/services/low_buy/production_scoring*` | `protected` | 生产分数、priority board 上游 |
| strategy policy | `backend/app/services/low_buy/strategy_policy.py` | `protected` | 生产策略语义边界 |
| priority board/read model/materialization | `backend/app/services/low_buy/*priority*`, `low_buy_materialization*` | `protected` | 推荐榜单、实时行动、选股宝典主链路 |
| market | `backend/app/services/market`, `backend/app/api/routes/market.py` | `protected` | 行情、市场状态、K线/实时价格 |
| paper | `backend/app/services/paper`, `backend/app/api/routes/paper*.py` | `protected` | 模拟盘闭环 |
| backtest | `backend/app/services/backtest*`, `backend/app/api/routes/backtests.py` | `protected` | 回测闭环 |
| tasks queue | `backend/app/services/tasks`, `backend/app/workers/runtime_worker.py` | `protected` | RuntimeTaskQueue、刷新/物化任务 |
| BFF monitor/workspace | `backend/app/services/bff`, `backend/app/api/routes/bff.py`, `monitor_snapshot_service.py` | `protected` | 监控页主数据和聚合 |
| OpenAPI contract | `docs/contracts/openapi.json` | `protected` | 前后端契约事实源 |
| 核心前端闭环 | `/monitor`, `/monitor/market`, `/analysis`, `/playbook`, `/strategy-tracking`, `/backtest`, `/paper`, `/data`, `/settings`, `/next/*` | `protected` | 当前产品主闭环 |

## Candidate Inventory

| 候选 | 路径/入口 | 规模 | Route/API | Job | Frontend entry | Tests | 当前状态 | 建议 |
|---|---|---:|---|---|---|---|---|---|
| ML signal | `backend/app/services/ml_signal` | 38 files / 2384 py lines | `backend/app/api/routes/ml_signals.py`, OpenAPI/generated types | `ml_signal_incremental_train_weekly`, `ml_signal_build_samples`, `ml_signal_train`；worker 受 ML gate | 无主要产品页面；generated API types 存在 | `test_phase4_phase5_foundation.py`, `test_ml_signal_drift_monitor.py`, `test_ml_online_learning_schedule.py`, `test_web_heavy_task_migration.py` | `research_only` | 保留但不接生产排序；后续若长期不用，先标 API deprecated |
| Factor mining | `backend/app/services/factor_mining` | 34 files / 1708 py lines | `backend/app/api/routes/factor_mining.py` | `factor_mining_monthly`, `factor_mining_iterate`, `factor_mining_evaluate`；worker 受 factor gate | 无主要产品页面；generated API types 存在 | `test_factor_mining.py`, `test_web_heavy_task_migration.py`, `test_runtime_task_contracts.py` | `research_only` | 保留测试，维持 default off |
| Decision context | `backend/app/services/decision_context` | 20 files / 1979 py lines | strategy tracking detail includes decision context | `decision_context_24m_report` analytics handler | `frontend-next/src/features/strategy-tracking/StrategyTrackingDetailPanel.tsx` 可展示 attribution | 多个 `test_decision_context_*`, `test_strategy_tracking.py` | `active` | 不删除；属于策略跟踪解释链路 |
| Strategy improvement | `backend/app/services/strategy_improvement` | 26 files / 1853 py lines | research/closed-loop report | strategy improvement closed-loop scripts | 无核心 UI | `test_strategy_improvement_closed_loop.py` | `research_only` | 保留，后续归档需先确认 24m/闭环报告不再使用 |
| Strategy engine | `backend/app/services/strategy_engine` | 12 files / 553 py lines | shadow/parity boundary | 无生产替代 job | 无生产排序入口 | `test_strategy_engine_boundary.py`, `test_strategy_engine_production_gate_guards.py`, `test_strategy_engine_adapter_golden.py`, `test_strategy_engine_parity_tracker.py` | `research_only` | 维持 shadow-only，不替代 low-buy 生产排序 |
| Trading experience | `backend/app/services/trading_experience`, `backend/app/api/routes/trading_experience.py` | 30 files / 2230 py lines | `/api/trading-experience/*` | `trading_experience_*` runtime task | old frontend query keys/API client exist；suite flag 默认 false | 10+ `test_trading_experience_*` | `default_off` | 维持 hidden/default-off；6 个月不用再评估 remove_candidate |
| AKeyLevel/key levels | `backend/app/services/key_levels`, `backend/app/api/routes/key_levels.py` | 22 files / 1415 py lines | `/api/key-levels/*` | key level materialization worker | old frontend `features/key-levels`; frontend-next monitor-action reads `stock_key_levels` payload | `test_key_levels_engine.py`, `test_key_levels_materialization_readiness.py` | `default_off` | 不删；flag off 时 blocked/stale，后续看是否纳入核心分析 |
| Agent API/tools | `backend/app/api/routes/agent.py`, `agent_quality.py`, `backend/app/agent_*`, `backend/app/services/agent_*` | 多 route/service | `/api/agent/*` | `agent_priority_notifications`, `agent_daily_report_push` | generated API types; no core product required path | `test_agent_*`, `test_main_timezone.py` | `optional_integration` | provider none/default write off；删除前需线上零调用和 OpenAPI deprecated |
| Old frontend ritual UI | `frontend/src/features/ritual-ui`, `frontend/src/styles/workspace/workspace-ritual.css` | 11 files | 无后端 | 无 | old frontend CSS/imports present | component tests/visual dependent possible | `active_ui_debt` | 本轮不改旧前端；后续若旧前端归档再处理 |
| Old frontend key-levels | `frontend/src/features/key-levels` | 3 files | `/api/key-levels/*` | 依赖 AKeyLevel | `MonitorMarketPage.tsx` import | `KeyLevelPanel.test.tsx` | `default_off_but_referenced` | 不删；需产品确认 |
| Old frontend trading-experience | `frontend/src/features/trading-experience`, `frontend/src/api/client.ts` trading-experience methods | 1 feature dir + API methods | `/api/trading-experience/*` | 依赖 trading experience tasks | old frontend query keys/API client exist | backend route tests | `default_off_but_referenced` | 不删；先保持 hidden |
| `docs/reports` machine artifacts with runtime refs | `front-row-weighted-production-scoring-backtest-2026-05-29.json`, `strategy-24m-backtest-2026-05-30.json`, `strategy-24m-backtest-2026-05-28.json` | 14MB+ | Dockerfile/API/scripts refs exist | scripts read/write | N/A | deploy script test, route/script tests | `blocked_archive_candidate` | 先改默认路径和 tests 后再迁移 |
| `docs/reports` machine artifacts without runtime refs | `strategy-24m-optimization-report-2026-05-28.json`, `strategy-24m-front-row-filter-backtest-2026-05-29.json`, `market-state-guard-walk-forward-2026-05-28`, `frontend-next-density-review-2026-06-06` | about 15MB | no non-doc refs found | none | none | none | `archived_this_round` | 已按 manifest 归档到 ignored artifact 目录 |

## Route/Service/Job 覆盖

- Routes covered: `ml_signals.py`, `factor_mining.py`, `research.py`, `agent.py`, `agent_quality.py`, `key_levels.py`, `trading_experience.py`, `backtests.py`, `bff.py`, `screeners.py`, `strategy_tracking.py`.
- Services covered: `ml_signal`, `factor_mining`, `decision_context`, `strategy_improvement`, `strategy_engine`, `trading_experience`, `key_levels`, agent services.
- Jobs covered: `strategy_validation_monthly`, `backtest_research_worker`, `low_buy_strategy_governance`, `strategy_self_evolution`, `ml_signal_incremental_train_weekly`, `factor_mining_monthly`, `agent_priority_notifications`, `agent_daily_report_push`, `trading_experience_*`.
- Frontend entries covered: old `frontend/src/features/ritual-ui`, `key-levels`, `trading-experience`; frontend-next generated API types and strategy detail decision context display.
- Tests covered by inventory: strategy engine boundary/gate, BFF monitor workspace, low-buy read paths, ML/factor/agent/trading-experience/key-levels focused tests.

## 未处理项

- 不做 route 拆分。`bff.py`、`backtests.py`、`screeners.py`、`strategy_tracking.py` 后续可按计划 Phase 4 单独分批处理。
- 不做 frontend-next/旧 frontend cutover 或删除。双栈收敛仍需用户单独授权。
- 不移动有运行引用的大 JSON。先保留，避免 Dockerfile/API/script/test 断裂。

