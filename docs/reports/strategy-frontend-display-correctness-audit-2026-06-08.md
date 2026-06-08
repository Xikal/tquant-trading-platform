# 策略旧前端展示正确性审计报告（2026-06-08）

## 范围与边界

- 验收对象：生产旧前端 `frontend/` 的策略相关入口与展示链路。
- 覆盖入口：`/monitor`、`/monitor/market`、`/playbook`（`/low-buy` 重定向）、`/strategy-tracking`、`/backtest`（`/strategy` 重定向）、`/paper`（`/performance` 重定向）。
- 未纳入修复范围：`frontend-next/` 仅作为既有风险上下文保护；本轮未修改。
- 未改动：`strategy_policy.py`、生产策略公式、`production_score` 口径、priority board 后端排序语义、风控阈值、strategy_engine shadow-only 边界。
- 未执行：部署、切流、真实写入、自动交易改动。

## 页面到数据链路矩阵

| 页面/入口 | 组件/模块 | API | Schema/Type | 后端 builder/service | 数据源/表 | 展示字段核对结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `/monitor` 实时行动 | `frontend/src/features/monitor/MonitorActionPage.tsx`、`frontend/src/features/trading-workspace/useMonitorData.ts`、`workspaceViewModels.ts` | `/bff/v1/workspace/monitor?view=action`、fallback `/monitor/snapshot`、`/screeners/low-buy/priority-board` | `LowBuyPriorityBoardResult`、`LowBuyPriorityBoardItem` | `monitor_snapshot_service.build_monitor_snapshot`、`low_buy/priority_board.py`、`priority_response.py`、BFF workspace | `low_buy_*` snapshots/read models、watchlist、market breadth/emotion | `monitor_snapshot.priority_board` 嵌套读取正确；stale/data_quality/read_path 有提示；已修复前端 worker 不再按分数重排后端榜单。 |
| `/monitor/market` 市场环境 | `MonitorMarketPage.tsx`、`MonitorPage.panels.tsx` | `/bff/v1/workspace/monitor?view=market`、market breadth/pulse fallback | `MarketBreadth`、`IntradayMarketPulse`、priority board market fields | `monitor_snapshot_service`、market pulse/breadth services | market breadth/emotion/hourly snapshots | 市场状态、涨跌比例、涨停/跌停、热点板块来自后端字段；BFF 可选源失败时主数据仍可展示并显示降级提示。 |
| `/playbook` 选股宝典 | `features/playbook/PlaybookPage.tsx`、`queries.ts`、`workspaceViewModels.candidateToCard` | `/screeners/low-buy?strategy=...`、`/screeners/low-buy/quotes` | `LowBuyScreenerResult`、`LowBuyCandidate` | `LowBuyScreenerService.screen`、`screening_read.py`、quote refresh | low-buy materialized full/quick snapshots、daily history | strategy key/title、buy_signal_state、score、entry/stop/reasons 直接取后端；stale/snapshot_warning 有提示；已修复“当前确认推荐”不再用自然日误判非交易日。 |
| `/strategy-tracking` 策略跟踪 | `StrategyTrackingPage.tsx`、`StrategyTrackingTable.tsx`、`queries.ts` | `/strategy-tracking/snapshot`、detail/review/holding/report | `StrategyTrackingSnapshotResponse`、`StrategyTrackingItem` | `StrategyTrackingSnapshotBuilder`、`StrategyTrackingService`、live quote overlay | strategy tracking snapshots、low-buy lifecycle、quote overlay | 排序/筛选由请求参数交给后端 snapshot/service；前端展示 signal/lifecycle/status/date/risk/sector，不重算生产分数。strategy_engine 仅显示“影子校验”文案。 |
| `/backtest` 回测 | `BacktestDashboard.tsx`、`BacktestDashboard.panels.tsx`、`api/backtests.ts` | `/backtests*`、`/backtests/verdict-thresholds`、research optimize/validate | `BacktestRunDetail`、`BacktestTrade`、`ExecutionModelPreview` | `backtests.py`、backtest engine/job/persistence services | backtest runs/trades/metrics/equity | 收益、回撤、胜率、交易明细、净值曲线按 API 字段展示；execution_model_preview 明确标注 Preview/非事实源，`replacement_enabled=false` 不替代真实收益。 |
| `/paper` 模拟盘 | `PaperTradingPage.tsx`、`PaperOrderEntryModal.tsx`、`PaperDetailTabs` | `/bff/v1/workspace/paper`、`/paper/*`、`/screeners/low-buy/priority-board` | `PaperAccount/Position/Order/Trade/Performance`、`LowBuyPriorityBoardItem` | `paper/*` services、paper routes、low-buy priority board | paper account/order/trade/performance、low-buy priority board | 持仓/订单/绩效按后端字段展示；模拟盘导入生产买入信号只导入后端确认状态，已改为按后端发布交易日判断，不在周末/节假日误空。 |

## 已修复问题

### P1：旧前端 worker 可能重排生产 priority board

- 文件：`frontend/src/workers/computeSync.ts`
- 现象：`normalizeMonitorPrioritySync` 对 `priority_board.items` 按 `priority_score ?? production_score` 降序排序，可能覆盖后端已经确定的生产排序。
- 修复：归一化仅过滤无 symbol 项并按 limit 截断，保留后端顺序。
- 回归：`frontend/src/workers/__tests__/computeSync.test.ts` 改为高分在后但期望保留原顺序。
- 影响：防止展示层改变生产榜单排序语义。

### P1：模拟盘/今日推荐使用自然日判断，非交易日会误判最新发布策略过期

- 文件：`frontend/src/features/workspace-shared/todayRecommendations.ts`
- 现象：`filterTodayConfirmedPriorityItems`、`filterTodayConfirmedCandidates` 只比较 `latest_trade_date` 与北京时间自然今天。周末/节假日或收盘前后发布窗口中，后端最新可用交易日可能不是自然今天。
- 修复：新增 `isCurrentPublishedTradeDate`，priority board 优先比较后端 `latest_trade_date` 与 `latest_available_trade_date`；playbook 没有 expected trade date 字段时优先信任后端 `stale=false`，只有旧 payload 缺少 stale 标记时才回退自然日。注意 `LowBuyScreenerResult.as_of_date` 是快照生成时间，不作为交易日判断依据。
- 回归：`todayRecommendations.test.ts` 增加周末场景，确认 2026-06-06 仍保留后端 2026-06-05 的当前确认信号。
- 影响：模拟盘导入生产买入信号和“当前推荐”不再因自然日误空。

### P2：后端 read-path 测试随真实日期漂移

- 文件：`backend/tests/test_low_buy_read_paths.py`
- 现象：用例硬期望 `2026-06-05`，在 2026-06-08 运行时生产逻辑返回当前 expected trade date，导致测试失败。
- 修复：仅在该测试内 patch `expected_low_buy_trade_date` 与 `published_low_buy_trade_date`，固定测试语境。
- 影响：不改变生产逻辑，防止交易日测试因当前日期漂移假失败。

## 已确认正确的模块

- 低吸/priority board：后端 `priority_response.py` 输出 `latest_trade_date`、`latest_available_trade_date`、`stale`、`stale_reason`、`data_quality`、`production_sort_replaced`、`items`；旧前端按字段展示，不重算分数。
- BFF/monitor：旧前端读取 `monitor_snapshot.priority_board` 嵌套路径；BFF 成功时可选 fallback 失败不会阻断主数据，可显示部分降级提示。
- strategy_engine：后端 payload 明确 `shadow_only=true`、`replacement_enabled=false`、`production_sort_replaced=false`；旧前端只显示“影子校验一致/复核”，未把 shadow 分数当生产排序。
- 策略跟踪：旧前端请求 `/strategy-tracking/snapshot`，筛选/排序通过 query 参数进入后端；表格展示 signal_state、lifecycle_status、latest_trade_date、recommendation_days、risk/sector 字段。
- 回测：执行模型预览标注为 `Preview · 非事实源`，展示 `replacement_enabled=false`，未替换真实收益/回撤/交易字段。
- 模拟盘：订单、持仓、绩效展示按 `/paper/*` 与 paper BFF 字段；本轮未触发真实写入。

## 需产品/量化确认的问题

- `/playbook` 的候选分层在前端按 `buy_signal_state` 分为确认可买/观察确认/接近买点/观察/放弃，这是展示分组，不改变后端排序；若产品要求“每个 tab 内也完全保留后端 candidate 原始顺序”，需另行确认。
- 策略跟踪页面的默认排序是后端参数 `max_gain_desc`，这是复盘视角排序，不等同生产 priority board 排序；如要默认展示生产优先级，需要后端提供明确字段/排序契约后再改。

## 剩余风险

- 本轮为本地代码与 mock smoke 验证，未部署、未切流、未验证云端真实账号数据。
- 真实线上数据是否已经包含本地修复取决于后续部署；本轮不做部署。
- `frontend-next/` 当前仍有既有未提交改动，本轮未触碰；其策略展示一致性不属于本报告修复范围。

## 验证命令与结果

| 命令 | 结果 |
| --- | --- |
| `git status --short` | 已执行；发现既有 `frontend-next/`、Go BFF、`docs/reports/frontend-next-reaudit-2026-06-07.md` 未提交/未跟踪文件，已保护。 |
| `cd frontend && npm test -- --run src/workers/__tests__/computeSync.test.ts src/features/workspace-shared/todayRecommendations.test.ts` | 2 files passed，9 tests passed。 |
| `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest ...`（low_buy、strategy_engine boundary、monitor/BFF、strategy_tracking、backtest、paper 目标集） | 187 passed，1 warning（urllib3/LibreSSL 环境警告）。 |
| `cd frontend && npm run lint` | passed；refactor/state/css guards passed；首次 bundle budget 因 dist report 未生成而跳过。 |
| `cd frontend && npm test -- --run` | 85 files passed，300 tests passed。输出中的 state guard failed 为测试夹具 stderr，命令退出码 0。 |
| `cd frontend && npm run build` | passed；生产构建成功。 |
| `cd frontend && npm run analyze` | passed；bundle report written；bundle budget passed：first_screen_js_gzip_kb 318.01，total_gzip_kb 819.92。 |
| `cd frontend && npm run smoke:monitor-bff` | passed；`dist/monitor-bff-smoke-report.json`，`ok=true`，BFF count 1，无登录门禁/错误。 |
| `cd frontend && npm run smoke:core-workflow` | passed；`dist/core-workflow-smoke-report.json`，`/monitor`、`/playbook`、`/backtest`、`/paper`、`/settings` 均 ok。 |
| `cd frontend && CORE_WORKFLOW_SMOKE_SCENARIO=stale npm run smoke:core-workflow` | passed；`dist/core-workflow-smoke-report-stale.json`，stale copy ok。 |

## 最终结论

当前旧前端策略展示链路已完成本地端到端正确性审计并修复 2 个展示/联动层问题。生产策略公式、生产排序语义、`strategy_policy.py`、后端业务逻辑、自动交易链路均未改变。当前结论仅代表本地验证通过；未部署、未切流。若要让线上生效，需要用户另行明确授权部署。

---

## 独立复核补充（2026-06-08 续审）

> 续审角色对上述修复做了独立交叉核验与全量重跑，确认结论成立，并补记一处在范围内但原文未单列的 BFF 改动。

### 契约字段交叉核验（字段名匹配 API 契约）

- `isCurrentPublishedTradeDate` 依赖的 `latest_available_trade_date`、`stale` 在**后端契约**确有产出：`backend/app/models/schema_defs/screener_parts/priority.py:174-175,189`（priority board）、`responses.py:34-35`（screener）；由 `priority_response.py:65-78` 实际写入。
- **前端类型**亦声明：`frontend/src/types/playbookResults.ts:324-329`（priority board：`latest_available_trade_date?`、`stale?`）、`:91-95`（screener：`stale?`、`stale_reason?`）。
- **易混淆点已澄清**：screener 级用 `stale`（响应级），candidate 级用 `is_stale`（个股 quote 级，`candidate.py:137` / `formatters.ts:33,81`）——语义不同且各自使用正确。`todayRecommendations.ts:104` 读的是 screener 级 `playbook.stale`，**映射正确**，周末/节假日修复有效，不会因字段错配静默回退自然日。

### 前端重排完整性核验（防生产排序被展示层覆盖）

- 全前端 `.sort(...)` 含 `priority_score/production_score`：**除已修复的 `computeSync.ts` 外无其它命中**——生产榜重排已被彻底移除，非仅一处。
- `strategy_engine` shadow 字段：前端**未用于任何排序/打分**；`StrategyTrackingTable.tsx:197,290-291` 仅渲染文案 `影子校验一致 · 不影响真实排序` / `影子校验待复核 · 不影响真实排序`，shadow-only 边界在展示层显式表达。

### 范围内补记：Go BFF 市场视图源超时

- 文件：`go-services/bff-gateway/cmd/bff-gateway/workspace_aggregate.go`（已有未提交改动，属本轮 BFF 展示一致性范围）。
- 内容：把 `market_breadth / monitor_review / sector / paired_hedge` 等可选源超时**按 view 区分**——`view=market` 用 4s/2s（市场页主数据），`action` 视图保持 250ms/120ms（仅辅助）。避免 `/monitor/market` 因紧超时丢主数据。
- 影响：纯取数超时口径，不改策略语义；`main_test.go` 同步更新，`test_go_bff_shadow.py` 续审通过。

### 续审重跑结果（全部新跑，全绿）

| 命令 | 结果 |
| --- | --- |
| 后端 `pytest`（low_buy read/trade-date/production_scoring/priority variants/materialization/recommendation_duration、strategy_engine boundary+gate、bff monitor+strategy、monitor routes、execution_model boundary、paper_auto_confirmation） | **66 passed** |
| 后端 `pytest`（strategy_tracking + variant filters + go_bff_shadow） | **24 passed** |
| 前端回归 `todayRecommendations.test.ts` + `computeSync.test.ts` | **9 passed** |
| 前端 `npm run lint` | passed（refactor/state/css/bundle-budget guard 全绿；first_screen 318KB / total 819.92KB gzip） |
| 前端 `npm test -- --run` | **85 files / 300 passed** |
| 前端 `npm run build` / `npm run analyze` | passed；bundle budget passed |
| 旧 `frontend/` + 后端 tracked 业务改动 | 仅展示层（computeSync/todayRecommendations）+ 测试 + Go BFF 超时；`strategy_policy.py`、生产公式、production_score 口径、风控阈值 **0 改动** |

### 续审结论

- **已验证正确（旧前端策略展示）**：低吸/priority board 字段映射与不重排、BFF 嵌套路径与降级、strategy_engine shadow-only 文案、回测 Preview 非事实源标注、模拟盘展示字段、交易日发布逻辑（周末/节假日）。
- **仍需产品/量化确认（非缺陷，口径选择）**：playbook 候选分 tab 分组是否需 tab 内完全保留后端原序；strategy-tracking 默认 `max_gain_desc` 复盘排序是否要改为生产优先级排序（需后端先给排序契约）。
- **剩余风险**：本地验证，未部署未切流；线上生效需另行授权；`frontend-next/` 既有改动不在本轮范围。
- **平台影响：不影响**生产策略语义/排序/风控/自动交易；仅修正展示层映射与交易日判断。
