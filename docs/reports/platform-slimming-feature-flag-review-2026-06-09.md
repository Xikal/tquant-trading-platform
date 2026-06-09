# 平台瘦身 Feature Flag 复核（2026-06-09）

## 结论

本轮只复核和记录，不启用、不关闭、不删除任何能力。生产排序、`production_score`、priority board 口径不变。

总体状态：

- 研究/ML/因子后台 job 环境开关默认关闭，当前本地 Settings 读取也为关闭。
- AKeyLevel、trading_experience、leader pullback 属数据库 feature flag 默认关闭或 research/backtest-only 入口，未接入生产排序。
- Agent provider 默认 `none`，写工具默认关闭；本地存在 agent token/Hermes URL 配置，但 provider 仍为 `none`，不代表生产闭环启用。
- `notification_signal_scan_enabled=True` 与 `agent_daily_report_push` 存在运行入口，但通知通道未配置时服务会降级跳过；该能力记录为 `optional_integration`，不是生产排序依赖。

## 环境与默认值证据

代码默认值：

- `backend/app/core/config.py`
  - `tquant_research_jobs_enabled=False`
  - `tquant_ml_jobs_enabled=False`
  - `tquant_factor_jobs_enabled=False`
  - `tquant_strategy_evolution_enabled=False`
  - `trading_experience_suite_enabled=False`
  - `trade_review_suite_enabled=False`
  - `vp_position_tags_enabled=False`
  - `relative_strength_board_enabled=False`
  - `holding_discipline_assistant_enabled=False`
  - `limit_up_followthrough_enabled=False`
  - `t_trade_discipline_enabled=False`
  - `platform_autopilot_notify_enabled=False`
  - `agent_provider="none"`
  - `agent_enable_write_tools=False`
  - `agent_enable_notify_tools=False`
- `backend/app/services/shared/feature_flags.py`
  - `strategy_leader_pullback_band_enabled=False`
  - `a_key_level_engine_enabled=False`
  - `trading_experience_suite_enabled=False`
  - 交易经验子 flag 全部 `False`

本地当前 Settings 读取：

```text
tquant_research_jobs_enabled=False
tquant_ml_jobs_enabled=False
tquant_factor_jobs_enabled=False
tquant_strategy_evolution_enabled=False
trading_experience_suite_enabled=False
trade_review_suite_enabled=False
vp_position_tags_enabled=False
relative_strength_board_enabled=False
holding_discipline_assistant_enabled=False
limit_up_followthrough_enabled=False
t_trade_discipline_enabled=False
agent_provider=none
agent_enable_write_tools=False
agent_enable_notify_tools=True
notification_signal_scan_enabled=True
platform_autopilot_notify_enabled=False
runtime_agent_daily_report_interval_seconds=300
hermes_api_url_set=True
hermes_api_key_set=False
agent_api_token_set=True
```

说明：

- `agent_enable_notify_tools=True` 是本地环境值；由于 `agent_provider=none` 且通知 channel 依赖 webhook/Hermes 配置，记录为 optional integration，不改变生产链路。
- `a_key_level_engine_enabled` 和 `strategy_leader_pullback_band_enabled` 是数据库 feature flag，不是 `Settings` 字段；默认值来自 `_DEFAULT_FLAGS`。
- 本轮未写数据库、未改环境文件、未改 compose。

## Flag 状态表

| 能力 | 控制项 | 默认值 | 当前本地值 | 入口/任务状态 | 本轮状态 |
|---|---|---:|---:|---|---|
| Research jobs | `TQUANT_RESEARCH_JOBS_ENABLED` / `settings.tquant_research_jobs_enabled` | False | False | `background_jobs.py` 与 `runtime_worker.py` 双层门控 | `default_off` |
| ML jobs | `TQUANT_ML_JOBS_ENABLED` / `settings.tquant_ml_jobs_enabled` | False | False | `_ml_jobs_enabled()` 需 research 同时开启 | `default_off` |
| Factor jobs | `TQUANT_FACTOR_JOBS_ENABLED` / `settings.tquant_factor_jobs_enabled` | False | False | `_factor_jobs_enabled()` 需 research 同时开启 | `default_off` |
| Strategy evolution | `settings.tquant_strategy_evolution_enabled` | False | False | 需 research 同时开启 | `research_only` |
| Strategy validation monthly | `strategy_validation_monthly_enabled=True` + research gate | True + research False | research False | 只有 research gate 开启才注册 | `research_only` |
| AKeyLevel | `a_key_level_engine_enabled` | False | 未查 DB，本轮不写 | `/api/key-levels/*` 关闭时返回 blocked/stale，不请求时重算 | `default_off` |
| Trading experience suite | `trading_experience_suite_enabled` | False | False | 子能力依赖总开关 | `default_off` |
| Trade review | `trade_review_suite_enabled` | False | False | 依赖 trading experience suite | `default_off` |
| VP position tags | `vp_position_tags_enabled` | False | False | 依赖 trading experience suite | `default_off` |
| Relative strength board | `relative_strength_board_enabled` | False | False | 依赖 trading experience suite | `default_off` |
| Holding discipline assistant | `holding_discipline_assistant_enabled` | False | False | 依赖 trading experience suite | `default_off` |
| Limit-up followthrough | `limit_up_followthrough_enabled` | False | False | 依赖 trading experience suite | `default_off` |
| T trade discipline | `t_trade_discipline_enabled` | False | False | 依赖 trading experience suite | `default_off` |
| Leader pullback band | `strategy_leader_pullback_band_enabled` | False | 未查 DB，本轮不写 | metadata 为 `backtest_only` / research | `research_only` |
| Agent provider | `AGENT_PROVIDER` / `settings.agent_provider` | `none` | `none` | Agent route 可存在，但 provider 未启用 | `default_off` |
| Agent write tools | `agent_enable_write_tools` | False | False | 写工具默认禁止 | `default_off` |
| Agent notify tools | `agent_enable_notify_tools` | False | True | 本地值开启，但 provider none，记录为可选通知集成 | `optional_integration` |
| Priority notification scan | `notification_signal_scan_enabled` | True | True | 通知通道未配置则服务降级跳过 | `optional_integration` |
| Platform autopilot notify | `platform_autopilot_notify_enabled` | False | False | 不发送 autopilot 通知 | `default_off` |

## 不接入生产排序的证据

- `strategy_engine` 仍按 shadow/parity/boundary 测试处理，生产排序仍由 low-buy production scoring / priority board 负责。
- `runtime_worker.py` 对 research、ML、factor task 有执行前门控：
  - research task 未开 `TQUANT_RESEARCH_JOBS_ENABLED` 会抛出 disabled。
  - ML task 未开 `TQUANT_ML_JOBS_ENABLED` 会抛出 disabled。
  - factor task 未开 `TQUANT_FACTOR_JOBS_ENABLED` 会抛出 disabled。
- AKeyLevel route 在 flag 关闭时返回 blocked 结果，不允许请求时同步刷新。
- trading_experience service 的所有子入口依赖 suite flag 和子 flag。

## 后续建议

- 若要进一步瘦身 Agent 通知链路，先做线上只读调用观测，再决定是否标 OpenAPI deprecated；本轮不改。
- 若要迁移 AKeyLevel/trading_experience 到归档候选，需先确认产品周期内不启用，并保留现有测试与恢复路径。

