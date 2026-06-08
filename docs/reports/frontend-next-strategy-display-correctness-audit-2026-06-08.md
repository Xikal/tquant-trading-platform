# frontend-next 策略展示正确性审计报告（2026-06-08）

## 范围与边界

- 审查对象：`frontend-next/` 中 `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/backtest`、`/next/paper`、`/next/playbook` 的策略结果、排序、状态、日期、分数、标签、回测/模拟盘联动展示。
- 对照来源：后端低吸/priority board/BFF/strategy-tracking/backtest/paper 服务，OpenAPI 生成类型，旧前端已验证行为，仅作字段与语义参照。
- 硬边界：未改 `strategy_policy.py`，未改生产策略公式、`production_score`、priority board 排序语义、风控阈值；`strategy_engine` 仍是 shadow-only，不替代 low-buy/priority board/production scoring。
- 本轮未部署、未切流；旧前端 `frontend/` 未作为本轮修复对象。
- 开始前已执行 `git status --short`。工作树中存在本轮前已有的 backend、old frontend、Go BFF、报告/截图等脏文件，本轮未回滚这些改动。

## 链路矩阵

| 新前端入口 | 组件/模型 | 请求函数/API | 后端 builder/service | 数据源与口径 | 审计结论 |
|---|---|---|---|---|---|
| `/next/monitor` | `MonitorActionPage.tsx`、`monitorActionModel.ts` | `apiClient.monitorWorkspace("action")` -> `/api/bff/v1/workspace/monitor?view=action` | `monitor_snapshot_service`、`low_buy/priority_board`、BFF monitor workspace | `monitor_snapshot.priority_board` 优先；priority items 保留后端顺序 | 已确认：只过滤 lane，不按 `priority_score/production_score` 重排；缺市场状态不再伪造“下跌退潮/观望/100% 火力”。 |
| `/next/monitor/market` | `MonitorMarketPage.tsx`、`monitorMarketModel.ts` | 同 BFF，`view=market` | monitor BFF + market breadth/pulse/review | 可选 market 源失败不阻断主 snapshot | 已确认：主数据可用时展示；`partial/stale/cache` 状态区分；自然日“今天”改为当前快照语义。 |
| `/next/strategy-tracking` | `StrategyTrackingPage.tsx`、detail/review/tabs | `/api/bff/v1/workspace/strategy`，必要时读 `/api/strategy-tracking/*` | `StrategyTrackingService`、strategy BFF | 后端 `items/performance/holding/review/journal/relative_strength` | 已修复：去除静态行业分布、Sharpe、漂移、诊断、审计样本等假数值；shadow 仅作只读对照说明。 |
| `/next/backtest` | `BacktestPage.tsx`、`backtestModel.ts` | `/api/backtests*`、`/api/strategies/meta` | backtest v2 API/engine/job persistence | run detail、trades、attribution、OOS、execution preview | 已修复：不再显示硬编码“样本分组/日志/OOS/静态 KPI”；策略选项来自后端 meta 或历史 run。 |
| `/next/paper` | `PaperPage.tsx`、`PaperWorkflowTabs.tsx`、`PaperMechaHud.tsx` | `/api/bff/v1/workspace/paper`、paper APIs | paper workspace/performance/order/risk services | account、positions、orders、trades、risk、auto runs | 已修复：无后端自动交易记录时显示空态，不再伪造 09:30 日志、同步率、指数馈入。 |
| `/next/playbook` | `PlaybookPage.tsx`、`playbookModel.ts` | `/api/screeners/low-buy*`、priority board、quotes、strategy meta | low-buy screener/priority board/strategy meta | screener `confirmed_candidates/candidates/watch_candidates` 优先，空时回退 priority board | 已修复：读取正式 `candidates` 字段；发布日期来自后端 `latest_trade_date/latest_available_trade_date`，不使用自然日。 |

## 已修复问题

1. **Playbook 只读 `watch_candidates`，遗漏正式 `candidates`**
   - 文件：`frontend-next/src/features/playbook/playbookModel.ts`
   - 修复：`priorityRecordsFromBoard` 合并 `confirmed_candidates`、`candidates`、`watch_candidates`；选中策略候选优先于全局 priority board。
   - 测试：`playbookModel.test.ts` 增加正式 `candidates` 优先级断言。

2. **Playbook 使用自然日/“今日”语义**
   - 文件：`PlaybookPage.tsx`、`playbookModel.ts`
   - 修复：展示后端发布交易日；文案改为“发布日/当前交易日”，避免周末、节假日误判。

3. **Backtest 展示硬编码归因、日志、样本外窗口和静态 KPI**
   - 文件：`BacktestPage.tsx`、`BacktestPrimitives.tsx`、`backtestModel.ts`
   - 修复：仅展示后端 `detail/result` 返回的 attribution、execution model、quality notes、OOS/walk-forward/trades；缺字段显示空态。
   - 测试：新增 `backtestModel.test.ts`，E2E 断言不再出现“样本分组A”。

4. **Strategy Tracking 多处假数据兜底**
   - 文件：`StrategyTrackingPage.tsx`
   - 修复：去除 `1.82` Sharpe、`2.14 : 1` 盈亏比、行业 45/30/15、`99.2%` 影子一致性、`平均 0.85 秒`、`1,613 次` 审计样本等静态值；缺数据显示 `--` 或“后端暂未返回”。
   - 测试：E2E 增加静态假数值不可见断言。

5. **Monitor Action 缺字段时伪造市场判断**
   - 文件：`MonitorActionPage.tsx`、`monitorActionModel.ts`
   - 修复：缺 `market_state/firepower/direction/portfolio_risk` 时显示“未返回/--”，不再默认“下跌退潮/观望/清晰/100% 火力”。
   - 测试：`monitorActionModel.test.ts` 增加缺字段不伪造断言。

6. **Paper 自动交易日志伪造实时记录**
   - 文件：`PaperMechaHud.tsx`、`PaperWorkflowTabs.tsx`、`PaperPage.tsx`
   - 修复：无后端 runs/risk/status 时显示明确空态；时间缺失显示 `--`，同步率仅来自后端字段。
   - 测试：`paper-mecha.spec.ts` 增加无 runs 不显示 `SYSTEM_INIT/84.2%/指数馈入` 断言。

7. **自然日“今日/今天”策略展示语义**
   - 文件：monitor/playbook/paper/strategy-tracking/monitor-market 页面
   - 修复：策略结果相关文案统一为“发布日/当前快照/当前交易日”，与后端 `published_low_buy_trade_date(db) or expected_low_buy_trade_date(db)` 口径一致。

## 已确认正确

- Priority board：新前端读取 `monitor_snapshot.priority_board`，只做展示过滤，不重排后端生产顺序。
- 分数与标签：`production_score/priority_score/signal_state/buy_signal/strategy_weight_score/risk tags` 均来自后端字段或 OpenAPI 类型，不在 worker 或页面中重算。
- 日期：低吸榜、playbook、monitor 使用后端发布/可用交易日，不用自然日判断“最新策略结果”。
- BFF：`view=action` 与 `view=market` 分开；主 snapshot 可用时，可选 market fallback/partial error 不阻断主展示。
- `strategy_engine`：页面只保留 shadow-only 说明，不替代生产排序、生产评分或 priority board。
- 旧前端：仅作为对照；本轮未做旧前端策略展示改造。

## 需确认项与剩余风险

- Backtest 提交面板中的执行假设仍应长期由后端 `execution_assumptions/execution_model_preview` 驱动；当前已避免展示伪造结果，但具体 UI 文案如需精确到费率口径，仍建议由量化确认后统一。
- Playbook lane 文案是展示分桶，不改变候选顺序；如果产品要求 lane 标题完全等同后端 `simple_bucket_text`，可继续收敛。
- 本轮是本地/模拟 API 与目标后端 pytest 验证，未做线上真实数据验收、未部署、未切流。

## 验证结果

| 命令 | 结果 |
|---|---|
| `cd /Users/j/Documents/gupiao && git status --short` | 已执行，识别并保护既有脏文件。 |
| `cd frontend-next && npm run typecheck` | 通过。 |
| `cd frontend-next && npm run lint` | 通过，含 refactor/css/boundary/bundle budget guard。 |
| `cd frontend-next && npm test -- --run` | 24 files / 105 tests passed。 |
| `cd frontend-next && npm run build` | 通过，Vite build 成功。 |
| `cd frontend-next && npx playwright test tests/e2e/backtest-data-settings.spec.ts tests/e2e/monitor-workflows.spec.ts tests/e2e/strategy-tracking.spec.ts tests/e2e/paper-mecha.spec.ts tests/e2e/analysis-playbook.spec.ts --project=chromium` | 16 passed，覆盖 `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/backtest`、`/next/paper`、`/next/playbook`。 |
| 后端目标 pytest（low_buy、trade-date、priority board、strategy_engine boundary/gate、BFF、strategy_tracking、backtest、paper） | 252 passed, 1 urllib3/OpenSSL warning。 |
| `cd go-services/bff-gateway && go test ./cmd/bff-gateway` | passed。 |

## 最终结论

`frontend-next/` 策略相关展示已完成本轮端到端正确性审查和最小修复。核心策略结果、排序、状态、日期、分数、标签、回测/模拟盘联动信息已按后端真实数据和 API 契约展示；发现的静态假数据、自然日误导、shadow-only 误导、缺字段伪造判断均已修复并补测试。

未部署、未切流；正式 cutover 仍需单独授权。
