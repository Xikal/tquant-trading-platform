# Trust And Data-Quality Expansion Implementation Plan (2026-05-30)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans，按 Task 逐步实现。Steps 用 `- [ ]` 跟踪。
>
> **定位：** 这是两件“做深核心闭环、不扩广度”的高 ROI 工程，**一次到位、非过渡、非过度**。两件事按依赖排序，各自独立可合入/回滚：
> - **Batch D｜数据质量 SLA + 修复管道（地基，先做）**：把数据可靠性变成可监控、可自动修复、可门控的一等子系统。
> - **Batch E｜真实战绩漂移监控（信任，后做）**：把生产信号的“回测预期 vs 真实已实现”做成持续对比与告警，作为平台信任锚点。
>
> **强制原则（防过度设计）：** 不引入新预测/ML、不新建组合引擎、不造通用告警框架、不加新存储技术。全部复用：DuckDB 分析层、RuntimeTask 队列、`analytics-worker`、`portfolio_backtest_metrics`（max5/max10 唯一实现）、paper 真实成交、feishu/agent 通知、既有 `analytics/quality.py`。
>
> **前置依赖：** 与在途 8 方向 `decision_context` 扩展**解耦**——本计划只依赖已稳定提交的基础设施，不依赖那批未合入的 gate 层。

**Goal:** ① 让“数据是否可信、缺在哪、怎么修”可见、可自动修复、可门控；② 让“跟着生产榜做，真实会怎样、相对回测漂移多少”可量化、可追溯、可告警，从而把平台从“信号展示”升级为“可信赖的决策闭环”。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL, DuckDB, RuntimeTask DB queue, React, TypeScript, Ant Design, Vite, Vitest, Pytest（**均为现有栈，不新增**）。

---

## Scope And Non-Goals

**In scope**
- Batch D：数据质量 SLA 指标、可复现幂等修复管道（脚本 + RuntimeTask）、数据健康看板与告警、生产/报告/漂移共用的单一数据门。
- Batch E：生产信号账本（发出即落账、无未来函数）、真实已实现收益跟踪（同回测口径）、回测预期 vs 真实漂移指标、漂移告警（advisory）、24M 报告“live vs backtest”段、前端漂移看板。

**Out of scope / Non-Goals**
- 不做收益预测、不引 ML/RL 做漂移建模（漂移只做统计对比 + 阈值）。
- 不新建任何组合模拟引擎（复用 `portfolio_backtest_metrics`）。
- 不造通用告警/调度框架（复用 feishu + RuntimeTask）。
- 不接实盘、不承诺收益、不展示“保本/稳赢”。
- 不更换 React/AntD/Vite、不引 WASM、不动 ECharts。
- 不臆造任何行情数据；修复只对无歧义脏行操作。
- 漂移结论不自动改策略分层（只作为治理/晋级证据）。

---

## 硬边界（不可跑偏 · 实现期必须始终成立）

> 任一条被破坏即视为失败，停止并回退。

1. **修复绝不臆造价格**：只对无歧义脏行（open/high/low/close≤0、high<low、不可能 OHLC、零量停牌却有价等）操作；任何变更前必须 DB 备份 + 行级 JSON 备份；**先尝试重抓数据源、失败才删**；写审计 JSON；**幂等**（重跑不重复删/不污染）。
2. **SLA 失败 → `blocked_by_data` / `degraded` + 显式原因**，绝不静默通过；生产优先榜、24M 报告、漂移监控**共用同一 SLA 事实源**，不得各算各的。
3. **战绩账本无未来函数**：信号按“发出日当时可见”数据落账；realized 收益从发出日之后开始计算；每条记录含 `signal_time` / `data_cutoff_time` / `return_start_time`；落账后**不可变**（append-only，更正走新版本行）。
4. **realized 组合口径唯一**：复用 `portfolio_backtest_metrics`（max5/max10、费用、滑点、T+1、涨跌停可成交性、同票冷却、占用资金）；**禁止新建并行组合引擎**；当 paper 自动交易开启且有真实成交时，realized 以**真实 paper 成交**为准，回测口径仅作对照。
5. **漂移只产证据与告警（advisory）**：不自动改 `strategy_policy`、不自动晋/降级；漂移结论作为 B3 晋级/治理输入。
6. **生产战绩只统计 `buy_now`/`soft_buy_now`**；`near_entry` 单列、不进生产战绩榜；尊重既有生产标的范围（剔除 ST/退市风险/创业板/科创板）。
7. **重计算只在 `analytics-worker`/`runtime-worker`**；Web 默认 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`，不新增 Web 后台 loop；前端新面板默认懒加载/折叠、走 `DataTable`/`VirtualCardList`、零 `useState/useReducer`。

---

## Existing Code Anchors（复用，勿重写）

- 数据质量基线：`backend/app/services/analytics/quality.py`（`DailyBarsQualityResult`、`check_daily_bars_24m_quality`、invalid_ohlc 检测 :114-149、`status="fail" if blockers`、enqueue 回填 :152-159）
- 行情实体：`backend/app/models/market_entities.py`（`DailyBarSnapshot`、`MinuteBarSnapshot:336`、`TickTradeSnapshot:369`）
- 回填脚本：`backend/scripts/backfill_daily_history.py`（被 `data_backfill_24m` 调用）
- 分析层：`backend/app/services/analytics/{__init__,config,exporters,manifest,duckdb_repository,report_queries,schemas}.py`
- 任务注册/消费：`backend/app/services/tasks/analytics_handlers.py: register_analytics_handlers`、入口 `backend/scripts/analytics_worker.py`、`backend/app/workers/runtime_worker.py: _execute_task`
- 组合唯一口径：`backend/scripts/low_buy_market_backtest_reporting.py: portfolio_backtest_metrics`（:679-840）+ `TradeOutcome`
- 纸面真实成交/绩效：`backend/app/services/paper/{performance.py,order.py,executor.py}`、`backend/app/services/paper/scheduler.py`（auto-trader）
- 生产信号来源：`backend/app/services/low_buy/{priority_board.py,priority_items.py,production_scoring.py,strategy_policy.py}`（生产门 `participates_in_priority_board`）
- 策略追踪：`backend/app/services/strategy_tracking_snapshot.py`、`backend/app/api/routes/strategy_tracking.py`、`frontend/src/features/strategy-tracking/`
- 报告：`backend/app/services/analytics/report_queries.py`、`backend/scripts/run_duckdb_strategy_report.py`、`docs/reports/strategy_24m_duckdb_report.md`
- 通知：`backend/app/services/feishu/*`、`backend/app/services/agent_notification_service.py`
- 前端基础：`frontend/src/ui/table/DataTable.tsx`、`frontend/src/ui/list/VirtualCardList.tsx`、`frontend/scripts/check-refactor-guard.mjs`
- 配置：`backend/app/core/config.py`（feature flag 字段写这里）

## File Structure Plan

**Batch D — Create**
- `backend/app/services/data_quality/{__init__,sla.py,repair.py,schemas.py}`
- `backend/app/models/data_quality_entities.py`（`data_quality_snapshots`、`data_repair_audits`）
- `backend/scripts/repair_invalid_ohlc.py`（可复现幂等修复 CLI）
- `backend/app/api/routes/data_quality.py`（只读 SLA 状态；admin-gated 修复触发）
- `backend/alembic/versions/20260531_0001_data_quality_sla.py`
- `frontend/src/features/settings/DataQualityPanel.tsx`（懒加载，挂在设置/管理页）
- `frontend/src/api/dataQuality.ts`
- 测试：`backend/tests/test_data_quality_sla.py`、`backend/tests/test_data_quality_repair.py`

**Batch E — Create**
- `backend/app/services/track_record/{__init__,signal_ledger.py,realized_outcome.py,drift_metrics.py,drift_alerts.py,schemas.py}`
- `backend/app/models/track_record_entities.py`（`production_signal_ledger`、`signal_realized_outcomes`、`strategy_drift_snapshots`）
- `backend/app/api/routes/track_record.py`
- `backend/alembic/versions/20260531_0002_track_record_drift.py`
- `frontend/src/features/strategy-tracking/DriftMonitorPanel.tsx`（懒加载）
- `frontend/src/api/trackRecord.ts`
- 测试：`backend/tests/test_track_record_ledger.py`、`test_track_record_realized.py`、`test_track_record_drift.py`

**Modify（两批共用）**
- `backend/app/core/config.py`（feature flags）
- `backend/app/models/entities.py`（导出新实体）
- `backend/app/api/router.py`（注册两个新 router）
- `backend/app/services/tasks/analytics_handlers.py`（注册新分析/报告任务）
- `backend/app/workers/runtime_worker.py`（注册短刷新任务 + 声明门控归属）
- `backend/app/services/analytics/report_queries.py`、`backend/scripts/run_duckdb_strategy_report.py`（报告新增数据质量段 + live-vs-backtest 段）
- `backend/app/services/analytics/quality.py`（抽出可复用的 OHLC 校验供 SLA/repair 共用，**不复制**）
- `backend/app/services/low_buy/priority_items.py`（生产信号发出时触发账本落账钩子，只读不改排序）
- `frontend/src/api/client.ts`、`frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx`、`frontend/src/features/settings/SettingsPage.tsx`
- `PRODUCTION_RUNBOOK.md`、`docs/README.md`、`docker-compose.mysql.yml`、`docs/contracts/openapi.json(.hash)`、`frontend/src/generated/api-types.ts`

## Feature Flags（`backend/app/core/config.py` 的 `AppSettings` 声明 bool 字段）

```env
DATA_QUALITY_SLA_ENABLED=true          # SLA 计算与门控
DATA_REPAIR_AUTO_ENABLED=false         # 永久谨慎：修复仅经显式 admin 触发/任务，绝不静默自动删
TRACK_RECORD_ENABLED=true              # 战绩账本与 realized 跟踪
DRIFT_ALERT_ENABLED=false              # 漂移告警，阈值线上验证稳定后再置 true
```

## Milestones（两批，依赖序：D → E）

### M0 基线（0.5d）
- `git status` 干净；`PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_strategy_24m_duckdb_report.py backend/tests/test_analytics_worker.py backend/tests/test_paper_performance_archive.py -q`；前端 `api:check && lint && test`。

### Batch D｜数据质量 SLA + 修复管道（先做，地基）
Tasks D1（实体/迁移/flags）、D2（SLA 计算）、D3（幂等修复管道+脚本）、D4（API+前端看板+任务+告警+报告段）。出口：SLA 可计算、修复可复现且幂等、生产/报告读同一数据门、看板可见。

### Batch E｜真实战绩漂移监控（后做，消费地基）
Tasks E1（账本实体/迁移）、E2（信号账本落账，无未来函数）、E3（realized 收益跟踪，复用组合口径/paper 真实成交）、E4（漂移指标+告警 advisory）、E5（API+前端漂移看板+报告 live-vs-backtest 段）。出口：每条生产信号可追溯 realized vs expected、漂移可量化告警、不自动改策略。

---

## Batch D Tasks

### Task D1: Data-Quality Entities, Migration, Flags
- Create `data_quality_entities.py`：
  - `data_quality_snapshots`: unique(`dataset_key`,`as_of_date`,`scope`); 列 `expected_days`/`actual_days`/`missing_days`/`invalid_rows`/`duplicate_rows`/`stale`/`coverage_pct`/`status(ok|warn|fail)`/`blockers_json`/`checked_at`。
  - `data_repair_audits`: unique(`repair_id`); 列 `dataset_key`/`reason`/`detected_rows_json`/`backup_path`/`refetch_result`/`deleted_rows_json`/`fabricated(bool, 必须恒 false)`/`operator`/`created_at`。
- Create migration（幂等 `op.create_table` + `downgrade`）。
- Modify `config.py` 增 `DATA_QUALITY_SLA_ENABLED`/`DATA_REPAIR_AUTO_ENABLED`。
- Test `test_data_quality_sla.py::test_schema_roundtrip`。

### Task D2: SLA Computation（复用 quality.py，不复制 OHLC 校验）
- [ ] 失败测试：注入 1 行零 OHLC → `status=="fail"` 且 `blockers` 含 `daily_bars_invalid_ohlc`；缺 3 个交易日 → `missing_days==3` 且 `status` 至少 `warn`。
- [ ] `data_quality/sla.py: compute_dataset_sla(db, dataset_key, scope, as_of)`：scope ∈ {`production_universe`,`all`}；`production_universe` 必须按既有生产范围（剔 ST/退市/创业板/科创板）统计。复用 `analytics/quality.py` 抽出的 OHLC 校验与交易日覆盖逻辑。
- [ ] 输出 `DataQualitySnapshot`，写 `data_quality_snapshots`；`minute_bars`/`tick` 数据集只算覆盖率与可用性（供后续分钟/事件方向门控），不足时显式 `unavailable`，不造分。
- [ ] 测试：production_universe 覆盖率计算、minute/tick `unavailable` 标记。

### Task D3: Idempotent Repair Pipeline + 可复现脚本（落实复审 S2-f）
- [ ] 失败测试：给定 3 行零 OHLC、重抓 mock 返回 empty → 备份文件被写、审计 `fabricated==false`、3 行被删、`invalid_rows` 归 0；**再跑一次**（幂等）→ 0 行待删、不报错、不重复写脏。
- [ ] `data_quality/repair.py: repair_invalid_ohlc(db, *, dataset_key, dry_run, refetch=True)`：流程**检测→DB 备份(`backup_database.sh` 或 dump)→行级 JSON 备份→按数据源重抓→重抓成功则覆盖、失败且无歧义脏行才删→写 `data_repair_audits`**。`DATA_REPAIR_AUTO_ENABLED=false` 时仅 `dry_run` 产出待修复清单，删除必须显式 `--apply`/admin 触发。
- [ ] `backend/scripts/repair_invalid_ohlc.py`：CLI 封装（`--dataset --as-of --dry-run/--apply --output <audit.json>`），幂等、强制备份、绝不臆造。
- [ ] 测试：dry-run 不改库；apply 前必有备份路径；重抓成功不删只覆盖；非无歧义脏行不删。

### Task D4: API + 看板 + 任务 + 告警 + 报告段
- [ ] `api/routes/data_quality.py`：`GET /api/data-quality/sla`（登录只读，返回各 dataset/scope 最新 SLA）；`POST /api/data-quality/repair`（`require_admin_auth`，触发 `data_repair_run` 任务，默认 dry-run）。
- [ ] 任务：`analytics_handlers` 注册 `data_quality_sla_refresh`、`data_repair_run`（analytics-worker 消费）；`runtime_worker` 可定时 enqueue `data_quality_sla_refresh`（轻量、不门控为 research）。
- [ ] 告警：SLA `fail` 经 `agent_notification_service`/feishu 推送（复用既有通道，无新框架）；无 webhook 时静默跳过。
- [ ] 报告：`report_queries.py` 24M 报告头部新增“数据质量 SLA”段（覆盖率/缺失/invalid/最近修复审计）；SLA `fail` 时报告 `blocked_by_data`。
- [ ] 前端 `DataQualityPanel.tsx`（懒加载，挂设置/管理页）：各 dataset 状态、缺失/invalid 计数、覆盖率趋势、最近修复审计、dry-run 触发按钮（admin）；表走 `DataTable`。
- [ ] 验收命令见 Verification(Batch D)。

---

## Batch E Tasks

### Task E1: Track-Record Entities + Migration
- `track_record_entities.py`：
  - `production_signal_ledger`: unique(`signal_date`,`strategy_key`,`symbol`); append-only; 列 `signal_state`/`production_score`/`priority_score`/`entry_zone_low/high`/`stop_loss`/`expected_horizon_returns_json`（来自回测/评分的发出时预期）/`market_regime`/`front_row_tier`/`data_quality`/`signal_time`/`data_cutoff_time`/`source_version`。
  - `signal_realized_outcomes`: unique(`ledger_id`,`horizon_days`); `return_pct`/`max_gain_pct`/`max_drawdown_pct`/`exit_reason`/`return_start_time`/`settled(bool)`/`data_quality`。
  - `strategy_drift_snapshots`: unique(`strategy_key`,`as_of_date`,`window_days`); realized vs expected：`realized_pf`/`expected_pf`/`realized_avg`/`expected_avg`/`realized_winrate`/`expected_winrate`/`realized_max5`/`backtest_max5`/`realized_max10`/`backtest_max10`/`tracking_error`/`decay_pct`/`drift_flag`/`sample_settled`。
- 迁移幂等 + downgrade。Modify `config.py` 增 `TRACK_RECORD_ENABLED`/`DRIFT_ALERT_ENABLED`。

### Task E2: Signal Ledger（落账·无未来函数）
- [ ] 失败测试：对一条 `buy_now`/`first_board` 信号落账 → 账本含 `signal_time/data_cutoff_time`、`expected_horizon_returns`，且 `near_entry` 信号**不**进生产账本（单列 watch）。
- [ ] `signal_ledger.py: capture_production_signals(db, board_items, as_of)`：仅落 `participates_in_priority_board` 且 `signal_state ∈ {buy_now, soft_buy_now}` 的项；`near_entry`/research 单独标注不计入生产战绩；`expected_horizon_returns` 取自该策略回测统计（发出时已知），不得用未来数据。
- [ ] 落账钩子：`priority_items.py` 生成生产榜后触发（只读，不改排序）；或由 `runtime_worker` 的 `signal_ledger_capture` 任务在收盘后落账（推荐后者，避免 Web 负担）。
- [ ] 测试：append-only（重复落账同日同票不产生重复行/走版本）、near_entry 排除、无未来字段。

### Task E3: Realized Outcome Tracking（复用组合口径 / paper 真实成交）
- [ ] 失败测试：给定日线序列，realized 1/3/5/10 日收益正确；`return_start` 在发出日之后；数据缺失 → `settled=false`、`data_quality=missing`，不造分。
- [ ] `realized_outcome.py`：
  - 单信号 realized：用发出日之后日线，按回测同口径（T+1、费用、涨跌停可成交性、退出规则）计算各 horizon；缺数据则 `unsettled`。
  - 组合 realized：**复用 `portfolio_backtest_metrics`**（max5/max10、同票冷却…）跑“账本信号”的真实组合；**当 paper auto-trading 开启且有真实成交时，realized 组合以真实 paper 成交/`paper/performance.py` 为准**，回测口径仅对照。
- [ ] 任务 `realized_outcome_refresh`（analytics-worker）：每日结算到期信号。
- [ ] 测试：realized horizon 计算、unsettled 标记、组合 realized 与 paper 真实成交一致性（有 paper 时）。

### Task E4: Drift Metrics + Alerts（advisory）
- [ ] 失败测试：realized PF 明显低于 expected → `drift_flag` 置位且 `decay_pct` 为负；样本不足（settled < 阈值）→ `drift_flag="insufficient_sample"`，不告警。
- [ ] `drift_metrics.py: compute_strategy_drift(db, strategy_key, window_days)`：按策略/整体/可选 regime 计算 realized vs expected（PF/avg/winrate/max5/max10/tracking_error/decay）；只统计 `buy_now`/`soft_buy_now`。
- [ ] `drift_alerts.py`：阈值（如 settled≥N 且 realized_pf < expected_pf×0.7，或滚动 decay 超阈）→ 产 `drift_flag` + 经 feishu 告警；**advisory，不自动改分层**；`DRIFT_ALERT_ENABLED=false` 时只记录不推送。
- [ ] 漂移结论写入 `strategy_drift_snapshots`，并可被 B3 晋级引擎/治理读取作为证据（只读暴露，不耦合）。
- [ ] 测试：drift 计算、insufficient_sample 不告警、advisory（无 strategy_policy 写入）。

### Task E5: API + 前端漂移看板 + 报告 live-vs-backtest 段
- [ ] `api/routes/track_record.py`：`GET /api/track-record/drift`（登录只读，按策略/窗口）、`GET /api/track-record/ledger`（分页）。
- [ ] 报告：`report_queries.py` 24M 报告新增“真实战绩 vs 回测”段（每策略 realized PF/avg/max5/max10 与 backtest 对照 + decay + settled 样本数）；口径仍“每日信号等权复利收益 + 真实组合 max5/max10”，**无裸“总收益”**。
- [ ] 前端 `DriftMonitorPanel.tsx`（策略追踪页，懒加载/折叠）：每策略 realized vs expected 对照表（`DataTable`）、decay、settled 样本、漂移标签；长列表用 `VirtualCardList`。
- [ ] 验收命令见 Verification(Batch E)。

---

## Acceptance Matrix

| 能力 | 生产行为 | 缺数据行为 | 必测 | UI |
|---|---|---|---|---|
| 数据 SLA | fail→`blocked_by_data`/降级，生产/报告/漂移共用 | 显式 fail/unavailable，不静默 | `test_data_quality_sla.py` | 数据健康面板 |
| 修复管道 | 仅 admin/任务触发，幂等、备份、不臆造 | 重抓失败才删无歧义脏行 | `test_data_quality_repair.py` | dry-run 触发 |
| 信号账本 | 仅 buy_now/soft_buy_now 落生产账本，无未来函数 | data_quality 标注，不造账 | `test_track_record_ledger.py` | （审计） |
| realized 跟踪 | 同回测口径 / paper 真实成交优先 | 缺数据 unsettled | `test_track_record_realized.py` | 漂移看板 |
| 漂移监控 | advisory，不自动改分层 | 样本不足不告警 | `test_track_record_drift.py` | 漂移看板 |

## Verification Commands

**Batch D**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_data_quality_sla.py \
  backend/tests/test_data_quality_repair.py \
  backend/tests/test_strategy_24m_duckdb_report.py \
  backend/tests/test_analytics_worker.py -q
cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head
# 幂等：连跑两次 dry-run 修复，第二次待修复数应为 0（无新脏写入时）
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/repair_invalid_ohlc.py --dataset daily_bars --dry-run --output /tmp/repair1.json
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/repair_invalid_ohlc.py --dataset daily_bars --dry-run --output /tmp/repair2.json
```

**Batch E**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_track_record_ledger.py \
  backend/tests/test_track_record_realized.py \
  backend/tests/test_track_record_drift.py \
  backend/tests/test_paper_performance_archive.py \
  backend/tests/test_strategy_24m_duckdb_report.py -q
# 报告口径硬校验（无裸“总收益”）
rg -n "^\| *总收益 *\|" docs/reports/strategy_24m_duckdb_report.md && echo "FAIL" || echo "OK"
```

**两批共用（合入前全绿）**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run api:check && npm run lint && npm run build && npm test -- --run && npm run analyze
```

## Runtime / Deploy / Runbook
- 新任务全部由 `analytics-worker`（报告/结算/SLA）或 `runtime-worker`（轻量 enqueue/落账）消费；Web 不新增后台 loop。`data_quality_sla_refresh`/`signal_ledger_capture`/`realized_outcome_refresh`/`strategy_drift_refresh`/`data_repair_run` 在对应 registry 注册并声明门控（均非 research 门控，属生产可追溯/地基）。
- `docker-compose.mysql.yml`：复用现有 `analytics-worker`，无需新容器。
- `PRODUCTION_RUNBOOK.md` 增段：如何看 SLA、如何 dry-run/apply 修复（含备份与审计路径）、如何查漂移、如何用 flag 回退、`DATA_REPAIR_AUTO_ENABLED`/`DRIFT_ALERT_ENABLED` 默认与放开条件。
- 线上验收：enqueue `data_quality_sla_refresh` → SLA 入库且 `/api/data-quality/sla` 可读；enqueue `strategy_drift_refresh` → 漂移入库且 `/api/track-record/drift` 可读；24M 报告含数据质量段 + live-vs-backtest 段；修复 dry-run 产审计、apply 必有备份。

## Rollback
```env
DATA_QUALITY_SLA_ENABLED=false   # 生产门回到既有 quality 检查
DATA_REPAIR_AUTO_ENABLED=false   # 始终
TRACK_RECORD_ENABLED=false       # 停止落账/漂移，旧功能不受影响
DRIFT_ALERT_ENABLED=false        # 停告警
```
两批独立回退：关 flag 即回到既有行为；新表保留供审计；新任务可停而不影响 Web 与既有 paper/报告。

## Definition Of Done
- Batch D：SLA 可计算且为生产/报告/漂移单一数据门；修复脚本幂等、强制备份、`fabricated` 恒 false、绝不臆造；缺数据显式 fail/unavailable；看板可见；定向 + 全量 pytest 绿、前端校验过。
- Batch E：每条生产信号可追溯 realized vs expected；realized 复用 `portfolio_backtest_metrics` / paper 真实成交，无并行引擎；账本无未来函数、append-only；漂移 advisory、不改 `strategy_policy`；报告含 live-vs-backtest 段且无裸“总收益”；定向 + 全量 pytest 绿、前端校验过。
- 通用：仅 buy_now/soft_buy_now 进生产战绩；Web 无新后台 loop；不接实盘、不承诺收益、不换前端栈；合入前 `pytest backend/tests` 全绿（含既有守卫，干净提交态非脏改动假绿）。
```
