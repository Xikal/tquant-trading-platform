# 集合竞价辅助能力需求文档（核验版）

状态：核验通过，按本文进入开发评审
日期：2026-06-11
来源草案：`docs/call-auction-assist-requirements-2026-06-10.md`
适用范围：A 股集合竞价信息用于已持仓票晨间风险提示、策略推荐票次日入场确认门、竞价数据前向采集研究
关联基线：`docs/engineering-conventions.md`、`docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`、`docs/strategy-success-rate-optimization-requirements-2026-06-11.md`、`TRADING_QUANT_LEAD_PLAYBOOK.md`

## 1. 核验结论

原草案提出的问题成立，解决方案总体可行，但必须带三项修正后执行：

1. `/next/paper` 当前在 `frontend-next/src/app/routeTree.tsx` 中重定向到 `/next/monitor`，因此 Phase 2 的首个展示落点应先落在现有 `/next/monitor` 持仓/自选区域；若要在 `/next/paper` 展示，必须先恢复或新建 frontend-next Paper 页面。
2. 竞价过程数据（9:20-9:25 虚拟撮合价、匹配量、未匹配量）当前没有表、provider、历史数据源或回补链路，只能从上线日起前向采集；Phase 3 不能承诺历史回测。
3. `akshare stock_zh_a_hist_pre_min_em` 或东财盘前分时是否稳定可用，必须先做交易日小样本 provider spike。未通过 spike 时，Phase 2/3 只能保持 `no_data`，不得误拦推荐票或生成伪提示。

在上述修正下，推荐落地顺序维持原草案的三阶段：Phase 1 先用历史日线 `open/pre_close` 做 gap 确认门回测；Phase 2 再做竞价采集和持仓晨间风险哨；Phase 3 等前向样本积累后研究竞价过程信号。

## 2. 当前项目事实基线

### 2.1 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic、SQLite/MySQL、Redis 可选缓存、RuntimeTaskQueue。
- 前端现状：旧 `frontend` 为 React；`frontend-next` 为 Solid + Vite + TanStack Router/Query，OpenAPI 类型生成在 `frontend-next/src/generated/api-types.ts`。
- 数据源：免费数据源优先，已有 provider router、ProviderResult、provider circuit、timeout 与降级质量字段。
- 任务：已有 DB-backed RuntimeTaskQueue、任务注册表、runtime worker、analytics worker。
- 文档规范：新文档放 `docs/`，报告放 `docs/reports/`，大型机器产物放 `backend/data/reports/` 或 `backend/data/analytics/reports/`。

### 2.2 已存在可复用能力

| 能力 | 当前证据 | 对本需求的含义 |
|---|---|---|
| VWAP/尾盘盘中确认 | `backend/app/services/low_buy/intraday_confirmation.py` 已有 `VWAP_CONFIRMATION_STRATEGIES`、`LATE_SESSION_CONFIRMATION_STRATEGIES`、`IntradayConfirmation`、`intraday_confirmation_passes`、`intraday_confirmation_hint` | 可扩展出竞价确认模块，但不应直接塞入生产排序 |
| 次日事件计划 | `backend/app/services/low_buy/next_day_event_model.py` 已生成 `confirmation_rules`、`next_day_action` 等文案 | 可升级为读取真实 `auction_state`，但契约需新增字段 |
| 次日计划契约 | `backend/app/models/schema_defs/screener_parts/plans.py` 的 `LowBuyNextDayEventPlanOut` 当前没有竞价状态字段 | 需要扩展 `auction_state`、`auction_reason_text`、`auction_as_of` 等字段并同步 OpenAPI |
| 竞价因子占位 | `backend/app/services/low_buy/factor_functions.py` 已有 `pre_market_auction_factor` stub，权重 0，状态为缺竞价快照 | 问题确实未落地；可作为现状证据，不直接复用为生产因子 |
| 推荐候选目标集合 | `backend/app/services/market_quote_cache_refresh.py` 的 `build_quote_cache_demand_symbols` 已汇总 priority board、monitor cache、watchlist、paper positions、strategy tracking、热点板块成员、指数 ETF | 竞价采集可以复用同源需求集，再按交易日和数量限额裁剪 |
| 模拟盘持仓 | `backend/app/models/paper_entities.py` 有 `PaperPosition`、`PaperAccount` | 持仓晨间风险哨可基于 `quantity > 0` 的持仓 |
| 自选股 | `backend/app/models/market_entities.py` 有 `Watchlist`、`UserWatchlist` | 自选区可生成 advisory 提示 |
| AKeyLevel | `backend/app/services/key_levels/*`、`backend/app/models/schema_defs/key_levels.py`、`backend/app/api/routes/key_levels.py` 已有支撑/压力、缓存、物化任务和 feature flag | 破位风险可复用 `support_price/support_zone_low/data_quality` |
| 持仓纪律提示 | `backend/app/services/trading_experience/holding_discipline.py` 已按 AKeyLevel 生成持仓纪律 hint | 竞价风险哨可沿用 hint 语义，但需新增竞价专属状态与文案守卫 |
| RuntimeTask | `backend/app/services/tasks/queue.py`、`backend/app/services/tasks/registry.py` 已有入队、幂等、重试、心跳、artifact | 采集任务应注册为 runtime 任务，不进入 Web 请求线程 |
| ProviderResult/circuit | `backend/app/services/market/providers/quality.py`、`backend/app/services/market/providers/router.py` 已有质量枚举、usable 判定、熔断、timeout | 竞价 provider 可按同一质量与熔断模式接入 |
| 历史 gap 数据 | `backend/app/models/market_entities.py` 的 `DailyBarSnapshot` 有 `open_price/pre_close/is_suspended` | Phase 1 可做历史 gap 确认门；必须只读 `open/pre_close`，避免未来函数 |
| 竞价专表 | 当前没有 `auction_snapshots`、`auction_confirmations`、`auction_position_hints` | 需要新增 Alembic、SQLAlchemy model、schema 和 API |
| frontend-next Paper 页面 | `/next/paper`、`/paper` 当前 redirect 到 `/next/monitor` | 原草案展示落点需修正 |

### 2.3 外部交易机制核验

上交所 2026 年修订版交易规则、深交所 2023 年修订版交易规则均确认：竞价交易申报时间包含 9:15-9:25；9:20-9:25 开盘集合竞价阶段不接受撤销申报。本文据此确认“9:15-9:20 噪声大、9:20-9:25 更适合作为过程研究窗口、9:25 结果可作为确认输入”的市场机制口径可用。

参考：

- [上海证券交易所交易规则（2026年修订）](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml)
- [深圳证券交易所交易规则（2023年修订）](https://docs.static.szse.cn/www/lawrules/rule/stock/trade/W020230217564423808793.pdf)

## 3. 问题是否成立

### P1：平台目前没有可执行的集合竞价信息

结论：成立。

证据：

- `pre_market_auction_factor` 仍为 stub，权重为 0，标注缺逐股集合竞价快照。
- 当前数据库模型只有日线、分钟、逐笔和盘中确认快照，没有独立竞价快照。
- `next_day_event_model.py` 中的竞价/开盘规则是文案，不引用真实 `auction_state`。

影响：推荐票在次日 9:25 后没有“弱承接跳过/降级入场”的可执行确认门，已持仓票也没有开盘前竞价破位提示。

### P2：集合竞价是 S4b 入场确认门的合理修复方向

结论：成立，但必须先回测。

证据：

- `docs/reports/strategy_24m_duckdb_report.md` 显示 `first_board` 24M 总体强，但最近 quarter_proxy OOS 成交 46、PF 0.75、收益 -1.01%。
- `docs/strategy-success-rate-optimization-requirements-2026-06-11.md` 已把 `first_board` OOS 诊断与 `volume_shrink` 分时确认列入修复方向。
- `DailyBarSnapshot.open_price/pre_close` 可支持历史 gap 回测。

约束：竞价确认门不得直接改生产排序、`production_score` 或 `strategy_policy.py`。任何启用必须经过 24M、walk-forward、OOS、样本留存、成本与守卫测试。

### P3：持仓晨间风险哨有业务价值且可工程实现

结论：成立。

证据：

- Paper 持仓、自选股、AKeyLevel、持仓纪律 hint 均已有。
- 现有持仓纪律以最新价/关键位为主，没有 9:25 后开盘前竞价视角。

约束：提示必须是 advisory，只展示风险事实和观察上下文，不输出“建议买入/卖出/必涨/低吸”等越界文案，不触发自动交易或模拟盘订单。

### P4：原草案中的 `/next/paper` 展示位不完全成立

结论：需修正。

证据：`frontend-next/src/app/routeTree.tsx` 当前将 `/next/paper` 和 `/paper` 重定向到 `/next/monitor`。

修正：Phase 2 最低可验收落点为 `/next/monitor` 的持仓/自选区域；`/next/paper` 展示必须作为前置任务恢复页面后再验收。

## 4. 产品定位

集合竞价信息只用于“观察提示”和“次日入场确认过滤”，不是新策略、不是预测工具、不是自动交易入口。

核心定位：

- 对推荐票：在次日 9:25 后补充 `auction_state`，用于标记“今日确认/今日跳过/缺数据保持现状”。
- 对持仓票：在 9:25 后、连续竞价前提供竞价破位、低开观察、高开放量强势等风险提示。
- 对研究：前向采集 9:20-9:25 过程数据，积累样本后再评估是否升级为规则。

## 5. 目标与非目标

### 5.1 目标

1. 推荐票确认门：为 `first_board`、`volume_shrink` 等策略提供研究态 `auction_state`，回测达标后才允许灰度展示。
2. 持仓风险哨：对 paper 持仓和自选股展示 9:25 后竞价提示，联动 AKeyLevel 支撑/止损风险。
3. 数据采集：建立竞价结果与过程快照的前向采集、质量标记、任务观测、provider 熔断。
4. 工程隔离：默认 feature flag 关闭，关闭时完全回到当前行为。
5. 证据闭环：Phase 1 先交付回测报告，Phase 2 交付采集质量报告，Phase 3 交付前向研究报告。

### 5.2 非目标

1. 不做竞价选股榜、竞价排名、抢筹榜。
2. 不自动下单，不生成模拟盘订单，不触发实盘交易。
3. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
4. 不改变 `production_score`、priority board 排序语义、核心策略信号定义、风控阈值。
5. 不在 Web 请求线程实时拉竞价数据。
6. 不使用 9:15-9:20 可撤单段作为确认门决策输入。
7. 不伪造历史 9:20-9:25 过程数据。

## 6. 用户与场景

| 用户/角色 | 场景 | 成功标准 |
|---|---|---|
| 持仓用户 | 9:25 后查看 paper 持仓或自选股 | 看见竞价破位/高开强势/低开观察/无数据状态，知道证据和时间 |
| 策略使用者 | 次日准备跟踪生产优先榜推荐票 | 推荐票保留原信号，同时显示竞价确认状态和原因 |
| 量化研究者 | 验证竞价 gap 与策略收益关系 | 获取 24M 对照报告和不采纳结论，避免拍脑袋阈值 |
| 运维/QA | 检查采集是否健康 | RuntimeTask 有心跳、失败、重试、artifact；provider 熔断可观测 |

## 7. 状态与术语

### 7.1 推荐票确认状态

`auction_state` 枚举：

- `confirmed`：竞价结果通过当前阈值版本，允许当日继续观察入场条件。
- `rejected`：竞价结果触发弱承接或破坏入场前提，当日标记跳过/降级入场。
- `not_evaluated`：功能关闭、未到评估时间、非交易日、策略不适用。
- `no_data`：应评估但竞价数据缺失、停牌、新股无昨收、provider 失败。

缺数据策略：`no_data` 不阻断推荐票，保持当前行为，并显式展示“竞价数据缺失，未参与确认”。

### 7.2 持仓提示状态

`hint_code` 枚举：

- `auction_break_risk`：竞价开盘价跌破 AKeyLevel 支撑/止损风险线。
- `auction_gap_strength`：竞价高开且放量，仅提示强势观察或分层止盈上下文。
- `auction_gap_down`：低开但未破关键位，仅提示开盘观察。
- `auction_no_data`：缺数据。
- `auction_not_evaluated`：功能关闭、非交易日、9:25 前、目标不适用。

`level` 枚举：

- `info`：观察信息。
- `warn`：风险提示。

## 8. 阶段范围

### Phase 1：历史 gap 确认门研究

目的：在不依赖新 provider 的情况下，用历史日线 `open/pre_close` 验证 gap 类规则是否能提高策略净胜率。

范围：

- 新增研究态 `auction_confirmation` 规则引擎，先只支持 gap。
- 扩展或新增回测脚本，对 `first_board`、`volume_shrink` 做基线 vs 竞价确认门对照。
- 产出 Markdown + JSON 报告。
- 不接入生产排序，不改 priority board。

可用数据：

- `DailyBarSnapshot.open_price`
- `DailyBarSnapshot.pre_close`
- `DailyBarSnapshot.is_suspended`
- 信号日/入场日交易日历

不可用或仅近似：

- 历史竞价成交量/额：只有 provider 或分钟首 bar 能近似时才进入研究报告，报告必须披露口径。
- 历史 9:20-9:25 过程数据：不可回补，不进入 Phase 1 采纳门。

### Phase 2：竞价采集 + 持仓晨间风险哨

目的：从上线日起采集竞价结果/过程快照，并在 monitor/paper 展示 advisory 提示。

范围：

- provider spike 通过后新增竞价 provider。
- 新增 `auction_snapshots` 落库与 RuntimeTask。
- 新增持仓/自选竞价 hint 生成服务。
- `/next/monitor` 展示持仓/自选竞价提示。
- `/next/paper` 若仍重定向，不作为 Phase 2 必须展示面；若恢复 PaperPage，则同步展示。

### Phase 3：竞价过程信号前向验证

目的：采集至少 4 周交易日样本后，研究 9:20-9:25 过程指标与次日收益/开盘后走势关系。

范围：

- 仅研究面板和报告，不进入推荐票确认门。
- 指标包括虚拟撮合价斜率、匹配量变化、未匹配量变化、最后一分钟突变。
- 统计显著且稳定后，另起需求进入 Phase 1 同款采纳门。

## 9. 功能需求

### FR-A 推荐票次日竞价确认门

FR-A1：新增独立竞价确认模块。

- 建议位置：`backend/app/services/low_buy/auction_confirmation.py`。
- 不直接扩写已接近职责边界的生产排序模块。
- 提供 `build_auction_confirmation(strategy_key, auction_context, thresholds)`、`auction_confirmation_passes(...)`、`auction_confirmation_hint(...)`。

FR-A2：新增策略适用集合。

- `AUCTION_CONFIRMATION_STRATEGIES = {"first_board", "volume_shrink"}` 先作为研究配置。
- `late_session_strong_support` Phase 1 不启用确认门，只观察。

FR-A3：确认规则必须阈值版本化。

- `first_board` 研究变体：
  - 弱承接：`gap_pct < g1_low`，或 `g1_low <= gap_pct <= g1_high` 且量能近似低于 `v1`。
  - 温和高开 + 放量：`confirmed`。
  - 极端高开、停牌、新股无昨收：按规则返回 `rejected` 或 `no_data`，不得硬编码拍脑袋阈值。
- `volume_shrink` 研究变体：
  - 大幅高开破坏低吸前提：`gap_pct > g2_high` 返回 `rejected`。
  - 普通 gap 不直接确认买点，只允许继续观察。

FR-A4：确认结果只改变“当日入场标记/提示”，不改变推荐信号和排序。

- priority board 原信号仍可见。
- `rejected` 只显示“竞价弱承接，今日不参与/继续观察”类文案。
- 不修改 `production_score`、`priority_score`、排序字段。

FR-A5：升级次日事件计划。

- `LowBuyNextDayEventPlanOut` 新增：
  - `auction_state`
  - `auction_reason_text`
  - `auction_gap_pct`
  - `auction_volume_ratio`
  - `auction_thresholds_version`
  - `auction_as_of`
  - `auction_data_quality`
- OpenAPI 与 `frontend-next/src/generated/api-types.ts` 同步。

FR-A6：feature flag 关闭时返回 `not_evaluated`。

- `auction_confirmation_enabled=false` 时不得触发任何确认门行为。
- 关闭前后 priority board 排序 hash 必须一致。

### FR-B 持仓晨间风险哨

FR-B1：目标集合。

- paper 持仓：`PaperPosition.quantity > 0`。
- 自选股：`UserWatchlist`。
- 如果账户/用户上下文不可得，自选只展示当前用户可见范围，不跨用户泄漏。

FR-B2：提示规则。

- `auction_break_risk`：
  - `auction_open_price < support_zone_low` 或 `auction_open_price < configured_stop_line`。
  - evidence 包含竞价价、gap、支撑/止损价、AKeyLevel 来源、as_of。
- `auction_gap_strength`：
  - `gap_pct >= threshold` 且 `auction_volume_ratio >= threshold`。
  - 文案只能提示“强势观察/分层止盈上下文”，不得说“追买”。
- `auction_gap_down`：
  - 低开达到阈值但未破关键位。
  - 文案为“低开未破关键位，开盘后观察承接”。
- `auction_no_data`：
  - provider 失败、停牌、新股无昨收、目标不在采集范围。

FR-B3：展示落点。

- Phase 2 必做：`/next/monitor` 的持仓/自选区域。
- 条件必做：若 `/next/paper` 恢复为真实页面，则在持仓卡展示同一 hint。
- 9:25 前展示 `not_evaluated` 或隐藏提示，不伪造竞价状态。

FR-B4：文案守卫。

禁止出现：

- 建议买入
- 建议卖出
- 必涨
- 低吸
- 抢筹必胜
- 自动执行

允许出现：

- 风险提示
- 观察
- 开盘后评估
- 数据缺失
- 仅供复盘/研究

### FR-C 竞价数据采集

FR-C1：provider spike。

正式开发前必须在一个真实交易日执行小样本 spike：

- 样本：10-30 只，覆盖沪市、深市、ETF、停牌/异常样本（如可得）。
- 时间：9:19:30-9:25:30。
- 输出：`docs/reports/call-auction-provider-spike-YYYY-MM-DD.md`。
- 内容：字段可得性、延迟、失败率、限频、9:20-9:25 过程字段是否存在、9:25 结果字段是否稳定。

FR-C2：provider 接入方式。

- 优先按 `backend/app/services/market/providers/*` 模式接入。
- 若 provider router protocol 扩展成本过高，可先建立 `backend/app/services/market/providers/auction_provider.py`，但仍必须返回 `ProviderResult`。
- 必须接入 provider circuit、timeout、source、data_quality。

FR-C3：采集任务。

新增 runtime 任务：

- `auction_snapshot_collect`
- `auction_snapshot_result_collect`
- `auction_position_hint_refresh`

任务要求：

- 注册进 `RUNTIME_TASK_REGISTRY`。
- 加入 runtime worker task types。
- 幂等键：
  - `auction_snapshot_collect:{trade_date}:{hhmm}:{symbol_batch_hash}`
  - `auction_snapshot_result_collect:{trade_date}:{symbol_batch_hash}`
  - `auction_position_hint_refresh:{trade_date}:{scope}:{user_or_account}`
- 只在交易日窗口入队。
- 非交易日不报缺数据。
- 9:25:30 后只做 result 补采，不继续过程采集。

FR-C4：目标集合。

目标集合来自 `build_quote_cache_demand_symbols(db)`，再做裁剪：

- paper 持仓优先。
- 用户自选优先。
- 最新 priority board 候选优先。
- 单日单窗口最大采集数量需要配置，默认不超过 300。
- 如果目标数超过限制，返回 `partial` 并记录被裁剪数量。

FR-C5：数据质量。

`data_quality`：

- `ok`：字段完整且时间落在有效窗口。
- `partial`：字段缺失但核心 price/gap 可用。
- `stale`：时间戳过期。
- `no_data`：无数据。
- `provider_failed`：provider 失败或熔断。

## 10. 数据契约

### 10.1 `auction_snapshots`

用途：采集层事实表。

字段：

```text
id
symbol
trade_date
captured_at
phase: locked_0920_0925 | result_0925
ref_price
matched_volume
unmatched_volume
amount
prev_close
gap_pct
auction_volume_ratio
source
data_quality
as_of
payload_json
created_at
updated_at
```

索引/约束：

- index: `(trade_date, phase)`
- index: `(symbol, trade_date)`
- unique: `(symbol, trade_date, phase, captured_at, source)`

说明：

- `result_0925` 可以只有一条或少量补采记录。
- `locked_0920_0925` 可以多条，代表过程快照。
- 原始 provider 字段放 `payload_json`，便于后续研究但不让前端直接依赖。

### 10.2 `auction_confirmations`

用途：推荐票确认层结果。

字段：

```text
id
symbol
strategy_key
signal_trade_date
entry_trade_date
auction_state: confirmed | rejected | not_evaluated | no_data
reason_code
reason_text
gap_pct
auction_volume_ratio
thresholds_version
engine_version
data_quality
evaluated_at
as_of
payload_json
created_at
updated_at
```

约束：

- unique: `(symbol, strategy_key, signal_trade_date, entry_trade_date, thresholds_version)`

### 10.3 `auction_position_hints`

用途：持仓/自选 advisory 结果。

字段：

```text
id
scope: paper_position | watchlist
user_id
account_id
symbol
trade_date
hint_code
level: info | warn
evidence_json
key_level_source
key_level_trade_date
data_quality
as_of
created_at
updated_at
```

约束：

- unique: `(scope, user_id, account_id, symbol, trade_date, hint_code)`
- 不跨用户返回 `UserWatchlist` hint。

## 11. API 契约

新增路由建议：`backend/app/api/routes/auction.py`。

### GET `/api/auction/confirmations`

查询推荐票竞价确认状态。

Query：

- `trade_date`
- `symbols`
- `strategy_keys`

Response：

```json
{
  "items": [
    {
      "symbol": "600000",
      "strategy_key": "first_board",
      "signal_trade_date": "2026-06-10",
      "entry_trade_date": "2026-06-11",
      "auction_state": "rejected",
      "reason_text": "竞价弱承接，今日仅观察。",
      "gap_pct": -2.1,
      "auction_volume_ratio": 0.0,
      "thresholds_version": "auction-gap-v1",
      "data_quality": "ok",
      "as_of": "2026-06-11T09:25:30+08:00"
    }
  ],
  "data_quality": "ok",
  "as_of": "2026-06-11T09:25:30+08:00"
}
```

### GET `/api/auction/position-hints`

查询持仓/自选竞价提示。

Query：

- `trade_date`
- `scope=paper_position|watchlist|all`
- `account_id` 可选

Response：

```json
{
  "items": [
    {
      "scope": "paper_position",
      "symbol": "600000",
      "hint_code": "auction_break_risk",
      "level": "warn",
      "evidence": ["竞价价 9.80", "AKeyLevel 支撑 9.92", "gap -2.10%"],
      "data_quality": "ok",
      "as_of": "2026-06-11T09:25:30+08:00"
    }
  ],
  "data_quality": "ok",
  "as_of": "2026-06-11T09:25:30+08:00"
}
```

### POST `/api/runtime-tasks`

继续复用现有 RuntimeTask 入队接口，不新增 Web 后台 loop。

## 12. Feature Flags

新增默认值均为 `false`：

- `auction_confirmation_enabled`
- `auction_position_hints_enabled`
- `auction_snapshot_collection_enabled`
- `auction_process_research_enabled`

落位要求：

- `backend/app/services/shared/feature_flags.py` 增加默认值和描述。
- 如需 settings 环境变量，也在 `backend/app/core/config.py` 声明。
- 前端只展示后端返回状态，不本地猜测启用状态。
- 关闭 flag 后：
  - 推荐票返回 `not_evaluated` 或不附加字段。
  - 持仓哨隐藏或显示未评估。
  - 采集任务不入队。
  - priority board 排序 hash 不变。

## 13. 前端需求

### 13.1 `/next/monitor`

新增竞价提示展示：

- 推荐票列表：显示 `auction_state` pill、原因 tooltip、as_of。
- 自选区：显示持仓/自选 `auction_position_hint`。
- 持仓区：如 monitor snapshot 已包含持仓，显示同一 hint。

四态展示：

- `confirmed`：中性/信息态，不用强行动色。
- `rejected`：警示态，但不隐藏原信号。
- `not_evaluated`：灰态或不展示。
- `no_data`：灰态，注明数据缺失。

### 13.2 `/next/paper`

当前页面未实现，路由重定向到 `/next/monitor`。因此：

- Phase 2 不把 `/next/paper` 作为必验收项。
- 若同批恢复 PaperPage，必须复用同一 API 和同一 UI 文案守卫。

### 13.3 设计限制

- 复用 `StatusPill`、`Tag`、`PagePanel` 等既有组件。
- 不新增大段解释性文案。
- 不使用“胜率已提升”“买入建议”等未经验证文案。
- 空态必须明确：未到 9:25、功能关闭、无竞价数据、非交易日。

## 14. 回测与研究要求

### 14.1 Phase 1 报告

输出：

- `docs/reports/call-auction-gap-confirmation-backtest-YYYY-MM-DD.md`
- `backend/data/reports/call-auction-gap-confirmation-backtest-YYYY-MM-DD.json`

报告必须包含：

- 策略：`first_board`、`volume_shrink`。
- 基线 vs 各阈值变体。
- 24M、walk-forward、OOS。
- 胜率、PF、净期望、最大回撤、样本留存、成交留存、最长无票。
- 成本、滑点、涨跌停、停牌、新股无昨收处理。
- 是否采纳；不采纳也要给结论。

### 14.2 采纳门

任一策略变体必须同时满足：

- PF 不低于基线。
- 净期望不低于基线。
- 胜率提升或回撤显著改善。
- 样本留存 >= 60%。
- OOS 不劣化。
- walk-forward 通过率不低于基线。
- 关闭/开启竞价 flag 后 priority board 排序字段 hash 一致。

未满足时：该策略保持 `auction_confirmation_enabled=false`，报告记录 `not_adopted`。

## 15. 测试要求

### 15.1 后端单测

新增测试建议：

- `backend/tests/test_low_buy_auction_confirmation.py`
- `backend/tests/test_auction_position_hints.py`
- `backend/tests/test_auction_snapshot_collection.py`
- `backend/tests/test_auction_routes.py`
- `backend/tests/test_auction_production_isolation.py`

覆盖：

- `confirmed/rejected/not_evaluated/no_data` 四态。
- 阈值边界。
- 停牌、新股、无昨收。
- 非交易日不评估。
- 9:25 前不评估。
- 缺 provider 时返回 `no_data`。
- `no_data` 不阻断推荐票。
- 不 import 或写入 `strategy_policy.py`、production scoring 写路径。
- priority board 排序 hash 守卫。

### 15.2 Provider/任务测试

覆盖：

- provider 返回 `ProviderResult`。
- provider circuit open 时任务降级为 `provider_failed`。
- 任务只在窗口入队。
- 幂等键稳定。
- registry 与 runtime worker task types 一致。
- 失败重试上限。
- 任务 artifact 写入报告路径。

### 15.3 前端测试

覆盖：

- 四态渲染。
- `rejected` 不隐藏原信号。
- `no_data` 不伪造成确认。
- 文案越界守卫。
- `/next/paper` 若未恢复，不把它列为成功验收。

## 16. 验收标准

### Phase 1 验收

1. 产出完整回测报告和 JSON。
2. 报告明确每个策略是否采纳。
3. `pytest` 相关 auction confirmation 与 backtest guard 通过。
4. priority board 排序 hash 守卫通过。
5. 无生产排序、`production_score`、`strategy_policy.py` 变更。

### Phase 2 验收

1. provider spike 报告证明数据源可用或明确不可用。
2. `auction_snapshots` 可在交易日采集到目标集合结果。
3. RuntimeTask summary 可见采集任务、心跳、失败和重试。
4. `/next/monitor` 正确展示持仓/自选四态。
5. 采集窗口外无常驻 Web 请求开销。
6. 缺数据时提示 `no_data`，不误拦推荐票。

### Phase 3 验收

1. 前向样本 >= 4 周交易日。
2. 报告展示过程指标与次日收益/开盘后走势关系。
3. 只输出研究结论，不进入生产确认门。
4. 若建议升级规则，必须重新走 Phase 1 采纳门。

## 17. 实施拆解

### G0 可行性与契约准备

- 完成 provider spike。
- 明确 Phase 2 是否恢复 `/next/paper`。
- 确认阈值配置版本命名。

### G1 Phase 1 回测

- 新增 auction confirmation domain schema。
- 用 `DailyBarSnapshot.open/pre_close` 生成 gap 样本。
- 扩展回测脚本和报告生成。
- 加生产隔离测试。

### G2 Phase 2 采集

- 新增 SQLAlchemy model 和 Alembic migration。
- 新增 provider、collector、repository。
- 注册 RuntimeTask。
- 写任务测试和 provider 测试。

### G3 Phase 2 展示

- 新增 auction API route。
- OpenAPI 导出并生成 frontend-next 类型。
- `/next/monitor` 接入。
- 加前端单测/E2E。

### G4 Phase 3 前向研究

- 累积样本。
- 输出研究报告。
- 决策是否进入下一轮需求。

## 18. 风险与降级

| 风险 | 影响 | 降级 |
|---|---|---|
| provider 不稳定 | 竞价数据缺失 | 返回 `no_data`，不阻断推荐票 |
| 9:15-9:20 诱导单污染 | 误判承接 | 决策硬排除，仅存档研究 |
| 阈值过拟合 | 回测好、实盘差 | OOS、walk-forward、季度复核、阈值版本化 |
| `/next/paper` 未恢复 | 展示验收失败 | Phase 2 先落 `/next/monitor` |
| 任务窗口错过 | 当日无样本 | `no_data` + 任务失败记录，不补造 |
| Web 请求拉 provider | 热路径超时 | 明确禁止，所有采集走 RuntimeTask |
| 与生产排序耦合 | 改变核心策略语义 | hash 守卫 + import 边界测试 |

## 19. 权限与合规边界

- 普通用户只能查看自己账户/自选相关提示。
- 管理员可查看采集任务、provider 质量、feature flag。
- 不提供下单接口。
- 不把竞价提示写入模拟盘订单。
- 所有 UI 文案必须保留“观察/提示/风险”语义。

## 20. 最终开发准入

本需求可进入开发，但开发前必须满足：

1. 执行 `git status --short`，保护当前在途改动。
2. 先做 provider spike 或明确 Phase 1-only。
3. 明确是否恢复 `/next/paper`；未恢复则 Phase 2 验收只要求 `/next/monitor`。
4. 先写数据契约和 feature flag，再写业务逻辑。
5. 任一生产行为变更必须有用户单独确认；默认只研究/展示，不部署、不切流。

## 21. 推荐验证命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_low_buy_auction_confirmation.py \
  backend/tests/test_auction_position_hints.py \
  backend/tests/test_auction_snapshot_collection.py \
  backend/tests/test_runtime_task_registry_governance.py \
  backend/tests/test_market_provider_contract.py \
  -q
```

```bash
cd frontend-next
npm run api:check
npm run typecheck
npm test -- --run
```

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/call_auction_gap_confirmation_backtest.py \
  --strategies first_board,volume_shrink \
  --months 24 \
  --output-md docs/reports/call-auction-gap-confirmation-backtest-$(date +%F).md \
  --output-json backend/data/reports/call-auction-gap-confirmation-backtest-$(date +%F).json
```

注：脚本名为建议新增项；若实现时复用既有 `low_buy_market_backtest.py`，命令需随实现更新，但报告字段和验收口径不得降低。
