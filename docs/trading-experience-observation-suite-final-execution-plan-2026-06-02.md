# A 股交易经验观察与复盘套件最终开发计划

- 状态：最终执行计划 / 待实施
- 生成日期：2026-06-02
- 适用项目：维斯量化交易平台 / `tquant-trading-platform`
- 计划定位：把 16 篇交易经验沉淀为观察、复盘、风险标签、持仓纪律与效果归因能力
- 权威边界：本文是本轮“交易经验观察与复盘套件”的实施依据；若与早期草案冲突，以本文为准

## 1. 依据文档

本计划整合以下文档，不再单独新建选股引擎：

1. `AGENTS.md`
2. `docs/engineering-conventions.md`
3. `docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md`
4. `docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md`
5. `docs/a-share-strong-stock-trading-requirements-2026-06-02.md`
6. `docs/next-day-mainline-watchlist-execution-plan-2026-06-02.md`
7. `docs/a-share-key-level-engine-execution-plan-2026-06-02.md`
8. `docs/trading-experience-observation-suite-requirements-2026-06-02.md`

## 2. 总结论

当前平台已经在选股、主线、前排、关键位、策略跟踪、模拟盘和 24M 回测上有基础能力。

本轮不再追加一套新的强势股生产策略，也不把文章经验直接写入 `production_score`。

本轮真正要补的是五类能力：

1. 每日复盘闭环。
2. 用户交易纪律日志。
3. 量价-位置风险标签。
4. 相对强度 / 抗跌观察。
5. 持仓纪律与做 T 效果归因。

其中涨停后形态和做 T 规则必须先证伪、再采信，只能进入研究/观察层。

## 3. 硬边界

以下边界在所有阶段必须成立：

1. 只做观察、复盘、解释、纪律提示和研究归因。
2. 默认 feature flag 关闭。
3. 不替换 low-buy、priority board、front-row weighted 或任何现有生产排序。
4. 不产生 `production_score`。
5. 不修改 `strategy_policy`。
6. 不输出“买入、卖出、加仓、低吸、必涨、稳赚、推荐”等交易指令。
7. “主力出货、洗盘、吸筹、对倒”一律翻译为可观测的价量标签，不当作事实。
8. 所有判断只用信号日及之前可见数据；后验数据只用于复盘、归因和报告。
9. 缺数据必须输出 `insufficient`、`no_data`、`blocked`、`stale` 或 `research_only`，禁止空分、假分和 TODO 占位。
10. 重计算必须走 runtime/backtest/analytics worker，Web 不新增后台 loop。
11. 前端新大表走 `DataTable`，长卡片列表走 `VirtualCardList`；状态管理遵循现有 state-separation guard，不新增复杂本地状态。
12. 所有入口关闭 flag 后必须回到既有行为，不影响监控、策略跟踪、模拟盘、回测和生产排序。

## 4. 与现有计划的合并关系

### 4.1 补充 `a-share-strong-stock`

原文档已覆盖买点、卖点、做 T、复盘大框架。

本计划补充：

1. 把复盘从“需求描述”升级为可物化的 `review_pool_item` 和 `trade_journal_entry`。
2. 把风险识别从散落文案升级为统一 `vp_position_tag` 标签状态机。
3. 把“涨停后洗盘买点”降级为 `research_only` 形态跟踪器，必须过回测门。
4. 把“做 T 规则”从提示器升级为效果归因器，先回答“做 T 是否真的有效”。

### 4.2 补充 `next-day-mainline-watchlist`

原文档负责生成明日观察池。

本计划补充：

1. 观察池快照进入每日复盘闭环。
2. 次日剔除、三日留存和触发/失效结果必须落入复盘表。
3. `watch_score` 继续只用于观察排序，不进入生产收益排行。
4. 观察池报告必须和真实组合收益分开展示。

### 4.3 补充 `AKeyLevel Engine`

原文档负责支撑、压力、关键位和失效条件。

本计划补充：

1. 持仓纪律助手复用 AKeyLevel 的支撑/压力/破位，不重算第二套关键位。
2. 量价风险标签复用 AKeyLevel 的位置分位、支撑压力、失效条件。
3. `break_down` 与 `emotional_pullback` 必须由 AKeyLevel 客观规则支持。

## 5. 当前项目事实基线

已有能力：

1. `backend/app/services/low_buy/`：低吸、前排、生产分、优先榜相关能力。
2. `backend/app/services/key_levels/`：AKeyLevel 关键位引擎、物化、缓存和 API。
3. `backend/app/services/strategy_tracking*.py`：策略跟踪、快照、复盘、表现、详情。
4. `backend/app/services/paper/`：模拟盘账户、订单、持仓、动态退出、smart T、绩效。
5. `backend/app/workers/runtime_worker.py`：已有 runtime task 消费链。
6. `frontend/src/features/strategy-tracking/`：策略跟踪页面和复盘面板基础。
7. `frontend/src/features/paper/`：模拟盘页面和持仓详情基础。
8. `frontend/src/features/key-levels/`：关键位展示面板。
9. `frontend/src/ui/table/DataTable.tsx` 和 `frontend/src/ui/list/VirtualCardList.tsx`：大表/长列表规范入口。

本轮新增必须复用这些入口，不允许并行重建。

## 6. Feature Flags

后端配置新增字段，环境变量使用大写：

| 配置字段 | 环境变量 | 默认值 | 说明 |
|---|---|---:|---|
| `trading_experience_suite_enabled` | `TRADING_EXPERIENCE_SUITE_ENABLED` | false | 总开关 |
| `trade_review_suite_enabled` | `TRADE_REVIEW_SUITE_ENABLED` | false | 每日复盘与交易日志 |
| `vp_position_tags_enabled` | `VP_POSITION_TAGS_ENABLED` | false | 量价-位置标签 |
| `relative_strength_board_enabled` | `RELATIVE_STRENGTH_BOARD_ENABLED` | false | 相对强度/抗跌榜 |
| `holding_discipline_assistant_enabled` | `HOLDING_DISCIPLINE_ASSISTANT_ENABLED` | false | 持仓纪律助手 |
| `limit_up_followthrough_enabled` | `LIMIT_UP_FOLLOWTHROUGH_ENABLED` | false | 涨停后形态研究 |
| `t_trade_discipline_enabled` | `T_TRADE_DISCIPLINE_ENABLED` | false | 做 T 纪律与归因 |

禁止新增“生产排序开关”。若未来要进入生产排序，必须另写策略准入文档并走 `strategy_policy` 门禁。

## 7. 后端落地结构

新增服务目录：

```text
backend/app/services/trading_experience/
```

建议文件：

| 文件 | 职责 |
|---|---|
| `config.py` | 阈值、flag、默认参数 |
| `schemas.py` | 内部 schema 与输出 schema |
| `repository.py` | 读取日线、板块、指数、paper、AKeyLevel、观察池快照 |
| `review_pool.py` | 每日强势池、次日剔除、三日留存 |
| `trade_journal.py` | 用户交易纪律日志 |
| `volume_position_tags.py` | 量价-位置标签状态机 |
| `relative_strength.py` | RS / 抗跌榜计算 |
| `holding_discipline.py` | 持仓纪律提示 |
| `limit_up_followthrough.py` | 涨停后形态分类 |
| `t_trade_attribution.py` | 做 T 效果归因 |
| `service.py` | 统一编排与 readiness |

新增 API 路由：

```text
backend/app/api/routes/trading_experience.py
```

建议接口：

| API | 用途 | 默认状态 |
|---|---|---|
| `GET /api/trading-experience/readiness` | 数据和开关状态 | 可读 |
| `GET /api/trading-experience/review-pool` | 每日复盘池 | flag 控制 |
| `GET /api/trading-experience/trade-journal` | 查询交易日志 | flag 控制 |
| `POST /api/trading-experience/trade-journal` | 新增/更新交易日志 | flag 控制 |
| `GET /api/trading-experience/volume-position-tags/{symbol}` | 单票风险标签 | flag 控制 |
| `GET /api/trading-experience/relative-strength` | 抗跌榜 | flag 控制 |
| `GET /api/trading-experience/holding-discipline` | 持仓纪律提示 | flag 控制 |
| `GET /api/trading-experience/limit-up-followthrough` | 涨停后研究列表 | flag 控制 |
| `GET /api/trading-experience/t-trade-attribution` | 做 T 归因 | flag 控制 |

所有 response 必须带：

```text
data_quality
as_of
engine_version
source
research_only
```

## 8. 数据模型

### 8.1 `review_pool_item`

用于每日复盘池。

字段：

```text
pool_date
symbol
name
status: in_pool | retained | dropped
entry_pct
volume_ratio
mainline_state
sector_role
drop_reason
tracked_days
evidence[]
data_quality
as_of
engine_version
```

### 8.2 `trade_journal_entry`

用于用户交易纪律日志。

字段：

```text
entry_id
user_id
account_id
symbol
action: buy | sell | trim | add | t_trade | note
reason_text
signal_source
discipline_flags
mistake_tags[]
created_at
updated_at
```

`discipline_flags` 至少包含：

```text
trend_follow
stop_loss_set
no_add_down
no_chase_noliquidity
not_against_mainline
planned_position
```

### 8.3 `vp_position_tag`

用于量价-位置风险标签。

字段：

```text
symbol
trade_date
tag_code
level: info | warn
evidence[]
explanation
data_quality
as_of
engine_version
```

首批 `tag_code`：

1. `high_vol_distribution_risk`
2. `low_vol_grind_down_risk`
3. `healthy_pullback_observe`
4. `up_shrink_down_expand_risk`
5. `blowoff_overheat_risk`
6. `price_volume_divergence_risk`

### 8.4 `relative_strength_item`

用于抗跌榜。

字段：

```text
symbol
trade_date
index_code
sector_code
stock_pct
index_pct
sector_pct
rs_vs_index
rs_vs_sector
sector_rank
resilience_flag: resilient | follow_down | neutral
data_quality
as_of
```

### 8.5 `holding_discipline_hint`

用于持仓纪律助手。

字段：

```text
account_id
symbol
hint_code: trailing_stop | no_add_down_warning | break_down | emotional_pullback | watch_cadence
level: info | warn
evidence[]
data_quality
as_of
```

### 8.6 `limit_up_followthrough_item`

用于涨停后形态研究。

字段：

```text
symbol
limit_up_date
pattern_code
days_since
evidence[]
backtest_winrate
backtest_pf
sample_count
quarter_stability
status: research_only | observed
data_quality
as_of
```

首批 `pattern_code`：

1. `three_yin_floor`
2. `half_volume_signal`
3. `four_star_consolidation`
4. `probe_updown`
5. `volume_stall_warning`

### 8.7 `t_trade_attribution`

用于做 T 效果归因。

字段：

```text
account_id
symbol
period
t_trade_count
realized_cost_delta
win_rate
sell_fly_count
vs_no_t_trade_return_delta
minute_data_coverage
data_quality
as_of
```

## 9. Worker 任务

新增 runtime task 类型：

| task_type | 触发时机 | 产物 |
|---|---|---|
| `trading_experience_review_refresh` | 收盘后 | 复盘池、剔除、三日留存 |
| `trading_experience_tag_materialization` | 收盘后 | 量价-位置标签 |
| `trading_experience_relative_strength_refresh` | 大跌日或收盘后 | 抗跌榜 |
| `trading_experience_limit_up_backtest` | 手动/analytics worker | 24M 涨停形态报告 |
| `trading_experience_t_attribution_refresh` | 收盘后或手动 | 做 T 归因 |

运行要求：

1. 任务幂等。
2. 写入 `as_of`、`engine_version`、`data_quality`。
3. 失败时保留旧快照并标 `stale`。
4. Web 请求只读缓存或轻量聚合。

## 10. 前端落地

### 10.1 策略跟踪页

在 `frontend/src/features/strategy-tracking/` 新增：

| 组件 | 用途 |
|---|---|
| `TradeReviewPanel.tsx` | 每日复盘、次日剔除、三日留存 |
| `TradeJournalPanel.tsx` | 用户交易纪律日志 |
| `VolumePositionTagStrip.tsx` | 单票风险标签条 |
| `RelativeStrengthBoard.tsx` | 抗跌榜 |

接入方式：

1. 新增“复盘”页签，懒加载。
2. 复盘池和抗跌榜使用 `DataTable`。
3. 标签条可在详情 drawer 内折叠展示。
4. flag 关闭时入口隐藏。

### 10.2 模拟盘页

在 `frontend/src/features/paper/` 新增或增强：

| 组件 | 用途 |
|---|---|
| `HoldingDisciplinePanel.tsx` | 持仓纪律提示 |
| `TTradeAttributionPanel.tsx` | 做 T 效果归因 |
| `TradeJournalQuickEntry.tsx` | 快速记录交易理由 |

要求：

1. 不拦截真实交易。
2. 对 paper 加仓动作只提示纪律警告，不阻断。
3. 做 T 面板先展示归因结果，不鼓励操作。
4. 分钟数据不足时显示 `no_data`。

### 10.3 监控页 / 个股详情

在 `frontend/src/features/monitor/` 和 `frontend/src/features/key-levels/` 增强：

1. 单票展示 `VolumePositionTagStrip`。
2. 大跌日展示相对强度事实。
3. 标签文案只用“需警惕、观察、留意、数据不足”。

## 11. 分批实施计划

### G0：计划收口与守卫

目标：先锁定边界，防止实现跑偏。

任务：

1. 新增本计划到 `IMPLEMENTATION_PLAN.md` 当前开发入口。
2. 新增 feature flags 到后端 settings。
3. 新增 API/schema 草案，不实现生产逻辑。
4. 新增文案禁词守卫：禁止“买入、卖出、加仓、低吸、必涨、推荐、稳赚”。
5. 新增生产隔离守卫：所有 trading experience 输出不得设置 `production_score`。

验收：

1. flag 默认 false。
2. flag 关闭时无 UI 入口。
3. `production_score` 隔离测试通过。
4. 文案守卫测试通过。

### G1：每日复盘池 + 交易纪律日志

目标：先把用户最需要的复盘习惯闭环做出来。

任务：

1. 实现 `review_pool.py`。
2. 收盘后按涨幅阈值默认 8% 构建强势池。
3. 次日标记 `dropped` / `retained`。
4. 三日跟踪强势结构。
5. 实现 `trade_journal.py`，支持 paper 关联和手动记录。
6. 策略跟踪页新增“复盘”页签。

验收：

1. 可看到当日强势池。
2. 可看到次日剔除原因。
3. 可看到三日留存状态。
4. 可记录交易理由和纪律 flags。
5. 缺数据显示 `insufficient`。
6. 不产生任何买卖建议。

### G2：量价-位置风险标签 + 抗跌榜

目标：把文章里的“出货/洗盘/抗跌”转成可观察标签。

任务：

1. 实现 `volume_position_tags.py`。
2. 首批输出 6 类标签。
3. 标签 evidence 必须包含可计算条件。
4. 实现 `relative_strength.py`。
5. 大跌日输出 `rs_vs_index`、`rs_vs_sector` 和 `resilience_flag`。
6. 监控页和策略详情展示风险标签。

验收：

1. 每个标签有触发和不触发测试。
2. 标签不影响 priority board 和生产排序。
3. 抗跌榜不预测后续涨跌。
4. 缺指数/板块数据时标 `insufficient`。

### G3：持仓纪律助手

目标：让模拟盘持仓能提醒纪律，而不是只看盈亏。

任务：

1. 实现 `holding_discipline.py`。
2. 复用 AKeyLevel 的支撑/压力/破位。
3. 盈利超过阈值后输出移动防守位提示。
4. 持仓破位后，对加仓动作输出 `no_add_down_warning`。
5. 区分 `break_down` 与 `emotional_pullback`。
6. paper 持仓详情新增纪律面板。

验收：

1. 每个持仓可生成纪律状态。
2. 提示文案不含交易指令。
3. 破位判断不依赖未来数据。
4. flag 关闭后 paper 页面恢复既有行为。

### G4：涨停后量价跟踪研究门

目标：只研究，不采信；先判断形态是否经得起回测。

任务：

1. 实现 `limit_up_followthrough.py`。
2. 对近 5 日有涨停标的分类 3-5 日形态。
3. 接入 24M 回测任务。
4. 输出胜率、PF、最大回撤、样本量、季度稳定性。
5. 未达标统一 `research_only`。

验收：

1. 形态分类可复现。
2. 回测报告不只看收益率。
3. 未达标不进入观察排序、生产排序或 `production_score`。
4. UI 明确标注“研究态，需验证”。

### G5：做 T 纪律与效果归因

目标：先回答“做 T 是否真的降低成本”，不做做 T 推荐器。

前置条件：

1. 分钟/盘中数据覆盖率通过检查。
2. paper 成交记录足够完整。
3. AKeyLevel 可提供破位状态。

任务：

1. 实现 `t_trade_attribution.py`。
2. 基于 paper 真实成交计算做 T 次数、成本变化、胜率。
3. 估算 `vs_no_t_trade_return_delta`。
4. 统计 `sell_fly_count`。
5. 分钟数据不足时降级为 `no_data`。
6. paper 页面新增做 T 归因面板。

验收：

1. 归因结果允许为负，并如实展示。
2. 不输出“应该做 T”。
3. 数据不足明确显示。
4. 不影响 paper 订单撮合、风控和持仓账本。

### G6：统一验收、报告和回退

目标：形成可部署、可回退、可审查的完整闭环。

任务：

1. 所有 API 更新 OpenAPI 和 generated types。
2. 前端通过 `api:check`、lint、test、build、analyze。
3. 后端通过相关 pytest。
4. 生成 Markdown 验收报告。
5. 记录 flag 关闭回退步骤。

验收：

1. 关闭全部 flags，核心页面行为不变。
2. 打开 M1/M2 flags，策略跟踪和监控页可展示观察数据。
3. 打开 M3 flag，paper 页面可展示纪律提示。
4. 打开 M4/M5 flags，仅研究页/归因页展示，不进入生产排序。

## 12. 测试计划

后端测试：

1. `backend/tests/test_trading_experience_review_pool.py`
2. `backend/tests/test_trading_experience_trade_journal.py`
3. `backend/tests/test_trading_experience_volume_position_tags.py`
4. `backend/tests/test_trading_experience_relative_strength.py`
5. `backend/tests/test_trading_experience_holding_discipline.py`
6. `backend/tests/test_trading_experience_limit_up_followthrough.py`
7. `backend/tests/test_trading_experience_t_trade_attribution.py`
8. `backend/tests/test_trading_experience_guards.py`

前端测试：

1. `frontend/src/features/strategy-tracking/TradeReviewPanel.test.tsx`
2. `frontend/src/features/strategy-tracking/TradeJournalPanel.test.tsx`
3. `frontend/src/features/strategy-tracking/VolumePositionTagStrip.test.tsx`
4. `frontend/src/features/strategy-tracking/RelativeStrengthBoard.test.tsx`
5. `frontend/src/features/paper/HoldingDisciplinePanel.test.tsx`
6. `frontend/src/features/paper/TTradeAttributionPanel.test.tsx`

必须覆盖：

1. flag-off 隐藏。
2. 空数据、缺数据、stale、blocked。
3. 禁词文案。
4. 不产生 `production_score`。
5. 不修改现有排序。
6. 375px 移动端无横向溢出。

## 13. 验收命令

后端：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_trading_experience_review_pool.py \
  backend/tests/test_trading_experience_trade_journal.py \
  backend/tests/test_trading_experience_volume_position_tags.py \
  backend/tests/test_trading_experience_relative_strength.py \
  backend/tests/test_trading_experience_holding_discipline.py \
  backend/tests/test_trading_experience_limit_up_followthrough.py \
  backend/tests/test_trading_experience_t_trade_attribution.py \
  backend/tests/test_trading_experience_guards.py
```

前端：

```bash
cd frontend
npm run api:check
npm run lint
npm test -- --run
npm run build
npm run analyze
```

通用：

```bash
git diff --check
```

## 14. 不做清单

1. 不做新的强势股生产排序。
2. 不做实盘自动下单。
3. 不做喊单、荐股、收益承诺。
4. 不把文章经验直接接入 `production_score`。
5. 不把 `watch_score` 当作生产分。
6. 不做“主力事实判定器”。
7. 不做做 T 推荐器。
8. 不否定或删除基本面排雷能力。
9. 不新增 Web 后台 loop。
10. 不用后验涨跌反推当日标签。

## 15. 最终交付物

每批交付必须包含：

1. 后端服务、schema、route、worker 或明确说明该批不需要 worker。
2. 前端面板、状态、空态、错误态和 flag-off 隐藏。
3. OpenAPI / generated types 同步。
4. 单元测试和必要的前端测试。
5. 验收报告，说明未进入生产排序。
6. 回退说明。

最终完成后，平台应形成以下用户闭环：

```text
收盘生成强势观察池
→ 次日记录剔除和留存
→ 盘中/收盘查看量价风险标签和抗跌事实
→ 持仓页查看纪律提示
→ 用户记录实际操作和是否守纪律
→ 周期性复盘纪律达成率与做 T 归因
→ 未验证规则永远停留在 research_only
```

## 16. 直接实施结论

推荐按以下顺序启动：

1. G0 + G1 作为第一批，优先做复盘池和交易日志。
2. G2 作为第二批，补量价标签和抗跌榜。
3. G3 作为第三批，接入 paper 持仓纪律。
4. G4/G5 作为研究批，必须先跑回测和数据覆盖检查。
5. 每批通过测试和验收后再进入下一批。
