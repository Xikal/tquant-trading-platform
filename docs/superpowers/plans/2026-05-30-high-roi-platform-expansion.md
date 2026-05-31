# High ROI Platform Expansion Implementation Plan (Revised 2026-05-30)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **复审修订说明（2026-05-30）：** 本版本已按架构复审整改。主要变更：① 拆为 3 个可独立合入/回滚的批次 A/B/C，不再一次性大改；② 修正全部错误的文件/测试锚点路径（analytics worker、paper order、测试名）；③ 方向 4 强制复用既有 `portfolio_backtest_metrics`，禁止并行实现；④ 市场总闸缺数据改为降级而非全局阻断；⑤ 晋级引擎仅产出建议，禁止自动改 `strategy_policy`/自动生效 override；⑥ 方向 7 增加数据源前置验证门，无源不进生产阻断；⑦ feature flag 落到 `config.py`；⑧ 新增“硬边界”不可跑偏清单。

**Goal:** 将当前平台从“策略信号展示”扩展为“市场状态门控、板块龙头确认、风险过滤、纸面组合执行、信号归因、分钟级入场、事件风险、研究晋级”的闭环系统，提升信号质量与执行稳定性。

**Architecture:** 新增一个轻量的 `decision_context` 决策上下文层，把市场状态、板块龙头、硬风险、分钟入场、事件风险、策略分层和纸面组合执行统一写入可审计快照。现有 `strategy_policy` 继续作为策略分层唯一事实源，生产分与前排排序只消费决策上下文，不把研究策略直接推入生产分。**组合 max5/max10 只有一套实现，复用既有 `backend/scripts/low_buy_market_backtest_reporting.py: portfolio_backtest_metrics`，不得另建并行引擎。** 所有耗时刷新由 `runtime-worker` 或 `backend/scripts/analytics_worker.py`（analytics-worker 容器入口）消费 `RuntimeTask`，Web 请求只读快照和发起任务。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL, DuckDB analytics, RuntimeTask DB queue, React, TypeScript, Ant Design, Vite, Vitest, Pytest.

---

## Scope And Non-Goals

**In scope**

- 8 个高 ROI 扩展方向：
  1. 市场状态总闸
  2. 板块/龙头确认引擎
  3. 避坑过滤器
  4. 真实组合执行器（复用既有口径）
  5. 信号归因与自学习复盘
  6. 分钟级入场优化
  7. 公告/事件风险摘要
  8. 研究到生产晋级系统
- 每个方向都必须有后端可测逻辑、前端可见结果、RuntimeTask 或缓存刷新策略、报告/运行手册、回归测试。
- 所有生产建议必须带样本数、PF、平均单笔、最大回撤、max5/max10、季度稳定性、walk-forward、OOS 或明确标记“样本不足/仅研究”。

**Out of scope**

- 不接券商实盘自动下单。
- 不承诺收益，不展示“保本”“稳赢”“收益保证”文案。
- 不更换 React、AntD、Vite，不引入 WASM，不改 ECharts 基础库。
- 不把大模型作为选股决策源；大模型只可用于公告摘要、复盘摘要和可解释文本，且必须拒绝输出买卖建议。
- 不重写现有低吸策略体系；只在策略外侧增加门控、执行和归因闭环。
- 不新建第二套组合执行引擎（必须复用既有 `portfolio_backtest_metrics`）。

---

## 复审问题与处置记录（2026-05-30 计划复审留痕）

> 本节记录计划复审发现的问题与其在本计划中的处置位置，作为审计留痕。严重度：S0 阻断 / S1 高 / S2 中低。**复审结论：需修订后执行（本版本已按下表修订）。**

**结论摘要**

- 架构合规：保留 `strategy_policy` 单一事实源、`participates_in_priority_board` 生产门、RESEARCH 不给生产分、无实盘、重任务归 worker、缺数据 `blocked_by_data` —— 与 P0-A~P2-I 整改成果一致，不破坏既有成果。
- 最高 ROI / 最低风险：方向 3 避坑过滤器 + 方向 1 市场状态总闸。
- 最大风险（本版已处置）：组合执行器重复实现、市场总闸全局阻断、晋级 override 不生效、8 方向捆成大改、锚点路径错误。

**S0（阻断）**

- 无纯粹 S0：计划本身合规，所有生产副作用均挂 feature flag、可回退。最接近 S0 的是方向 7 事件风险缺数据源 —— 已记为 S1-5，并以 Task C0 数据源前置门兜底（无源则不进生产阻断）。

**S1（高优先 · 已处置）**

| 编号 | 问题 | 证据（文件:行） | 处置位置 |
|---|---|---|---|
| S1-1 | 方向 4 新建 `portfolio_executor` 与既有 `portfolio_backtest_metrics` 重复，max5/max10 口径会漂移 | `backend/scripts/low_buy_market_backtest_reporting.py:679-840` | Task B2 强制复用 + 一致性测试；硬边界 4 |
| S1-2 | 市场总闸“缺数据即 `block`”是全局单一开关，一处行情缺失会清空整个生产榜 | 原 Task A3 规则；`backend/app/services/market/regime.py`（全局单一 regime） | Task A3 Step2 缺数据分级：market-level→`reduce`+保留上一日 regime；symbol-level→`research_only` |
| S1-3 | 晋级引擎写 `StrategyTierOverride`，但生产排序用**静态** `get_tier_weight`，override 实际不生效 | `backend/app/services/low_buy/priority_scoring.py:193` vs `backend/app/services/low_buy/strategy_tier_resolver.py:30` | Task B3 写死“仅建议、不自动生效、人工改常量+守卫测试”；`PROMOTION_ENGINE_AUTO_APPLY_ENABLED` 永久 false |
| S1-4 | 多处锚点/测试路径错误：`app/workers/analytics_worker.py`、`paper/order_service.py`、`test_paper_order_risk.py` 等 4 个测试名均不存在 | 真实：`backend/scripts/analytics_worker.py`、`backend/app/services/tasks/analytics_handlers.py`、`backend/app/services/paper/order.py`、`test_paper_routes.py`/`test_paper_performance_archive.py`/`test_low_buy_intraday_confirmation.py`/`test_ai_decision_support.py` | 已全量校正 Existing Code Anchors / File Structure / 各 Task Files / Verification Commands |
| S1-5 | 方向 7 缺公告/事件数据源，无源只能造假分（违反“禁假分”） | `backend/app/services/market/event_cache.py` 不存在 | Task C0 数据源前置门；无源 `EVENT_RISK_PRODUCTION_BLOCK_ENABLED=false`，只摘要、`data_quality=missing` |
| S1-6 | 8 个方向捆成一个 `decision_context` 大改（12 Task / 9 服务 / 新表+迁移），难独立验收与回滚 | 原 File Structure Plan / M0-M6 同一迁移 | 拆 Batch A/B/C，每批独立 feature flag、独立合入与回滚 |

**S2（中低 · 已处置）**

| 编号 | 问题 | 处置位置 |
|---|---|---|
| S2-1 | feature flag（`DECISION_CONTEXT_ENABLED` 等）未落到 `config.py`，pydantic 不读未声明字段 | “Feature Flags”节 + Task A1 / 部署 Step2，Modify `backend/app/core/config.py` |
| S2-2 | 晋级测试用例用不存在的 `strategy_key="n_pattern"` | Task B3 改用真实键 `n_pattern_long_wash` |
| S2-3 | 新增 8 个 task 类型未声明是否纳入 research/ml/factor 门控 | Runtime Tasks Step1 逐个声明门控归属 |
| S2-4 | 缺“无裸‘总收益’表头”的硬校验 | Report Step4 增 `rg -n "^\| *总收益 *\|"` 硬校验 |
| S2-5 | 新前端面板可能进入首屏关键路径，重制造性能问题 | Frontend 约束：默认懒加载/折叠，`analyze` 无新首屏超大 chunk |

**复审同时确认、实现期不得回退的既有事实**

- `production_scoring.py:128` 已用 `participates_in_priority_board` 门控；`strategy_policy` CORE={`first_board`,`volume_shrink`}、AUX={`late_session_strong_support`}、N 字在 RESEARCH。
- `runtime_worker._execute_task` 未知类型抛错（`:260`）、research/ml/factor 门控（`:263-270`）；analytics 任务由 `analytics_handlers.register_analytics_handlers` 注册、`backend/scripts/analytics_worker.py` 消费。
- 前端零 `useState/useReducer`；`DataTable` 默认 virtual、`VirtualCardList` 已存在、`check-refactor-guard.mjs` 护栏生效。
- **需要实测验证（不得猜测）**：分钟/Tick 数据覆盖率、公告/事件数据源是否存在 —— 由 Task C0 在 Batch C 前完成。

---

## 硬边界（不可跑偏 · 实现期必须始终成立）

> 任一条被破坏即视为本计划实现失败，必须停止并回退。

1. **生产分仅当 `strategy_policy.participates_in_priority_board(key) is True`**；N 字（`n_pattern_long_wash` / `n_pattern_short_wash`）及其他 RESEARCH 策略恒 `production_score=None`、不进 priority board。守卫：`backend/tests/test_low_buy_production_scoring.py` 不得回退。
2. **所有门控只做“乘子 / 加减分 / 阻断标记”**，不得改写策略核心规则；不得让任务/引擎自动修改 `backend/app/services/low_buy/strategy_policy.py` 常量（常量变更只能人工提交 + 守卫测试校验）。
3. **缺数据一律走 `blocked` / `research_only` / `no_data` + 显式原因**，禁止空分、假分、TODO 占位。
4. **组合 max5/max10 只有一套实现**（复用既有 `portfolio_backtest_metrics`）；24M 报告与 Paper 组合预览必须同口径同数值。
5. **重计算只在 `runtime-worker` / `backtest-worker` / `backend/scripts/analytics_worker.py` 消费**；Web 默认 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`，不得新增 Web 后台 loop。
6. **不接实盘下单、不承诺收益、LLM 仅摘要且拒绝买卖建议**；前端不换 React/AntD/Vite、不引 WASM、不动 ECharts；新表格走 `DataTable`、长列表走 `VirtualCardList`、新增面板默认懒加载/折叠，不进首屏关键路径。

---

## Agent Execution Order

1. `trading-quant-lead`: 定义门控指标、组合约束、回测验收线、晋级阈值。
2. `stock-analysis-specialist`: 定义板块主线、龙头、情绪周期、触发/失效条件。
3. `product-strategist`: 转成页面能力、配置项、研究/生产差异和验收标准。
4. `ui-designer`: 设计监控、纸面组合、策略追踪、复盘页的信息层级。
5. `fullstack-builder`: 落地后端、前端、任务、迁移和报告。
6. `qa-tester`: 补测试、回测、异常数据、线上验收。
7. `devops-operator`: 部署、监控、回滚、运行手册。

## Existing Code Anchors（已校正真实路径）

- 策略分层事实源：`backend/app/services/low_buy/strategy_policy.py`
- 策略层级 DB override 解析器：`backend/app/services/low_buy/strategy_tier_resolver.py`（注意：当前 `priority_scoring.py:193` 用**静态** `get_tier_weight`，不读 override —— 见 Task B3 边界）
- 生产评分：`backend/app/services/low_buy/production_scoring.py`（`participates_in_priority_board` 门控在 `:128`）
- 市场状态：`backend/app/services/market/regime.py`, `backend/app/services/market/regime_scoring.py`, `backend/app/services/market/regime_types.py`
- 低吸优先板：`backend/app/services/low_buy/priority_board.py`, `backend/app/services/low_buy/priority_scoring.py`, `backend/app/services/low_buy/priority_response.py`
- 板块/龙头已有能力：`backend/app/services/low_buy/leader_strength_enrichment.py`, `backend/app/services/low_buy/mainline_strength.py`, `backend/app/api/routes/market.py`
- 硬风险已有能力：`backend/app/services/low_buy/hard_risk.py`, `backend/app/services/paper/risk_control.py`, `backend/app/services/analytics/quality.py`（`invalid_ohlc` 检测在 `:114-149`）
- **既有组合执行口径（必须复用，勿重写）**：`backend/scripts/low_buy_market_backtest_reporting.py: portfolio_backtest_metrics`（`:679-840`：max5/max10、同票冷却 `duplicate_symbol_open`、同策略≤2、同板块≤2、弱市≤40%、退潮不开仓、占用资金）
- 纸面交易：`backend/app/services/paper/order.py`（`PaperOrderService.create_order`）、`backend/app/services/paper/admission.py`、`backend/app/services/paper/executor.py`、`backend/app/services/paper/performance.py`、`backend/app/api/routes/paper*.py`、`frontend/src/features/paper/`
- 策略追踪：`backend/app/services/strategy_tracking_snapshot.py`, `backend/app/api/routes/strategy_tracking.py`, `frontend/src/features/strategy-tracking/`
- 分钟/Tick：`backend/app/models/market_entities.py` 中 `MinuteBarSnapshot`(`:336`), `TickTradeSnapshot`(`:369`)
- RuntimeTask：`backend/app/services/tasks/queue.py`, `backend/app/workers/runtime_worker.py`（`_execute_task` 未知类型抛错于 `:260`；research/ml/factor 门控 `:263-270`）
- Analytics worker：**入口脚本** `backend/scripts/analytics_worker.py`；**任务注册** `backend/app/services/tasks/analytics_handlers.py: register_analytics_handlers`
- 24M 报告：`backend/app/services/analytics/report_queries.py`, `backend/scripts/run_duckdb_strategy_report.py`
- 前端性能基础：`frontend/src/ui/table/DataTable.tsx`（默认 AntD virtual + scroll.y）, `frontend/src/ui/list/VirtualCardList.tsx`
- 前端护栏：`frontend/scripts/check-refactor-guard.mjs`（禁 useState/raw Table/slice 截断）

## File Structure Plan（已校正）

**Create**

- `backend/app/models/decision_context_entities.py`
- `backend/app/models/schema_defs/decision_context.py`
- `backend/app/services/decision_context/__init__.py`
- `backend/app/services/decision_context/snapshot_writer.py`
- `backend/app/services/decision_context/market_gate.py`
- `backend/app/services/decision_context/sector_leader_gate.py`
- `backend/app/services/decision_context/hard_risk_filter.py`
- `backend/app/services/decision_context/portfolio_executor.py`（**薄封装**：仅适配/调用既有 `portfolio_backtest_metrics`，不重实现规则）
- `backend/app/services/decision_context/signal_attribution.py`
- `backend/app/services/decision_context/intraday_entry.py`
- `backend/app/services/decision_context/event_risk.py`
- `backend/app/services/market/event_cache.py`（**新建**，且仅在 Task C0 数据源验证通过后才接生产阻断）
- `backend/app/services/decision_context/promotion_engine.py`
- `backend/app/api/routes/decision_context.py`
- `backend/alembic/versions/20260530_0002_high_roi_decision_context.py`
- `backend/tests/test_decision_context_schema.py` 等 8 个 `test_decision_context_*.py`
- `frontend/src/api/decisionContext.ts`
- 前端面板（默认懒加载/折叠）：
  - `frontend/src/features/monitor/MarketStateGatePanel.tsx`
  - `frontend/src/features/monitor/SectorLeaderGatePanel.tsx`
  - `frontend/src/features/monitor/RiskFilterBadges.tsx`
  - `frontend/src/features/paper/PortfolioExecutionPanel.tsx`
  - `frontend/src/features/strategy-tracking/SignalAttributionPanel.tsx`
  - `frontend/src/features/strategy-tracking/PromotionReviewPanel.tsx`
  - `frontend/src/features/strategy-tracking/IntradayEntryPanel.tsx`
  - `frontend/src/features/strategy-tracking/EventRiskPanel.tsx`
  - `frontend/src/features/strategy-tracking/DecisionContextDrawer.tsx`
- `docs/high-roi-platform-expansion-runbook-2026-05-30.md`

**Modify**

- `backend/app/models/entities.py`: 导出新实体。
- `backend/app/core/config.py`: **新增 6 个 feature flag 字段到 `AppSettings`**（见“Feature Flags”）。
- `backend/app/api/router.py`: 注册 `decision_context` router。
- `backend/app/workers/runtime_worker.py`: 在 `_execute_task` 增加短刷新任务类型，并声明是否纳入 research/ml/factor 门控。
- `backend/app/services/tasks/analytics_handlers.py`: `register_analytics_handlers` 注册新分析/报告任务（**不是** `backend/app/workers/analytics_worker.py`，该路径不存在）。
- `backend/app/services/low_buy/priority_scoring.py`: 接入市场、板块、风险、事件门控乘子/加分，不改变策略核心规则。
- `backend/app/services/low_buy/production_scoring.py`: 继续通过 `participates_in_priority_board` 判断生产资格。
- `backend/app/services/low_buy/priority_response.py`: 返回决策上下文字段。
- `backend/app/services/analytics/report_queries.py`: 报告增加门控、组合、归因、晋级证据。
- `backend/scripts/run_duckdb_strategy_report.py`: 报告参数增加 `include_decision_context=true`。
- `docs/contracts/openapi.json`, `docs/contracts/openapi.hash`, `frontend/src/generated/api-types.ts`: API 生成文件。
- `frontend/src/api/client.ts`, `frontend/src/features/monitor/MonitorPage.tsx`, `frontend/src/features/paper/PaperTradingPage.tsx`, `frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx`, `frontend/src/features/playbook/PlaybookPage.tsx`
- `PRODUCTION_RUNBOOK.md`, `docs/README.md`, `docker-compose.mysql.yml`

## Feature Flags（落到 `backend/app/core/config.py` 的 `AppSettings`，默认值如下）

```env
DECISION_CONTEXT_ENABLED=true
MARKET_GATE_PRODUCTION_ENABLED=true
SECTOR_LEADER_GATE_PRODUCTION_ENABLED=true
HARD_RISK_FILTER_PRODUCTION_ENABLED=true
INTRADAY_ENTRY_PRODUCTION_BOOST_ENABLED=false
EVENT_RISK_PRODUCTION_BLOCK_ENABLED=false   # 仅 Task C0 数据源验证通过后才置 true
PROMOTION_ENGINE_AUTO_APPLY_ENABLED=false   # 永久 false：晋级只产出建议
```

`config.py` 必须为每个 flag 增加 `bool` 字段（pydantic settings 不读未声明字段）。

---

## Milestones（按 3 个可独立合入/回滚的批次组织）

### M0: Baseline And Safety Gates
- Duration: 0.5 day · Owner: `trading-platform-supervisor`, `qa-tester`
- Output: 当前分支基线、测试清单、数据质量基线、线上回滚点。
- Validation:
  - `git status --short`
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_low_buy_production_scoring.py backend/tests/test_strategy_24m_duckdb_report.py -q`
  - `cd frontend && npm run api:check && npm run lint && npm test -- --run`

### Batch A（M1）: 决策上下文最小地基 + 避坑过滤器 + 市场总闸（最高 ROI / 最低风险，可独立验收）
- Tasks: A1（最小存储）、A2（避坑过滤器）、A3（市场总闸含降级）、前端 A、Runtime/Report A、Runbook。
- 不碰 `strategy_policy` 常量；不建组合执行器。
- Validation 出口：见各 Task 与 Verification Commands(Batch A)。

### Batch B（M2）: 板块/龙头 + 组合执行器（复用）+ 晋级（仅建议）
- Tasks: B1（板块/龙头）、B2（组合执行器复用）、B3（晋级仅建议）、前端 B、Report B。
- Validation 出口：组合执行器与 24M 报告数值一致；晋级面板只显示建议、无自动改层。

### Batch C（M3，需实测前置）: 归因 + 分钟入场 + 事件风险
- 前置门 C0：分钟/Tick 覆盖率实测、公告/事件数据源确认；不通过则对应方向只做研究态、不进生产阻断。
- Tasks: C1（归因）、C2（分钟入场）、C3（事件风险）、前端 C、Analytics Report C。

---

## Task A1: Decision Context Schema And Minimal Storage

**Purpose:** 建立共享审计层；**仅建最小可用结构**，后续批次按需扩字段，不一次性塞满。

**Files:**
- Create: `backend/app/models/decision_context_entities.py`
- Create: `backend/app/models/schema_defs/decision_context.py`
- Create: `backend/app/services/decision_context/snapshot_writer.py`
- Create: `backend/alembic/versions/20260530_0002_high_roi_decision_context.py`
- Modify: `backend/app/models/entities.py`, `backend/app/core/config.py`（feature flags）
- Test: `backend/tests/test_decision_context_schema.py`

- [ ] **Step 1: Write failing schema tests**

```python
from datetime import date
from app.models.schema_defs.decision_context import DecisionContextOut, GateDecisionOut


def test_decision_context_requires_all_core_gates() -> None:
    payload = DecisionContextOut(
        symbol="000001",
        trade_date=date(2026, 5, 29),
        strategy_key="first_board",
        strategy_tier="core",
        production_eligible=True,
        market_gate=GateDecisionOut(decision="allow", score=82.0, reasons=["强势修复"]),
        sector_leader_gate=GateDecisionOut(decision="allow", score=76.0, reasons=["板块扩散"]),
        hard_risk_gate=GateDecisionOut(decision="allow", score=100.0, reasons=[]),
        event_risk_gate=GateDecisionOut(decision="allow", score=100.0, reasons=[]),
        intraday_entry_gate=GateDecisionOut(decision="wait", score=55.0, reasons=["等待回踩 VWAP"]),
        final_decision="candidate",
        final_score=78.5,
        data_quality="ok",
    )
    assert payload.final_decision == "candidate"
```

- [ ] **Step 2: Run failing test** — `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_decision_context_schema.py -q`（预期 import 失败）

- [ ] **Step 3: Add schema models**（同原计划 `GateDecisionOut` / `DecisionContextOut`，`decision ∈ {allow,reduce,block,wait,research_only}`，`final_decision ∈ {front_row,candidate,watch,research_only,blocked}`，`data_quality ∈ {ok,degraded,missing,blocked}`）

- [ ] **Step 4: Add storage entities and migration**
  - `decision_context_snapshots`: unique(`trade_date`,`strategy_key`,`symbol`); index(`trade_date`,`strategy_key`,`symbol`,`final_decision`,`data_quality`); JSON 文本列 `gates_json`/`evidence_json`/`source_snapshot_json`。
  - `signal_outcome_attributions`: unique(`context_snapshot_id`,`horizon_days`); `return_pct`,`max_gain_pct`,`max_drawdown_pct`,`hit`,`exit_reason`。
  - `strategy_promotion_reviews`: unique(`strategy_key`,`review_date`,`window_days`); 含 sample/PF/avg/dd/max5/max10/季度稳定性/WF/OOS/recommendation。
  - 迁移须 `op.create_table` 幂等（先 inspector 检查），并提供 `downgrade`。

- [ ] **Step 5: Implement `DecisionContextSnapshotWriter`**（`upsert_context` / `latest_for_symbol` / `latest_board`）

- [ ] **Step 6: Run tests + migration smoke**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_decision_context_schema.py -q
cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head
```

---

## Task A2: Hard Risk And Tradability Filter（第一批最高 ROI）

**Purpose:** 对 ST、退市风险、停牌、涨跌停不可成交、异常 OHLC、流动性不足、跳空过高做生产硬过滤。建在既有 `hard_risk.py` / `quality.py` 上。

**Files:**
- Create: `backend/app/services/decision_context/hard_risk_filter.py`
- Modify: `backend/app/services/low_buy/hard_risk.py`
- Modify: `backend/app/services/paper/risk_control.py`
- Modify: `backend/app/services/paper/order.py`（`PaperOrderService.create_order`，**真实文件名是 `order.py`**）
- Modify: `backend/app/services/analytics/quality.py`
- Test: `backend/tests/test_decision_context_hard_risk_filter.py`

- [ ] **Step 1: Write failing risk filter tests**（ST → block；invalid OHLC → block，`evidence["data_quality"]=="invalid_ohlc"`）
- [ ] **Step 2: Implement block/reduce matrix**（block：is_st / 非 active / 停牌或零量 / invalid OHLC / 买在涨停无流动性 / 卖需跌停处理不可假定成交 / 上市过短 / 事件高风险；reduce：流动性不足 / 跳空过高 / 缺涨跌停元数据 / 板块或标的元数据陈旧）
- [ ] **Step 3: Integrate with paper order creation** —— `PaperOrderService.create_order` 在 hard risk block 时拒绝生产/自动单；手动单仅 `source=="manual"` 且返回 `risk_override_required=true`，无静默成交。
- [ ] **Step 4: Integrate with analytics quality** —— invalid OHLC / 缺涨跌停假设 / 不可能成交 → 报告 `blocked_by_data`（复用既有 `quality.py:114-149` 的 invalid_ohlc 阻断）。
- [ ] **Step 5: Run tests**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_hard_risk_filter.py \
  backend/tests/test_paper_routes.py \
  backend/tests/test_strategy_24m_duckdb_report.py -q
```

---

## Task A3: Market State Master Gate（含缺数据降级 · 修正全局阻断风险）

**Purpose:** 用市场状态控制火力；强势/修复允许，震荡降权，弱势/退潮减少或阻断新开仓。**市场级缺数据必须降级，不得让整个生产榜清空。**

**Files:**
- Create: `backend/app/services/decision_context/market_gate.py`
- Modify: `backend/app/services/market/regime_types.py`
- Modify: `backend/app/services/low_buy/priority_scoring.py`, `backend/app/services/low_buy/priority_response.py`
- Test: `backend/tests/test_decision_context_market_gate.py`

- [ ] **Step 1: Write failing market gate tests**（修复/强势 → allow score≥75；退潮 → block 且 reasons 含“退潮”；**新增**：`market_state` 缺失 → decision `reduce`（不是 block），reasons 含“行情数据降级”）
- [ ] **Step 2: Implement gate contract**
  - `allow`：修复/强势，强度≥0.65，跌停≤10，热点板块≥3。
  - `reduce`：震荡/轮动，强度 0.35-0.65；或涨停多但指数下行；**或市场级关键数据缺失（降级，不阻断全局）**。
  - `block`：退潮/弱势，强度<0.35，或跌停≥40，或热点板块≤1且指数下行。
  - **数据缺失分级**：market-level（regime/指数/涨跌停统计）缺失 → `reduce` + 保留上一交易日 regime + 显式 `data_quality="degraded"`；symbol-level 数据缺失 → 该票 `research_only`，不影响全局。
- [ ] **Step 3: Integrate with priority scoring**（乘子，不改策略规则）
```python
MARKET_GATE_MULTIPLIER = {"allow": 1.0, "reduce": 0.62, "wait": 0.45, "research_only": 0.0, "block": 0.0}
```
生产前排候选必须同时满足：`participates_in_priority_board(key) is True`、`market_gate.decision in {"allow","reduce"}`、`hard_risk_gate.decision != "block"`、`data_quality != "blocked"`。
- [ ] **Step 4: Add response fields** —— `market_gate_decision`/`market_gate_score`/`market_gate_reasons`/`market_firepower_multiplier`。
- [ ] **Step 5: Run tests**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_market_gate.py \
  backend/tests/test_low_buy_production_scoring.py -q
```
Expected: 门控测试通过；N 字仍无生产分、不进 priority board；market-level 缺数据时榜单降权而非清空。

---

## Task B1: Sector And Leader Confirmation Engine

**Purpose:** 过滤孤立上涨，板块扩散 + 龙头健康 + 梯队完整才放大生产信号。

**Files:**
- Create: `backend/app/services/decision_context/sector_leader_gate.py`
- Modify: `backend/app/services/low_buy/leader_strength_enrichment.py`, `backend/app/services/low_buy/mainline_strength.py`, `backend/app/api/routes/market.py`
- Test: `backend/tests/test_decision_context_sector_leader_gate.py`

- [ ] Step 1: 失败测试（宽板块+健康龙头 → allow score≥75；孤立题材 → reduce，reasons 含“孤立”或“扩散不足”）。
- [ ] Step 2: 评分权重（板块 rank/strength 35%、龙头健康 30%、同板块扩散 20%、换手确认 15%）；decision allow/reduce/block/research_only。
- [ ] Step 3: `/api/market/sector-relative-strength` 增 `leader_status`/`leader_break_reason`/`same_sector_limit_up_count`/`diffusion_score`/`sector_leader_gate_decision`。
- [ ] Step 4: 接入低吸生产分：CORE 最多 +12、AUX 最多 +6、**RESEARCH 无生产先验**。
- [ ] Step 5: `PYTHONPATH=backend ... pytest backend/tests/test_decision_context_sector_leader_gate.py backend/tests/test_market_routes.py -q`

---

## Task B2: Real Portfolio Executor For max5/max10（强制复用既有口径）

**Purpose:** 把“每日信号收益”变成可执行组合收益。**复用既有 `portfolio_backtest_metrics`，禁止重写规则。**

**Files:**
- Create: `backend/app/services/decision_context/portfolio_executor.py`（薄封装/参数适配，调用既有实现）
- Modify: `backend/scripts/low_buy_market_backtest_reporting.py`（如需将 `portfolio_backtest_metrics` 抽为可复用纯函数，保持签名与数值不变）
- Modify: `backend/app/services/paper/performance.py`
- Modify: `backend/app/services/analytics/report_queries.py`, `backend/scripts/run_duckdb_strategy_report.py`
- Test: `backend/tests/test_decision_context_portfolio_executor.py`

- [ ] **Step 1: Write failing tests**（max_positions=5 + 同票冷却：6 个同日信号填 5 跳 1，次日同票冷却跳 1）
- [ ] **Step 2: Reuse, do not reimplement** —— `portfolio_executor.run_portfolio_execution(...)` 必须委托既有 `portfolio_backtest_metrics`（max5/max10、`duplicate_symbol_open`、同策略≤2、同板块≤2、弱市≤40%、退潮不开仓、资金占用、费用滑点、T+1、涨跌停可成交性）。新增 `same_symbol_cooldown_days` 参数若既有未含则在既有函数内扩展，保持单一实现。
- [ ] **Step 3: 一致性测试**（新增 `test` 断言：执行器输出与 24M 报告 `portfolio_backtests.max_5/max_10` 数值在容差内一致）。
- [ ] **Step 4: Wire 24M report + paper preview**（报告显示“每日信号等权复利收益 / 真实组合 max5 / 真实组合 max10 / 跳过原因分布 / 费用滑点冲击涨跌停停牌 T+1 假设”；Paper 页“组合执行预览”解释被跳过信号原因）。
- [ ] **Step 5: Run tests**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_portfolio_executor.py \
  backend/tests/test_strategy_24m_duckdb_report.py \
  backend/tests/test_paper_performance_archive.py -q
```

---

## Task B3: Research-To-Production Promotion Engine（仅建议 · 不自动生效）

**Purpose:** RESEARCH 策略通过证据产出**晋级建议**，绝不绕过 `strategy_policy` 拿生产分，绝不自动改层。

**Files:**
- Create: `backend/app/services/decision_context/promotion_engine.py`
- Modify: `backend/app/services/low_buy/strategy_auto_governance.py`, `backend/app/services/low_buy/strategy_governance.py`
- Modify: `backend/app/api/routes/strategy_meta.py`
- **不修改** `backend/app/services/low_buy/strategy_policy.py`（边界 2）
- Test: `backend/tests/test_decision_context_promotion_engine.py`

- [ ] **Step 1: Write failing tests**（用**真实键** `n_pattern_long_wash`：无 OOS → `recommendation=="stay_research"`，reasons 含 "OOS"）
- [ ] **Step 2: Implement promotion criteria**（AUX：sample≥200、PF≥1.20、avg>0、dd≥-12、季度稳定≥0.60、WF pass、OOS pass；CORE：sample≥500、PF≥1.35、avg≥0.45、dd≥-10、max5&max10 均正、季度稳定≥0.70、WF&OOS pass、最近两季不同时为负）
- [ ] **Step 3: 生效路径写死（边界 2/边界 3）** —— 晋级引擎只写 `strategy_promotion_reviews` 并产出建议；**`PROMOTION_ENGINE_AUTO_APPLY_ENABLED` 永久 false**，不自动创建/生效 `StrategyTierOverride`。层级变更的唯一生效路径 = 人工修改 `strategy_policy.py` 常量并通过守卫测试 `test_core_aux_strategies_match_latest_24m_report`（若该守卫不存在则在本任务补建）。
  > 说明：当前 `priority_scoring.py:193` 用静态 `get_tier_weight`，不读 `StrategyTierResolver`；本任务不打通该链路，避免动热路径。
- [ ] **Step 4: API 响应**（`current_tier`/`recommended_tier`/`recommendation`/`evidence`/`blocking_reasons`/`can_apply_override=false`）
- [ ] **Step 5: Run tests**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_promotion_engine.py \
  backend/tests/test_low_buy_strategy_replacement.py \
  backend/tests/test_low_buy_production_scoring.py -q
```

---

## Task C0: 数据可用性前置验证门（Batch C 必须先过）

**Purpose:** 分钟入场与事件风险高度依赖数据；无数据不得造假分或硬阻断生产。

- [ ] **Step 1: 分钟/Tick 覆盖率实测** —— 统计近 N 个交易日 `MinuteBarSnapshot`/`TickTradeSnapshot` 对生产标的的覆盖率，写入 runbook。覆盖率不足阈值 → Task C2 默认 `INTRADAY_ENTRY_PRODUCTION_BOOST_ENABLED=false`，只输出 `no_data`/研究态。
- [ ] **Step 2: 公告/事件数据源确认** —— 确认是否存在可用免费公告/减持/监管事件源。**无源 → Task C3 `EVENT_RISK_PRODUCTION_BLOCK_ENABLED=false`，事件风险只做摘要展示与 `data_quality=missing`，不进生产阻断**（边界 3）。
- [ ] **Step 3: 结论写入** `docs/high-roi-platform-expansion-runbook-2026-05-30.md`，作为 C2/C3 是否进生产的判据。

---

## Task C1: Signal Attribution And Self-Learning Review

**Files:** Create `backend/app/services/decision_context/signal_attribution.py`；Modify `backend/app/services/low_buy/priority_snapshot.py`, `backend/app/services/strategy_tracking_snapshot.py`, `backend/app/workers/runtime_worker.py`；Test `backend/tests/test_decision_context_signal_attribution.py`

- [ ] Step 1: 失败测试（`compute_signal_outcome` 多周期收益：entry 10.0、3 日 close 9.8 → return_pct=-2.0；max_gain/max_drawdown 按区间高低）。
- [ ] Step 2: 快照必含字段（strategy key/tier、`participates_in_priority_board`、signal state/score、production_score 或显式 null、5 个 gate、final_decision、entry/invalidation、data_quality、source versions）。
- [ ] Step 3: RuntimeTask `signal_attribution_refresh`（payload `{as_of_date,horizons:[1,3,5,10],limit}`），在 `runtime_worker._execute_task` 注册；声明**不**纳入 research 门控（属生产可追溯）。
- [ ] Step 4: 策略追踪详情抽屉展示（为何入/被阻、信号后收益、各 gate 正负贡献、相似历史样本数）。
- [ ] Step 5: `PYTHONPATH=backend ... pytest backend/tests/test_decision_context_signal_attribution.py backend/tests/test_strategy_tracking.py -q`

---

## Task C2: Intraday Entry Optimizer（数据不足显式降级）

**Files:** Create `backend/app/services/decision_context/intraday_entry.py`；Modify `backend/app/services/low_buy/intraday_confirmation.py`, `backend/app/services/low_buy/signal_entry.py`, `backend/app/api/routes/intraday.py`；Test `backend/tests/test_decision_context_intraday_entry.py`

- [ ] Step 1: 失败测试（高开追高 → `wait`，reasons 含“追高”或“回踩”）。
- [ ] Step 2: 决策 `buy_now`/`wait`/`avoid`/`no_data`（分钟数据缺失 → `no_data`，**不得加生产分**，受 `INTRADAY_ENTRY_PRODUCTION_BOOST_ENABLED` 控制，默认 false）。
- [ ] Step 3: API 输出 `intraday_entry_decision`/`entry_zone_low`/`entry_zone_high`/`vwap_distance_pct`/`support_distance_pct`/`confirmation_text`。
- [ ] Step 4: 前端 badge（可接近/等回踩/先观察/数据缺失）。
- [ ] Step 5: `PYTHONPATH=backend ... pytest backend/tests/test_decision_context_intraday_entry.py backend/tests/test_low_buy_intraday_confirmation.py -q`

---

## Task C3: Announcement And Event Risk Summary（有源才阻断）

**Files:** Create `backend/app/services/decision_context/event_risk.py`, `backend/app/services/market/event_cache.py`（新建）；Modify `backend/app/services/ai_decision_support.py`（或 `analysis_service.py`，以实际 LLM 入口为准）, `backend/app/api/routes/ai.py`；Test `backend/tests/test_decision_context_event_risk.py`

- [ ] Step 1: 失败测试（高风险减持 → block，reasons 含“减持”）。
- [ ] Step 2: 事件分级（高：退市/监管处罚/重大诉讼/业绩暴雷/大额减持/质押平仓/异常监控；中：问询函/业绩预告不确定/小额减持/重组不确定；低：正常经营/分红）。
- [ ] Step 3: LLM 仅输出 摘要/风险类型/严重度/影响周期/证据引用 id；**拒绝含买卖建议的输出**（边界 6）。
- [ ] Step 4: 接入：高风险阻断生产候选、中风险降分并告警；**仅当 Task C0 确认数据源且 `EVENT_RISK_PRODUCTION_BLOCK_ENABLED=true` 时生效**，否则只摘要、`data_quality=missing`。
- [ ] Step 5: `PYTHONPATH=backend ... pytest backend/tests/test_decision_context_event_risk.py backend/tests/test_ai_decision_support.py -q`

---

## Frontend（按批次随对应后端任务交付，统一约束）

**Files:** Create `frontend/src/api/decisionContext.ts` 与各面板；Modify `frontend/src/api/client.ts`, `MonitorPage.tsx`, `PaperTradingPage.tsx`, `StrategyTrackingPage.tsx`, `PlaybookPage.tsx`；Test `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`, `frontend/src/features/paper/PaperTradingPerformance.test.tsx`

- 约束（边界 6）：用 Zustand store（**禁 useState/useReducer**，`check-refactor-guard.mjs` 会拦截）；表格走 `DataTable`，>20 项卡片走 `VirtualCardList`；新增面板默认懒加载/折叠，不进首屏关键路径。
- Batch A 前端：Monitor 市场总闸面板、风险 badges。
- Batch B 前端：Monitor 板块/龙头面板、Paper 组合执行预览（跳过原因表走 `DataTable`）、策略追踪晋级审查面板。
- Batch C 前端：策略追踪归因、分钟入场 badge、事件风险面板、决策上下文抽屉。
- 校验：`cd frontend && npm run api:check && npm run lint && npm run build && npm test -- --run && npm run analyze`（analyze 输出无新的首屏超大 chunk）。

---

## Runtime Tasks And Report Integration

**Files:** Modify `backend/app/workers/runtime_worker.py`, `backend/app/services/tasks/analytics_handlers.py`, `backend/app/services/analytics/report_queries.py`, `backend/scripts/run_duckdb_strategy_report.py`, `docs/reports/strategy_24m_duckdb_report.md`；Test `backend/tests/test_analytics_worker.py`, `backend/tests/test_strategy_24m_duckdb_report.py`

- [ ] **Step 1: Add task types**
  - runtime worker（`_execute_task` 注册，逐个声明是否纳入 research/ml/factor 门控；归因/状态刷新属生产可追溯，不门控）：`market_state_gate_refresh`、`sector_leader_snapshot_refresh`、`hard_risk_context_refresh`、`signal_attribution_refresh`、`intraday_entry_snapshot_refresh`、`event_risk_refresh`、`strategy_promotion_review`、`paper_portfolio_execution_preview`。
  - analytics（`analytics_handlers.register_analytics_handlers` 注册）：`decision_context_24m_report`、`portfolio_execution_24m_report`。
- [ ] **Step 2: Add task tests**（断言：Web 默认不跑刷新 loop；runtime worker 消费短任务；analytics worker 消费报告任务；数据质量失败返回 `blocked_by_data` 而非静默成功）。
- [ ] **Step 3: Extend 24M report sections**（数据质量/市场门控/板块龙头/避坑命中/每日信号等权复利收益/真实组合 max5/max10/信号归因/分钟入场质量/事件风险/晋级建议/费用滑点冲击涨跌停停牌 T+1 同票冷却说明）。
- [ ] **Step 4: Run report locally + hard checks**
```bash
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py --output docs/reports/strategy_24m_duckdb_report.md
# 硬校验：无裸“总收益”表头（必须为空）
rg -n "^\| *总收益 *\|" docs/reports/strategy_24m_duckdb_report.md && echo "FAIL: bare 总收益 header" || echo "OK"
# 必含标签
rg -n "每日信号等权复利收益|真实组合 max5|真实组合 max10|策略晋级|blocked_by_data" docs/reports/strategy_24m_duckdb_report.md
```

---

## Runbook, Deployment, And Online Acceptance

**Files:** Create `docs/high-roi-platform-expansion-runbook-2026-05-30.md`；Modify `PRODUCTION_RUNBOOK.md`, `docs/README.md`, `docker-compose.mysql.yml`

- [ ] Step 1: Runbook（任务/worker 归属、数据依赖、数据质量阻断、如何 enqueue 每个 RuntimeTask、如何验证完成、如何重生成 24M 报告、如何查看被阻断信号、如何用 feature flag 回退、Task C0 数据可用性结论）。
- [ ] Step 2: Feature flags 落 `config.py`（见“Feature Flags”），默认值与批次一致；`EVENT_RISK_PRODUCTION_BLOCK_ENABLED` 与 `INTRADAY_ENTRY_PRODUCTION_BOOST_ENABLED` 默认 false。
- [ ] Step 3: Docker/worker 验证
```bash
docker compose -f docker-compose.mysql.yml build app runtime-worker analytics-worker
docker compose -f docker-compose.mysql.yml up -d app runtime-worker analytics-worker
docker compose -f docker-compose.mysql.yml exec analytics-worker python -c "import duckdb, pyarrow; print(duckdb.__version__, pyarrow.__version__)"
curl -fsS http://127.0.0.1:18090/readyz
```
- [ ] Step 4: 线上 RuntimeTask 验收（admin token）
```bash
curl -fsS -X POST "$BASE_URL/api/runtime-tasks" -H "X-Admin-Token: $ADMIN_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"task_type":"decision_context_24m_report","payload":{"output":"backend/data/analytics/reports/decision_context_24m_report.md"},"priority":20,"idempotency_key":"decision-context-24m-report"}'
```
验证：task `succeeded`；报告 artifact 存在；质量 `ok` 或显式 `blocked_by_data`；priority board 含决策上下文字段；N 字无生产分、不进 priority board。

---

## Acceptance Matrix

| Direction | Production Behavior | Research Behavior | Required Tests | Required UI |
| --- | --- | --- | --- | --- |
| 市场状态总闸 | 弱势/退潮阻断或降权；市场级缺数据降级不清空 | 可记录但标记研究 | `test_decision_context_market_gate.py` | Monitor 总闸 |
| 板块/龙头确认 | 板块扩散和龙头健康才加权 | 缺数据标记研究 | `test_decision_context_sector_leader_gate.py` | Monitor 板块/龙头 |
| 避坑过滤器 | ST/停牌/无效 OHLC/高风险事件阻断 | 可入研究但不可生产 | `test_decision_context_hard_risk_filter.py` | 风险 badges |
| 真实组合执行器 | max5/max10 可执行收益（复用既有口径） | 可模拟更多参数 | `test_decision_context_portfolio_executor.py` | Paper 执行预览 |
| 信号归因 | 生产信号必须可追溯 | 研究信号同样标注 | `test_decision_context_signal_attribution.py` | Strategy drawer |
| 分钟入场优化 | 只加减分或等待，不直接下单；缺数据 no_data 不加分 | 缺分钟数据显式降级 | `test_decision_context_intraday_entry.py` | 入场状态 badge |
| 公告/事件风险 | 有源且开关开启才阻断；否则只摘要 | 摘要可用于复盘 | `test_decision_context_event_risk.py` | 事件风险面板 |
| 研究晋级系统 | 满足证据才建议晋级；不自动生效、不绕过 policy | 不绕过 policy | `test_decision_context_promotion_engine.py` | 晋级审查面板 |

## Backtest And Report Requirements

每个策略建议与晋级复核必须包含：sample count、profit factor、average trade、max drawdown、max5、max10、quarterly stability、walk-forward、OOS、fee/slippage/impact 假设、涨跌停处理、停牌处理、T+1 处理、同票冷却、data quality。

任一关键输入缺失：生产路径返回 `blocked` 或 `research_only`；analytics 报告返回 `blocked_by_data`；UI 显示 blocker，不显示假分。

## Verification Commands（按批次，已校正测试名）

**Batch A:**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_schema.py \
  backend/tests/test_decision_context_hard_risk_filter.py \
  backend/tests/test_decision_context_market_gate.py \
  backend/tests/test_low_buy_production_scoring.py \
  backend/tests/test_paper_routes.py \
  backend/tests/test_strategy_24m_duckdb_report.py -q
```

**Batch B:**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_sector_leader_gate.py \
  backend/tests/test_decision_context_portfolio_executor.py \
  backend/tests/test_decision_context_promotion_engine.py \
  backend/tests/test_market_routes.py \
  backend/tests/test_paper_performance_archive.py \
  backend/tests/test_low_buy_strategy_replacement.py -q
```

**Batch C:**
```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_context_signal_attribution.py \
  backend/tests/test_decision_context_intraday_entry.py \
  backend/tests/test_decision_context_event_risk.py \
  backend/tests/test_strategy_tracking.py \
  backend/tests/test_low_buy_intraday_confirmation.py \
  backend/tests/test_ai_decision_support.py \
  backend/tests/test_analytics_worker.py -q
```

**Frontend（每批次结尾）:**
```bash
cd frontend && npm run api:check && npm run lint && npm run build && npm test -- --run && npm run analyze
```

**全量回归（合入前）:** `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q`（必须全绿，含既有 `test_n_pattern_observe_confirmed.py`）。

## Rollback Plan

回退不删数据表，只用 flag 关闭生产副作用：

```env
DECISION_CONTEXT_ENABLED=false
MARKET_GATE_PRODUCTION_ENABLED=false
SECTOR_LEADER_GATE_PRODUCTION_ENABLED=false
HARD_RISK_FILTER_PRODUCTION_ENABLED=false
EVENT_RISK_PRODUCTION_BLOCK_ENABLED=false
PROMOTION_ENGINE_AUTO_APPLY_ENABLED=false
```

预期回退行为：priority board 回到既有评分路径；已存决策上下文仍可读用于审计；RuntimeTask 刷新可停止而不影响 Web 请求；Paper 组合执行预览隐藏但旧纸面交易仍可用。每个批次可独立回退（A/B/C 互不依赖生产生效）。

## Definition Of Done

- 8 个方向各有代码、测试、UI、报告、runbook、线上验收证据。
- 生产分仍遵守 `strategy_policy` 与 `participates_in_priority_board`；N 字与 RESEARCH 不拿生产先验/前排生产分。
- 数据质量阻断显式；缺数据不出假分。
- 组合 max5/max10 单一实现，报告与 Paper 预览同口径同数值。
- 24M 报告含每日信号等权复利收益与真实 max5/max10；无裸“总收益”表头。
- RuntimeTask 由 runtime/analytics worker 消费验证；Web 默认无后台 loop。
- 晋级引擎不自动改 `strategy_policy`、不自动生效 override。
- 前端 `api:check`、lint、build、Vitest、analyze 通过；零 `useState/useReducer`。
- 不引入实盘下单；LLM 不输出买卖建议。
- 合入前 `pytest backend/tests` 全绿。
```
