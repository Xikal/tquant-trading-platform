# 集合竞价辅助能力开发执行计划

状态：待实施
日期：2026-06-11
权威需求：`docs/call-auction-assist-verified-requirements-2026-06-11.md`
来源草案：`docs/call-auction-assist-requirements-2026-06-10.md`
适用范围：A 股集合竞价信息用于已持仓票晨间风险提示、策略推荐票次日入场确认门、竞价数据前向采集研究

## 1. 执行结论

本能力可以开发，但必须按 G0 -> G1 -> G2 -> G3 -> G4 串行推进：

1. G0 先做 provider spike 和契约准入，确认 9:25 结果及 9:20-9:25 过程字段是否真实可得。
2. G1 先用历史日线 `open/pre_close` 做 gap 确认门回测，产出是否采纳结论。
3. G2 在 provider spike 通过后再做竞价快照落库、RuntimeTask 采集和持仓/自选 hint 生成。
4. G3 只把展示先落在现有 `/next/monitor`，`/next/paper` 未恢复前不作为验收目标。
5. G4 等前向样本至少 4 周后再研究 9:20-9:25 过程信号，不提前进入生产确认门。

默认不部署、不切流、不打开生产 feature flag。任一批次未达验收门，后续批次暂停并输出报告。

## 2. 硬边界

开发开始前必须执行：

```bash
git status --short
```

处理规则：

- 保护当前已有 staged、modified、untracked 内容；不得 `git reset --hard`、`git checkout --`、删除或覆盖无关文件。
- 新增功能默认按 `docs/engineering-conventions.md` 和 `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md` 执行。
- 不直接拆微服务；Web 只做轻量查询、任务提交和状态查询，采集与回测走 Worker/脚本。
- 不在 Web 请求线程实时拉竞价 provider。
- 不修改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变 `production_score`、`priority_score`、priority board 排序语义。
- 不把竞价提示写入模拟盘订单，不触发自动交易。
- 不输出“建议买入、建议卖出、必涨、抢筹必胜、低吸”等越界文案。
- 9:15-9:20 可撤单段不得作为确认门决策输入。
- 历史 9:20-9:25 过程数据不可伪造；没有历史数据时只做前向采集。
- `/next/paper` 当前重定向到 `/next/monitor`，未恢复真实页面前不作为 Phase 2 必验收项。

## 3. 角色编排

| 角色 | 本计划职责 | 必交输出 |
|---|---|---|
| `trading-quant-lead` | 阈值版本、回测口径、采纳门、生产隔离守卫 | G1 回测报告、采纳/不采纳结论 |
| `stock-analysis-specialist` | 市场状态过滤、触发/失效条件、支撑/压力解释口径 | hint 规则清单、文案边界 |
| `product-strategist` | 研究模式/生产模式差异、页面展示优先级 | 四态产品验收清单 |
| `ui-designer` | `/next/monitor` 高密度提示呈现、状态 pill、tooltip | UI 状态清单、文案守卫结果 |
| `fullstack-builder` | 后端服务、数据表、任务、API、前端接入 | 代码、OpenAPI、generated types |
| `qa-tester` | 单测、契约测试、前端测试、生产隔离测试 | 验证命令和结果 |
| `devops-operator` | RuntimeTask、provider 熔断、回滚、运行手册 | 任务观测与降级说明 |

## 4. 批次总览

| 批次 | 目标 | 主要交付 | 进入下一批条件 |
|---|---|---|---|
| G0 | provider spike 与准入 | spike 脚本、Markdown/JSON 报告、数据源结论 | 明确 `provider_ok`、`result_only` 或 `provider_failed` |
| G1 | 历史 gap 确认门回测 | auction confirmation 纯规则、回测脚本、报告、生产隔离测试 | 报告明确采纳/不采纳；测试通过；生产排序 hash 不变 |
| G2 | 竞价采集与持仓 hint | 表、repo、provider、collector、RuntimeTask、hint 服务 | 交易日可采集；缺数据可降级；任务可观测 |
| G3 | API 与 `/next/monitor` 展示 | route、OpenAPI、前端类型、UI 四态展示 | API/前端测试通过；越界文案为 0 |
| G4 | 前向过程信号研究 | 4 周以上样本报告、过程指标评估 | 仅输出研究结论；若升级规则另起需求 |

## 5. G0：Provider Spike 与准入

### 5.1 目标

确认免费数据源是否能稳定提供竞价结果或过程快照。G0 不改变产品行为，不启用任何 feature flag。

### 5.2 建议新增文件

- `backend/scripts/call_auction_provider_spike.py`
- `backend/tests/test_call_auction_provider_spike.py`
- `docs/reports/call-auction-provider-spike-YYYY-MM-DD.md`
- `backend/data/reports/call-auction-provider-spike-YYYY-MM-DD.json`

### 5.3 执行步骤

1. 读取 `build_quote_cache_demand_symbols(db)` 形成候选池，再裁剪到 10-30 只。
2. 样本覆盖沪市、深市、ETF、停牌或异常样本。
3. 在真实交易日 9:19:30-9:25:30 运行 spike。
4. 优先验证 `akshare stock_zh_a_hist_pre_min_em` 或东财盘前分时字段。
5. 记录字段可得性、延迟、失败率、限频、时间戳、source、data_quality。
6. 将结论写成三态之一：
   - `provider_ok`：9:25 结果和过程字段可用，允许 G2/G4。
   - `result_only`：只有 9:25 结果稳定，G2 只做 result 采集，G4 暂停。
   - `provider_failed`：数据源不可用，G2/G3 只能返回 `no_data`，先只执行 G1。

### 5.4 验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/call_auction_provider_spike.py \
  --sample-size 30 \
  --output-md docs/reports/call-auction-provider-spike-$(date +%F).md \
  --output-json backend/data/reports/call-auction-provider-spike-$(date +%F).json
```

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_call_auction_provider_spike.py -q
```

### 5.5 停止条件

- 非交易日或不在 9:19:30-9:25:30：只允许生成 blocked 报告，不伪造结果。
- provider 失败率过高：写 `provider_failed`，后续采集批次暂停。

## 6. G1：历史 Gap 确认门回测

### 6.1 目标

在不依赖新 provider 的情况下，用 `DailyBarSnapshot.open_price/pre_close` 验证 gap 类规则是否能改善 `first_board`、`volume_shrink` 的净胜率、PF、回撤和 OOS 表现。

### 6.2 建议新增/修改文件

- `backend/app/services/low_buy/auction_confirmation.py`
- `backend/app/models/schema_defs/auction.py`
- `backend/app/models/schema_defs/screener_parts/plans.py`
- `backend/scripts/call_auction_gap_confirmation_backtest.py`
- `backend/tests/test_low_buy_auction_confirmation.py`
- `backend/tests/test_auction_gap_backtest.py`
- `backend/tests/test_auction_production_isolation.py`
- `docs/reports/call-auction-gap-confirmation-backtest-YYYY-MM-DD.md`
- `backend/data/reports/call-auction-gap-confirmation-backtest-YYYY-MM-DD.json`

### 6.3 规则实现

新增纯函数模块，先不接生产排序：

- `AuctionContext`
- `AuctionConfirmationResult`
- `AuctionThresholds`
- `build_auction_confirmation(strategy_key, auction_context, thresholds)`
- `auction_confirmation_passes(...)`
- `auction_confirmation_hint(...)`

状态枚举：

- `confirmed`
- `rejected`
- `not_evaluated`
- `no_data`

策略集合：

```python
AUCTION_CONFIRMATION_STRATEGIES = {"first_board", "volume_shrink"}
```

阈值版本：

- 初始版本使用 `auction-gap-v1`。
- 阈值必须进入报告和 JSON，禁止散落硬编码。
- 阈值未通过采纳门时保持研究态，不启用生产 flag。

### 6.4 回测口径

必须包含：

- 24M 全样本。
- walk-forward。
- OOS 或 quarter proxy。
- 成本、滑点、涨跌停、停牌、新股无昨收处理。
- 胜率、PF、净期望、最大回撤、样本留存、成交留存、最长无票。
- 基线 vs 各阈值变体。
- 每个策略的 `adopted` 或 `not_adopted` 结论。

不得包含：

- 历史 9:20-9:25 过程数据假设。
- 未声明成交假设。
- 使用 `auction_state` 影响 production score 或 priority board 排序。

### 6.5 采纳门

任一策略变体必须同时满足：

- PF 不低于基线。
- 净期望不低于基线。
- 胜率提升或回撤显著改善。
- 样本留存 >= 60%。
- OOS 不劣化。
- walk-forward 通过率不低于基线。
- 关闭/开启竞价 flag 后 priority board 排序字段 hash 一致。

未满足时：

- `auction_confirmation_enabled=false`
- 报告写 `not_adopted`
- 前端只能展示 `not_evaluated` 或研究态说明。

### 6.6 验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/call_auction_gap_confirmation_backtest.py \
  --strategies first_board,volume_shrink \
  --months 24 \
  --output-md docs/reports/call-auction-gap-confirmation-backtest-$(date +%F).md \
  --output-json backend/data/reports/call-auction-gap-confirmation-backtest-$(date +%F).json
```

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_low_buy_auction_confirmation.py \
  backend/tests/test_auction_gap_backtest.py \
  backend/tests/test_auction_production_isolation.py \
  -q
```

## 7. G2：竞价采集与持仓 Hint

### 7.1 进入条件

G0 结论为 `provider_ok` 或 `result_only`。如果 G0 为 `provider_failed`，G2 只允许实现 `no_data` 降级壳，不做真实采集链路。

### 7.2 建议新增/修改文件

- `backend/app/models/auction_entities.py`
- `backend/app/models/entities.py`
- `backend/alembic/versions/YYYYMMDD_0001_call_auction_snapshots.py`
- `backend/app/repositories/auction.py`
- `backend/app/services/auction/target_symbols.py`
- `backend/app/services/auction/collector.py`
- `backend/app/services/auction/position_hints.py`
- `backend/app/services/auction/quality.py`
- `backend/app/services/market/providers/auction_provider.py`
- `backend/app/services/tasks/registry.py`
- `backend/app/services/tasks/handlers.py` 或现有 handler 注册模块
- `backend/app/workers/runtime_worker.py` 如任务分发需要更新
- `backend/app/services/shared/feature_flags.py`
- `backend/tests/test_auction_snapshot_collection.py`
- `backend/tests/test_auction_position_hints.py`
- `backend/tests/test_auction_provider_contract.py`
- `backend/tests/test_runtime_task_registry_governance.py`

### 7.3 数据表

新增三张表：

- `auction_snapshots`
- `auction_confirmations`
- `auction_position_hints`

关键约束：

- `auction_snapshots` unique: `(symbol, trade_date, phase, captured_at, source)`
- `auction_confirmations` unique: `(symbol, strategy_key, signal_trade_date, entry_trade_date, thresholds_version)`
- `auction_position_hints` unique: `(scope, user_id, account_id, symbol, trade_date, hint_code)`

### 7.4 Feature Flags

新增默认关闭：

- `auction_confirmation_enabled`
- `auction_position_hints_enabled`
- `auction_snapshot_collection_enabled`
- `auction_process_research_enabled`

关闭行为：

- 推荐票返回 `not_evaluated` 或不附加字段。
- 持仓 hint 隐藏或返回 `auction_not_evaluated`。
- 采集任务不入队。
- priority board 排序 hash 不变。

### 7.5 RuntimeTask

新增任务类型：

- `auction_snapshot_collect`
- `auction_snapshot_result_collect`
- `auction_position_hint_refresh`

幂等键：

- `auction_snapshot_collect:{trade_date}:{hhmm}:{symbol_batch_hash}`
- `auction_snapshot_result_collect:{trade_date}:{symbol_batch_hash}`
- `auction_position_hint_refresh:{trade_date}:{scope}:{user_or_account}`

任务规则：

- 只在交易日窗口入队。
- 9:25 前不生成确认门结果。
- 9:25:30 后只做 result 补采，不继续过程采集。
- provider 熔断或失败时写 `provider_failed`，不重试到拖垮任务队列。
- 采集目标来自 `build_quote_cache_demand_symbols(db)`，再按 paper 持仓、自选、priority board 候选排序裁剪，默认不超过 300。

### 7.6 Hint 规则

`auction_break_risk`：

- `auction_open_price < support_zone_low` 或 `auction_open_price < configured_stop_line`
- level: `warn`

`auction_gap_strength`：

- `gap_pct >= threshold` 且 `auction_volume_ratio >= threshold`
- level: `info`

`auction_gap_down`：

- 低开达到阈值但未破关键位
- level: `info`

`auction_no_data`：

- provider 失败、停牌、新股无昨收、目标不在采集范围

### 7.7 验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_auction_snapshot_collection.py \
  backend/tests/test_auction_position_hints.py \
  backend/tests/test_auction_provider_contract.py \
  backend/tests/test_runtime_task_registry_governance.py \
  -q
```

如新增 Alembic migration：

```bash
PYTHONPATH=backend:. backend/.venv/bin/alembic upgrade head
```

## 8. G3：API 与 `/next/monitor` 展示

### 8.1 目标

把竞价确认和持仓 hint 通过后端契约暴露给前端，并在 `/next/monitor` 展示四态。`/next/paper` 未恢复前不验收。

### 8.2 建议新增/修改文件

后端：

- `backend/app/api/routes/auction.py`
- `backend/app/api/router.py`
- `backend/app/models/schema_defs/auction.py`
- `backend/app/models/schema_defs/__init__.py`
- `backend/tests/test_auction_routes.py`
- `backend/tests/test_contract_first_openapi.py` 或新增 auction 契约测试

契约/前端：

- `docs/contracts/openapi.json`
- `docs/contracts/openapi.hash`
- `frontend-next/src/generated/api-types.ts`
- `frontend-next/src/shared/api/operations.ts`
- `frontend-next/src/shared/api/types.ts`
- `frontend-next/src/shared/api/client.ts`
- `frontend-next/src/shared/api/queryKeys.ts`
- `frontend-next/src/features/monitor-action/AuctionHintPill.tsx`
- `frontend-next/src/features/monitor-action/auctionHints.ts`
- `frontend-next/src/features/monitor-action/MonitorActionPage.tsx`
- `frontend-next/src/features/monitor-action/monitor-action.css`
- `frontend-next/src/features/monitor-action/auctionHints.test.ts`
- `frontend-next/src/features/monitor-action/MonitorActionPage.test.tsx`

### 8.3 API

新增 route：

- `GET /api/auction/confirmations`
- `GET /api/auction/position-hints`

契约要求：

- 所有 response schema 在 `backend/app/models/schema_defs/auction.py` 定义。
- OpenAPI 为事实源，前端只使用 generated types。
- `data_quality`、`as_of`、`source` 或 `thresholds_version` 必须随状态返回。
- `no_data` 不阻断推荐票。

### 8.4 前端展示

`/next/monitor` 需展示：

- 推荐票列表：`auction_state` pill、原因 tooltip、`as_of`。
- 自选区：`auction_position_hint`。
- 持仓区：如 monitor snapshot 有持仓，展示同一 hint。

四态：

- `confirmed`：信息态。
- `rejected`：警示态，但不隐藏原信号。
- `not_evaluated`：灰态或不展示。
- `no_data`：灰态，注明竞价数据缺失。

文案守卫：

- 只允许“风险提示、观察、开盘后评估、数据缺失、仅供复盘/研究”语义。
- 禁止“买入、卖出、必涨、低吸、抢筹、自动执行”等越界词。

### 8.5 验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/export_openapi_schema.py
```

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_auction_routes.py \
  backend/tests/test_contract_first_openapi.py \
  -q
```

```bash
cd frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

前端完成后需要截图或浏览器 smoke，至少覆盖：

- `confirmed`
- `rejected`
- `not_evaluated`
- `no_data`

## 9. G4：前向过程信号研究

### 9.1 进入条件

- G2 已稳定采集。
- 前向样本不少于 4 周交易日。
- provider 报告确认 9:20-9:25 过程字段可用。

### 9.2 建议新增文件

- `backend/scripts/call_auction_process_research.py`
- `docs/reports/call-auction-process-research-YYYY-MM-DD.md`
- `backend/data/reports/call-auction-process-research-YYYY-MM-DD.json`

### 9.3 指标

- 虚拟撮合价斜率。
- 匹配量变化。
- 未匹配量变化。
- 最后一分钟突变。
- 9:25 结果与开盘后 5/15/30 分钟表现。
- 次日收益、回撤、成交留存。

### 9.4 验收

G4 只输出研究结论，不进入生产确认门。若研究结论建议升级规则，必须另起需求并重新走 G1 的采纳门。

## 10. 最终验收清单

后端：

- 竞价四态逻辑测试通过。
- 生产隔离测试通过。
- RuntimeTask registry 治理测试通过。
- provider circuit、timeout、data_quality 覆盖。
- 缺数据返回 `no_data` 或 `not_evaluated`，不静默成功。

前端：

- `/next/monitor` 四态展示正确。
- `rejected` 不隐藏原信号。
- `no_data` 不伪造成确认。
- 越界文案为 0。
- `/next/paper` 未恢复时不作为验收失败。

报告：

- G0 provider spike 报告。
- G1 24M gap 回测报告。
- G2 采集质量报告或任务 artifact。
- G4 前向研究报告。

生产边界：

- 所有新增 flag 默认 false。
- 未经用户明确授权不部署、不推送、不打开线上开关。
- 关闭 flag 后 priority board 排序字段 hash 不变。

## 11. 推荐执行提示词

```text
你在 /Users/j/Documents/gupiao 工作。请按 docs/call-auction-assist-execution-plan-2026-06-11.md 执行集合竞价辅助能力开发，权威需求是 docs/call-auction-assist-verified-requirements-2026-06-11.md，同时遵循 docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md 和 AGENTS.md。

开始前必须执行 git status --short，保护已有 staged/modified/untracked 内容，不得 reset、checkout、clean、删除或覆盖无关改动。默认不部署、不推送、不打开生产 feature flag。

硬边界：不改 backend/app/services/low_buy/strategy_policy.py；不改变 production_score、priority_score、priority board 排序语义；不在 Web 请求线程拉竞价 provider；不自动下单、不写模拟盘订单；UI 不出现“建议买入/卖出/必涨/低吸/抢筹/自动执行”等文案；/next/paper 当前重定向到 /next/monitor，未恢复前不作为验收项。

按 G0->G1->G2->G3->G4 串行：
G0 先做 provider spike：新增 backend/scripts/call_auction_provider_spike.py，真实交易日 9:19:30-9:25:30 抽样 10-30 只，输出 docs/reports/call-auction-provider-spike-YYYY-MM-DD.md 和 backend/data/reports/call-auction-provider-spike-YYYY-MM-DD.json，结论只能是 provider_ok/result_only/provider_failed。
G1 用 DailyBarSnapshot.open_price/pre_close 做历史 gap 确认门回测：新增 backend/app/services/low_buy/auction_confirmation.py、backend/scripts/call_auction_gap_confirmation_backtest.py 和对应测试；覆盖 first_board、volume_shrink 的 24M、walk-forward、OOS、成本滑点、样本留存、PF、净期望、最大回撤；输出 adopted/not_adopted。不得用历史 9:20-9:25 过程数据。
G2 仅在 G0 可用时做采集：新增 auction_snapshots、auction_confirmations、auction_position_hints 表，ProviderResult 风格 provider、collector、position_hints、RuntimeTask：auction_snapshot_collect、auction_snapshot_result_collect、auction_position_hint_refresh。四个 flag 默认 false：auction_confirmation_enabled、auction_position_hints_enabled、auction_snapshot_collection_enabled、auction_process_research_enabled。
G3 新增 GET /api/auction/confirmations 和 GET /api/auction/position-hints，导出 OpenAPI 并生成 frontend-next 类型，只在 /next/monitor 展示 confirmed/rejected/not_evaluated/no_data 四态；rejected 不隐藏原信号，no_data 不误拦推荐票。
G4 等前向样本 >=4 周后再做 9:20-9:25 过程信号研究，只产出报告，不进入生产确认门。

每批完成后运行对应 pytest；涉及前端时运行 cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build。最终交付必须列出改动文件、报告路径、测试命令结果、未完成/阻塞原因、下一步建议。若任一批次不满足验收门，停止后续批次并输出原因。
```
