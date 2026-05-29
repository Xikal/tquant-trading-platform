# TQuant 平台瘦身与策略跟踪功能开发文档

## 1. 开发目标

请在 `/Users/j/Documents/gupiao` 项目中，完成平台前端瘦身和新增“策略跟踪”功能。

目标包括：

1. 删除前端“策略工作台”整个功能及对应前端代码，不影响后端策略能力、回测、选股宝典、模拟盘和设置页。
2. 删除前端“市场情绪”独立页签及对应前端代码，但实时监控界面的市场情绪、市场宽度、龙头强度、data_quality、pulse 等相关信息必须保留。
3. 新增“策略跟踪”功能页，展示已有生产策略选出的可买入、接近买点、观察确认股票，从首次推荐日起到信号结束期间的涨幅、回撤、买点触达、止损触发、生命周期状态、策略表现统计和单票详情。
4. 新页面优先复用现有组件、类型、格式化函数、API 封装和样式体系，前端展示要紧凑、高密度、性能友好。

## 2. 删除策略工作台

### 2.1 删除范围

需要删除或改造：

- 顶部导航中的“策略工作台”。
- `/strategy` 页面入口。
- `StrategyRoute`。
- `frontend/src/features/strategy/` 下只服务策略工作台页面的组件、store 和测试。
- 策略工作台 UI 独占相关的懒加载、路由测试、页面测试。

### 2.2 保留范围

必须保留：

- 后端策略元数据。
- 策略注册表。
- 生产策略分层。
- 回测页策略选择。
- 选股宝典策略候选。
- 模拟盘 `strategy_key`。
- 设置页策略治理能力。
- ETF T0、SmartT、动态止盈止损等底层能力。

### 2.3 路由要求

- `/strategy` 不再渲染策略工作台。
- `/strategy` 应重定向到 `/backtest`。

## 3. 删除市场情绪独立页

### 3.1 删除范围

需要删除或改造：

- 顶部导航中的“市场情绪”。
- `/emotion` 页面入口。
- `EmotionRoute`。
- `frontend/src/features/market-emotion/` 中只服务独立情绪页的页面代码。
- 市场情绪页独占测试。

### 3.2 保留范围

必须保留：

- 实时监控页中使用的市场情绪、市场宽度、龙头强度、data_quality、pulse 展示。
- 后端市场情绪 API。
- 市场情绪类型定义。
- 复盘、盘中 pulse、监控相关市场状态数据。

### 3.3 路由要求

- `/emotion` 不再渲染市场情绪独立页。
- `/emotion` 应重定向到 `/monitor`。

## 4. 新增策略跟踪页

### 4.1 页面定位

新增页面：

- 页面名称：`策略跟踪`
- 路由：`/strategy-tracking`
- 导航位置：建议放在“选股宝典”和“回测页”之间。

页面用于展示生产策略推荐股票从首次推荐日起到当前或结束日之间的真实走势表现，帮助判断：

- 推荐后有没有涨。
- 是否真正给到买点。
- 最大涨幅是多少。
- 最大回撤是多少。
- 是否跌破止损。
- 当前信号是否仍有效。
- 哪些策略近期推荐质量更高。

### 4.2 跟踪对象

只纳入生产策略推荐结果：

- `tier = core`
- `tier = auxiliary`
- `visibility = full`
- `enabled = true`

只纳入以下信号状态：

- `buy_now`
- `soft_buy_now`
- `near_entry`

可选纳入但必须单独标记：

- `observe_confirmed`

不纳入：

- `hidden`
- `research`
- `factor_only`
- `watch-only`
- 未启用策略
- 纯模型解释信号

### 4.3 生命周期起点

一只股票在某个生产策略下首次出现以下状态时，进入跟踪池：

- 可买入
- 小仓试买
- 接近买点
- 观察确认

需要记录：

- 首次推荐日期
- 首次推荐策略
- 首次推荐状态
- 首次推荐价
- 买点区间
- 止损价
- 推荐原因
- 风险提示
- 当日市场状态
- 当日板块强度
- data_quality

### 4.4 生命周期结束条件

满足任一条件时结束跟踪：

- 连续 N 个交易日不再命中生产策略，默认 N=3。
- 收盘价跌破止损价。
- 达到止盈观察目标，例如推荐后最高涨幅达到 8%、10%、15%。
- 信号状态变为放弃或失效。
- 超过最大跟踪天数，默认 20 个交易日。
- 股票停牌或数据连续缺失超过阈值。

生命周期状态：

- `active`：仍在跟踪
- `completed_profit`：达到止盈观察
- `stopped`：跌破止损
- `expired`：超过跟踪周期
- `invalidated`：策略失效
- `data_unavailable`：数据不足

## 5. 策略跟踪页功能

### 5.1 总览指标

顶部高密度展示：

- 当前跟踪股票数
- 今日新增推荐
- 仍在买点区数量
- 推荐后平均涨幅
- 推荐后最高涨幅中位数
- 跌破止损数量

支持时间范围：

- 今日
- 近 7 日
- 近 30 日
- 近 60 日
- 自定义

支持筛选：

- 策略族
- 策略名称
- 信号状态
- 生命周期状态
- 是否触达买点
- 是否跌破止损
- data_quality 状态

### 5.2 今日有效机会

展示当前仍有效的生产策略机会。

字段：

- 股票
- 策略
- 当前状态
- 买点区间
- 当前价
- 距买点
- 止损价
- 推荐天数
- 当前结论

结论示例：

- 仍在买点区
- 已高于买点，不追高
- 回踩未破位
- 已跌破止损
- 等待确认
- 信号失效

### 5.3 推荐后涨幅榜

展示从首次推荐日至当前的表现。

字段：

- 股票
- 策略
- 首次推荐日
- 推荐价
- 当前价
- 当前涨幅
- 推荐后最高价
- 推荐后最高涨幅
- 最大回撤
- 跟踪状态

排序：

- 默认按推荐后最高涨幅降序。
- 可切换为当前涨幅、最大回撤、跟踪天数。

### 5.4 推荐后风险榜

展示推荐后表现不佳或风险扩大的股票。

字段：

- 股票
- 策略
- 首次推荐日
- 当前跌幅
- 最大回撤
- 是否跌破止损
- 跌破日期
- 失败原因
- 当前处理建议

失败原因包括：

- 推荐后未触达买点直接下跌
- 放量破位
- 板块退潮
- 市场环境转弱
- 数据质量不足
- 追高风险过大

### 5.5 策略表现对比

按策略统计：

- 推荐次数
- 给到买点次数
- 买点触达率
- 3 日胜率
- 5 日胜率
- 10 日胜率
- 平均收益
- 平均最大涨幅
- 平均最大回撤
- 盈亏比
- 止损触发率
- 当前有效数量

展示方式：

- 紧凑表格为主。
- 可选小型柱状图或迷你趋势图。
- 不使用大面积卡片堆叠。

### 5.6 单票详情

点击股票后进入抽屉或详情弹窗，不建议跳独立页。

详情内容：

- 迷你 K 线或走势线。
- 首次推荐日标记。
- 买点区间标记。
- 止损线标记。
- 最高点标记。
- 失效日标记。
- 每日状态时间轴。
- 推荐理由。
- 风险提示。
- 策略解释。
- 当前复盘结论。

### 5.7 一键复盘

支持按日期复盘：

- 某天推荐的股票现在怎么样。
- 最近 30 天推荐股票整体表现。
- 哪些策略推荐后最容易冲高回落。
- 哪些策略推荐后经常不给买点。
- 哪些策略买点后胜率更高。

输出内容：

- 总体表现摘要。
- 表现最好的策略。
- 表现最差的策略。
- 最大问题类型。
- 下阶段建议关注的策略。

### 5.8 策略复盘中心（新增优先方向）

在 `/strategy-tracking` 中新增“复盘中心”能力，用于按多维度查看策略推荐后的真实表现。

统计维度：

- 策略：`strategy_key`、`strategy_name`、`strategy_family`
- 股票：`symbol`、`name`
- 推荐日期：`first_signal_date`、`latest_signal_date`
- 信号类型：`buy_now`、`soft_buy_now`、`near_entry`、`observe_confirmed`
- 生命周期：`active`、`completed_profit`、`stopped`、`expired`、`invalidated`、`data_unavailable`
- 市场状态：强势、震荡、弱势
- 板块状态：板块主升、板块退潮、板块轮动、无明显板块
- 数据质量：`ok`、`partial`、`unavailable`

核心问题必须能直接回答：

- 推荐后是否触发买点。
- 触发买点用了几个交易日。
- 推荐后最高涨幅是多少。
- 推荐后最大回撤是多少。
- 是否触发止损。
- 是否出现冲高回落。
- 当前信号是否仍有效。
- 该策略近期推荐质量是否稳定。

页面要求：

- 支持按日期范围、策略、信号、市场状态、板块状态、生命周期筛选。
- 支持按最高涨幅、当前收益、最大回撤、买点触达时间、止损触发排序。
- 列表只展示聚合后的必要字段，不返回完整 `payload_json`。
- 复盘中心属于只读统计，不改变策略排序、生产候选、模拟盘或真实交易。

### 5.9 失败归因（新增优先方向）

每条策略跟踪结果必须生成一个或多个失败/风险标签，方便定位“为什么没买入信号”“为什么收益夸张”“为什么策略表现不稳定”。

失败归因标签：

- `no_entry_touch`：未触达买点。
- `fast_support_break`：买入后快速跌破支撑。
- `spike_without_take_profit`：冲高未止盈。
- `sector_retreat`：板块退潮。
- `market_mismatch`：大盘环境不匹配。
- `data_insufficient`：数据不足。
- `abnormal_return`：异常收益，需要复核。
- `entry_chase_risk`：推荐时已明显高于买点，追高风险大。
- `stop_loss_triggered`：跌破止损。
- `signal_invalidated`：策略信号失效。

归因规则要求：

- 支持多标签，不要只保留一个失败原因。
- 标签必须基于可解释字段生成，例如买点区、支撑位、止损位、板块状态、市场状态、行情数据完整性、后验走势。
- `abnormal_return` 必须触发数据准确性提示，要求展示行情来源、数据截止时间和收益计算起点。
- 标签生成逻辑放在后端 service/helper 中，前端只展示，不做核心归因计算。
- 归因逻辑必须有单元测试，覆盖无买点、跌破支撑、冲高回落、数据缺失、异常收益。

### 5.10 市场状态分层（新增优先方向）

策略表现不能只看总收益率，必须按市场环境分层统计。

市场状态分层：

- `strong_market`：强势行情。
- `range_market`：震荡行情。
- `weak_market`：弱势行情。

板块状态分层：

- `sector_main_rise`：板块主升。
- `sector_rotation`：板块轮动。
- `sector_retreat`：板块退潮。
- `sector_unknown`：板块状态不足。

统计要求：

- 每个策略在不同市场状态下分别统计推荐次数、买点触达率、胜率、平均最大涨幅、平均最大回撤、止损率、收益/回撤比。
- 页面要能回答：某个策略到底适合强势行情、震荡行情还是弱势行情。
- 市场状态来自推荐当日或信号生成时刻的可见数据，不允许使用推荐后的市场表现反推当时状态。
- 市场状态缺失时必须标记为 `unknown`，不能默认当作中性或强势。

### 5.11 单票跟踪详情增强（新增优先方向）

单票详情需要从“看走势”升级为“看完整交易计划和执行复盘”。

必须展示：

- 推荐日。
- 信号生成时间。
- 使用的数据截止时间。
- 推荐价。
- 支撑位。
- 计划买点区间。
- 止损位。
- 目标位。
- 实际最高点。
- 实际最低点。
- 信号失效时间。
- 买点触达日期。
- 止损触发日期。
- 目标触达日期。
- 冲高回落幅度。
- 当前复盘结论。

详情图表标记：

- 首次推荐。
- 买点区。
- 支撑位。
- 止损线。
- 目标线。
- 推荐后最高点。
- 推荐后最低点。
- 最优持有退出点。
- 信号失效点。

详情结论必须区分：

- 盈利来自短线冲高止盈。
- 盈利来自趋势延续。
- 推荐后未给买点。
- 给买点后跌破支撑。
- 数据不足，暂不能判断。

### 5.12 策略健康度评分（新增优先方向）

给每个策略生成只读健康度评分，用于观察策略近期质量，不进入生产放行，不自动影响排序。

评分维度：

- 样本数是否足够。
- 买点触达率。
- 止损率。
- 平均最大涨幅。
- 平均最大回撤。
- 盈亏比。
- 收益/回撤比。
- 冲高回落比例。
- 数据质量完整度。
- 市场状态适配稳定性。

评分输出：

- `health_score`：0-100。
- `health_grade`：`A`、`B`、`C`、`D`、`insufficient_sample`。
- `sample_quality`：`enough`、`thin`、`insufficient`。
- `health_reasons`：评分原因。
- `health_risks`：主要风险。

硬性要求：

- 样本数不足时不能给高评分，必须显示 `insufficient_sample`。
- 分数只用于复盘观察，不得进入生产策略启停、排序、自动交易。
- 策略健康度必须按时间范围计算，不允许混用不同窗口导致结论漂移。

### 5.13 Shadow 观测闭环（新增优先方向）

新增 Shadow 观测闭环模块，用于定位为什么线上 Shadow 样本为 0，或为什么某个模型没有进入观测。

必须展示：

- 每个模型是否写入 Shadow 观测表。
- 最近一次观测时间。
- 最近一次观测样本数。
- 最近一次有效信号数。
- 最近一次被过滤数量。
- 观测表总样本数。
- 与策略跟踪结果的关联数量。

无样本原因枚举：

- `no_model_observation`：没有模型观测记录。
- `no_qualified_signal`：没有符合条件信号。
- `data_missing`：数据缺失。
- `strategy_disabled`：策略未启用。
- `window_not_reached`：时间窗口未到。
- `shadow_job_not_run`：Shadow 任务未运行。
- `write_failed`：观测写入失败。
- `schema_mismatch`：观测字段或模型版本不匹配。

要求：

- Shadow 为 0 时页面必须显示原因，而不是只显示数字 0。
- 后端要提供诊断字段，前端不猜测原因。
- 不允许为了补样本伪造观测记录；只能展示真实写入状态和阻塞原因。

### 5.14 防未来函数审计面板（新增优先方向）

新增防未来函数审计面板，每条跟踪记录都必须能看到收益和信号计算边界。

每条记录展示：

- 信号生成时间。
- 推荐日期。
- 使用的数据截止时间。
- 回看窗口起点。
- 回看窗口终点。
- 后验收益计算起点。
- 后验收益计算终点。
- 行情数据来源。
- 行情数据更新时间。
- 是否存在后验字段参与信号。
- 是否异常收益需要复核。

审计规则：

- 推荐当日信号只能使用推荐当日及以前数据。
- 后验收益必须从首次推荐日之后开始计算。
- 推荐日当天的最高价、最低价不能用于决定推荐日之前的信号。
- 异常收益样本必须标记 `needs_review`，例如单票短期收益过高、价格跳变异常、复权或数据源异常。
- 审计结果必须在 API 中返回，不只写日志。

异常收益复核触发建议：

- 单日涨跌幅超过 A 股正常涨跌停规则且无特殊标记。
- 推荐后 1-5 日最大涨幅异常高。
- 最大回撤为正或不符合计算逻辑。
- 当前价、最高价、最低价关系异常。
- 数据源 `data_quality` 为 `partial` 或 `unavailable`。

### 5.15 每日/每周策略跟踪报告（新增优先方向）

新增自动报告能力，先支持后台生成 Markdown/JSON，再考虑接入飞书或后台消息。

日报内容：

- 今日新增信号。
- 今日触发买点信号。
- 今日跌破止损样本。
- 今日冲高回落样本。
- 今日异常收益样本。
- 今日数据不足样本。
- Shadow 样本变化。
- 需要人工复核的记录。

周报内容：

- 本周策略表现排行。
- 本周策略风险排行。
- 本周买点触达率。
- 本周止损率。
- 本周冲高回落比例。
- 本周不同市场状态下的策略表现。
- 本周 Shadow 观测闭环状态。
- 下周建议重点观察策略。

输出要求：

- 报告必须包含生成时间、统计窗口、数据截止时间和 data_quality。
- 报告只做观察，不给自动买卖指令。
- 报告生成失败不能影响策略主流程。

### 5.16 持有期优化与短线转中长线（新增优先方向）

在每个推荐票维度增加持有期统计，判断“短线冲高止盈”还是“可延长为波段/中长线观察”。

统计字段：

- 最优持有天数。
- 最优退出日期。
- 最优退出收益。
- 最优退出前承受的最大回撤。
- 收益/回撤比。
- 峰值利润回吐比例。
- 短线、波段、趋势、中长线持有桶。
- 是否适合短线转中长线观察。

风控要求：

- 短线转中长线必须有利润垫。
- 持有期最大回撤不能明显扩大。
- 不得跌破原始止损或关键支撑。
- 趋势判断只能使用当日以前可见数据。
- 最优持有天数属于后验复盘指标，不能用于反推推荐当日信号。

该能力的详细执行计划见：

- `/Users/j/Documents/gupiao/docs/superpowers/plans/2026-05-29-strategy-tracking-holding-optimizer.md`

## 6. 数据设计

### 6.1 推荐快照

建议新增表或复用现有低吸结果表扩展生成视图：

`strategy_tracking_signals`

字段建议：

- `id`
- `symbol`
- `name`
- `strategy_key`
- `strategy_name`
- `strategy_family`
- `signal_state`
- `signal_text`
- `first_signal_date`
- `signal_trade_date`
- `signal_price`
- `entry_zone_low`
- `entry_zone_high`
- `stop_loss`
- `target_price`
- `reasons_json`
- `risk_flags_json`
- `market_state`
- `sector_strength`
- `data_quality`
- `payload_json`
- `created_at`

### 6.2 跟踪快照

建议新增：

`strategy_tracking_daily_snapshots`

字段建议：

- `id`
- `tracking_id`
- `symbol`
- `strategy_key`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `pct_chg`
- `volume`
- `amount`
- `current_return_pct`
- `max_return_pct`
- `max_drawdown_pct`
- `hit_entry_zone`
- `hit_stop_loss`
- `hit_target`
- `lifecycle_status`
- `review_text`
- `data_quality`
- `created_at`

增强字段建议：

- `support_price`
- `actual_high_price`
- `actual_high_date`
- `actual_low_price`
- `actual_low_date`
- `invalidated_date`
- `spike_retrace_pct`
- `failure_tags_json`
- `failure_reason_text`
- `market_state`
- `market_state_text`
- `sector_state`
- `sector_state_text`
- `abnormal_return`
- `needs_review`
- `audit_flags_json`
- `signal_generated_at`
- `data_cutoff_at`
- `lookback_start_date`
- `lookback_end_date`
- `posterior_start_date`
- `posterior_end_date`
- `market_data_source`
- `market_data_updated_at`
- `best_holding_days`
- `best_exit_date`
- `best_exit_return_pct`
- `best_exit_drawdown_pct`
- `return_drawdown_ratio`
- `giveback_from_peak_pct`
- `holding_bucket`
- `hold_extension_state`
- `suggested_holding_plan`

### 6.3 聚合统计

后端应直接输出聚合，避免前端大规模计算：

- 总览指标
- 今日有效机会
- 涨幅榜
- 风险榜
- 策略表现统计
- 单票走势详情

新增聚合：

- 复盘中心多维统计。
- 失败归因统计。
- 市场状态分层统计。
- 策略健康度评分。
- Shadow 观测闭环诊断。
- 防未来函数审计摘要。
- 日报/周报摘要。

### 6.4 失败归因结构

建议后端统一输出：

```json
{
  "failure_tags": ["no_entry_touch", "sector_retreat"],
  "failure_reason_text": "推荐后未触达买点，且板块进入退潮状态",
  "needs_review": false,
  "review_priority": "normal"
}
```

字段要求：

- `failure_tags` 支持多个标签。
- `failure_reason_text` 面向用户展示。
- `needs_review` 用于异常收益、数据质量、未来函数疑点标记。
- `review_priority` 可选 `low`、`normal`、`high`、`critical`。

### 6.5 市场状态分层结构

建议聚合输出：

```json
{
  "strategy_key": "first_board",
  "market_state": "strong_market",
  "sector_state": "sector_main_rise",
  "recommendation_count": 12,
  "entry_touch_rate": 66.67,
  "win_rate_5d": 58.33,
  "avg_max_gain_pct": 7.2,
  "avg_max_drawdown_pct": -3.1,
  "stop_loss_rate": 8.33,
  "return_drawdown_ratio": 2.32
}
```

### 6.6 策略健康度结构

建议聚合输出：

```json
{
  "strategy_key": "first_board",
  "health_score": 78,
  "health_grade": "B",
  "sample_quality": "enough",
  "health_reasons": ["买点触达率稳定", "平均最大涨幅优于回撤"],
  "health_risks": ["弱势行情样本表现偏差"]
}
```

### 6.7 Shadow 观测闭环结构

建议输出：

```json
{
  "model_key": "main_force_model",
  "model_version": "v1",
  "observation_count": 0,
  "latest_observed_at": null,
  "linked_tracking_count": 0,
  "no_sample_reason": "no_model_observation",
  "no_sample_reason_text": "观测表里目前没有该模型观测记录"
}
```

### 6.8 防未来函数审计结构

建议每条记录输出：

```json
{
  "signal_generated_at": "2026-05-29T14:50:00+08:00",
  "data_cutoff_at": "2026-05-29T14:45:00+08:00",
  "lookback_start_date": "2026-04-29",
  "lookback_end_date": "2026-05-29",
  "posterior_start_date": "2026-05-30",
  "posterior_end_date": "2026-06-12",
  "future_leak_check": "passed",
  "audit_flags": [],
  "abnormal_return": false,
  "needs_review": false
}
```

## 7. API 设计

### 7.1 总览接口

`GET /api/strategy-tracking/summary`

参数：

- `range`
- `strategy_key`
- `strategy_family`
- `status`

返回：

- 当前跟踪数
- 今日新增
- 平均收益
- 最高涨幅中位数
- 止损数
- 数据质量状态

### 7.2 列表接口

`GET /api/strategy-tracking/items`

参数：

- `range`
- `status`
- `signal_state`
- `strategy_key`
- `strategy_family`
- `market_state`
- `sector_state`
- `failure_tag`
- `needs_review`
- `hit_entry`
- `stopped`
- `sort`
- `limit`
- `offset`

返回：

- 分页列表
- 当前表现
- 生命周期状态
- 买点触达状态
- 风险标签
- 失败归因标签
- 市场状态
- 板块状态
- 防未来函数审计摘要
- 持有期优化摘要

### 7.3 策略表现接口

`GET /api/strategy-tracking/performance`

参数：

- `range`
- `strategy_family`

返回：

- 每个策略的推荐次数、胜率、收益、回撤、止损率。

### 7.4 单票详情接口

`GET /api/strategy-tracking/items/{id}`

返回：

- 推荐快照
- 每日走势
- 标记点
- 时间轴
- 复盘结论
- 支撑位、计划买点、止损位、目标位
- 实际最高点、实际最低点、信号失效时间
- 失败归因
- 市场/板块状态上下文
- 防未来函数审计详情
- 持有期优化详情

### 7.5 生成或刷新接口

`POST /api/strategy-tracking/refresh`

用途：

- 管理员手动刷新。
- 后台任务调用。

约束：

- 只生成跟踪快照。
- 不改变策略结果。
- 不改变模拟盘账本。
- 不触发交易。

### 7.6 复盘中心接口

`GET /api/strategy-tracking/review`

参数：

- `range`
- `strategy_key`
- `strategy_family`
- `signal_state`
- `market_state`
- `sector_state`
- `failure_tag`
- `data_quality`

返回：

- 多维复盘统计。
- 买点触达分布。
- 冲高回落分布。
- 止损分布。
- 异常收益样本列表。
- 需要人工复核样本列表。

### 7.7 失败归因接口

`GET /api/strategy-tracking/failure-attribution`

参数：

- `range`
- `strategy_key`
- `market_state`
- `sector_state`

返回：

- 失败标签统计。
- 每类失败标签样本数。
- 每类失败标签平均收益、最大回撤、止损率。
- 高优先级复核样本。

### 7.8 市场状态分层接口

`GET /api/strategy-tracking/market-segments`

参数：

- `range`
- `strategy_key`
- `strategy_family`

返回：

- 按市场状态分层表现。
- 按板块状态分层表现。
- 策略在不同市场环境下的适配结论。

### 7.9 策略健康度接口

`GET /api/strategy-tracking/health`

参数：

- `range`
- `strategy_family`

返回：

- 每个策略健康度评分。
- 样本质量。
- 评分原因。
- 主要风险。
- 不足样本提示。

### 7.10 Shadow 观测闭环接口

`GET /api/strategy-tracking/shadow-observations`

参数：

- `range`
- `model_key`
- `strategy_key`

返回：

- 模型观测记录数。
- 最近观测时间。
- 关联策略跟踪样本数。
- 无样本原因。
- Shadow 任务状态。
- 写入失败或 schema mismatch 信息。

### 7.11 防未来函数审计接口

`GET /api/strategy-tracking/leakage-audit`

参数：

- `range`
- `strategy_key`
- `needs_review`
- `abnormal_return`

返回：

- 审计摘要。
- 通过数量。
- 需复核数量。
- 异常收益数量。
- 未来函数疑点数量。
- 逐条审计记录。

### 7.12 报告接口

`GET /api/strategy-tracking/reports/daily`

`GET /api/strategy-tracking/reports/weekly`

参数：

- `date`
- `week`
- `format=json|markdown`

返回：

- 日报或周报内容。
- 统计窗口。
- 数据截止时间。
- data_quality。
- Shadow 样本变化。
- 需复核样本。

## 8. 后台任务

新增或扩展后台任务：

`strategy_tracking_daily_refresh`

触发时间建议：

- 盘后 15:30
- 或行情数据更新完成后

任务内容：

1. 扫描当日生产策略推荐结果。
2. 对新推荐股票创建 tracking 记录。
3. 更新仍在跟踪股票的每日表现。
4. 判断生命周期状态。
5. 写入聚合统计缓存。

失败处理：

- 某只股票数据缺失不影响其他股票。
- data_quality 标记为 `partial` 或 `unavailable`。
- 失败原因写入日志和 metrics。

## 9. 性能要求

### 9.1 后端边界

必须把性能设计纳入实现，不允许做成“功能可用但大数据量卡顿”的页面。

后端按“Python 编排 + Go 读聚合 + Rust 数值计算”的边界设计：

- Python 负责策略跟踪生命周期生成、后台刷新、数据落库、业务规则编排和 fallback。
- Go 优先用于读多写少、高并发、批量聚合接口，包括策略跟踪 summary、items、performance、detail 的读取聚合、分页、缓存、partial response、Redis/MySQL fallback。
- Rust 优先用于纯数值计算，包括最大涨幅、最大回撤、rolling return、ATR、波动率、胜率、盈亏比等基础数组计算。
- Python wrapper 必须处理空数组、短数组、NaN、缺失值。

如果当前已有 Go/Rust 基础设施可复用，优先接入现有服务，不要重复造新服务。

如果某项 Go/Rust 改造会明显拉长开发周期，先保留 Python 实现，但必须预留清晰接口边界、metrics、日志和后续迁移点，不能写死。

### 9.2 API 性能要求

- 策略跟踪列表接口必须后端分页，默认 limit 不超过 50，不允许前端一次性拉全量再过滤。
- 聚合统计必须后端完成，前端只做展示，不承担大规模收益、回撤、胜率计算。
- 列表接口不要返回完整 `payload_json`，详情接口再按需返回。
- data_quality 为 `partial` 或 `unavailable` 时页面必须降级展示，不能白屏。
- 策略跟踪接口响应时间需要有日志或测试说明。

### 9.3 前端性能要求

- 单票走势、K 线、时间轴必须懒加载，只在打开详情抽屉时请求。
- 前端图表必须按需加载，避免首屏打包过大。
- 表格数据需要稳定 rowKey、分页、排序参数和请求去抖，避免筛选时重复请求。
- 大列表优先使用 antd Table 分页。
- 如单页超过 100 行，必须使用虚拟滚动或降低默认 page size。
- 页面状态应使用 React Query 或项目现有 query 模式缓存，避免重复请求同一数据。
- 避免大对象进入 React state。

性能验收必须包括：

1. 首屏不加载全量历史走势。
2. 列表默认分页。
3. 详情按需加载。
4. 前端 build chunk 无明显膨胀。
5. 策略跟踪接口响应时间有日志或测试说明。
6. Go/Rust 是否接入生产路径有明确说明。

## 10. 前端设计要求

### 10.1 复用优先

优先复用：

- `WorkspaceComponents`
- `workspaceFormatters`
- `workspaceDisplayStyles`
- `MiniKlineChart`
- `BacktestResearchShared`
- 现有表格、Tag、Metric、EmptyState、InfoPill
- 现有 query / API 封装模式

避免：

- 新建大体量页面专属样式。
- 重复实现格式化函数。
- 大量 inline style。
- 一次性渲染全部历史走势。

### 10.2 页面布局

推荐布局：

- 顶部：紧凑指标条
- 中部：筛选器 + 四个分区 tab
- 主体：表格为主
- 右侧或抽屉：单票详情

Tab 建议：

- 今日有效
- 涨幅榜
- 风险榜
- 策略表现

### 10.3 空状态

必须覆盖：

- 暂无推荐
- 暂无有效跟踪
- 数据不足
- 行情缺失
- 策略未启用
- 后端刷新中
- 接口失败

空状态文案要通俗：

- “今天还没有生产策略给出可跟踪买点。”
- “这只股票后续行情数据不足，暂时不能判断推荐后的表现。”
- “当前筛选条件下没有跌破止损的记录。”

## 11. 代码质量硬性要求

- 拒绝代码坏味道，不允许为了赶进度写临时补丁、重复逻辑、巨型组件、巨型函数、隐式副作用或难以测试的代码。
- 单个新增或大幅修改文件尽量控制在 500 行以内；如果超过，必须拆分为服务、schema、hook、组件、工具函数或测试文件。
- 不重复造轮子，优先复用项目已有组件、store、API client、格式化函数、表格、空状态、图表和样式 token。
- 不把业务逻辑堆在 React 组件里；数据转换、状态判断、生命周期计算应放到独立 helper/service，并补单元测试。
- 不写魔法数字和散落字符串；策略状态、生命周期状态、排序字段、data_quality 状态要集中定义。
- 不用大段 inline style 新造页面风格；优先复用现有紧凑布局和共享样式。
- 不吞异常；接口失败、数据缺失、partial response 必须可观测并在 UI 降级展示。
- 不引入无必要的新依赖，尤其是大体积图表库或状态库。
- 不做破坏性重构；只围绕本需求清理和新增。
- 不留下无用代码、死路由、未使用 import、重复测试 fixture 或注释掉的旧实现。
- TypeScript 和 Python 类型要尽量明确，避免 `any`、裸 `dict`、裸 `object` 扩散。
- 后端聚合逻辑要可测试、可回放，不能依赖前端做大规模计算。
- 所有删除都要经过引用检查，确保不是共享能力。

## 12. 删除代码范围建议

### 12.1 策略工作台前端候选删除

需要检查并删除：

- `frontend/src/app/router/StrategyRoute.tsx`
- `frontend/src/features/strategy/StrategyHubPage.tsx`
- `frontend/src/features/strategy/useStrategyHub.ts`
- `frontend/src/features/strategy/StrategyHub*.tsx`
- `frontend/src/features/strategy/StrategyQuickCheckPanel.tsx`
- `frontend/src/features/strategy/StrategyDoctorPanel.tsx`
- `frontend/src/features/strategy/StrategySignalReplayPanel.tsx`
- `frontend/src/stores/strategyHubStore.ts`
- `frontend/src/stores/strategySignalReplayStore.ts`

谨慎保留或迁移：

- ETF T0 状态面板如果仍被回测或模拟盘复用，迁移到 `features/backtest` 或 `features/paper`。
- 策略展示格式化函数如果被回测使用，迁移到共享目录。

### 12.2 市场情绪前端候选删除

需要检查并删除：

- `frontend/src/app/router/EmotionRoute.tsx`
- `frontend/src/features/market-emotion/MarketEmotionPage.tsx`
- `frontend/src/features/market-emotion/MarketEmotionDashboard.tsx`
- 独立情绪页专用组件和测试。

谨慎保留或迁移：

- `SectorLeaderStrengthTable` 如果实时监控复用，则迁移到 `frontend/src/features/monitor` 或 `workspace-shared`。
- 情绪格式化、类型定义如被监控使用，不删除。

### 12.3 路由与导航修改

需要修改：

- `frontend/src/app/router/webRouteDefinitions.tsx`
- `frontend/src/app/router/webRoutes.test.tsx`
- `frontend/src/features/trading-workspace/Topbar.tsx`
- `frontend/src/features/workspace-shared/workspaceConstants.ts`
- `frontend/src/features/workspace-shared/workspaceTypes.ts`
- `frontend/src/features/trading-workspace/useWorkspacePageProps.ts`
- `frontend/src/features/trading-workspace/WorkspacePageContent.tsx`

目标：

- 移除 `strategy` 和 `emotion` 页面枚举。
- 新增 `strategyTracking` 或 `strategy-tracking` 页面枚举。
- 保证 cold navigation 正常。

## 13. 测试计划

### 13.1 前端测试

必须覆盖：

- 顶部导航不再显示策略工作台和市场情绪。
- 顶部导航显示策略跟踪。
- `/strategy` 重定向到 `/backtest`。
- `/emotion` 重定向到 `/monitor`。
- `/strategy-tracking` 渲染策略跟踪页面。
- 策略跟踪空状态。
- 策略跟踪列表状态。
- 策略跟踪详情抽屉。
- 375 / 768 / 1440 宽度下无遮挡、无横向溢出。
- 分页、错误状态和性能友好行为。

### 13.2 后端测试

必须覆盖：

- 只纳入生产策略。
- 只纳入指定信号状态。
- 首次推荐日计算正确。
- 生命周期结束条件正确。
- 推荐后最大涨幅计算正确。
- 推荐后最大回撤计算正确。
- 买点触达判断正确。
- 止损触发判断正确。
- 单只股票数据缺失不影响其他记录。
- 后验统计不回写策略评分。
- 失败归因标签生成正确。
- 冲高未止盈识别正确。
- 板块退潮和市场环境不匹配识别正确。
- 异常收益样本被标记 `needs_review`。
- 市场状态分层统计不使用推荐日后的市场数据。
- 策略健康度样本不足时显示 `insufficient_sample`。
- Shadow 样本为 0 时返回明确 `no_sample_reason`。
- 防未来函数审计返回信号生成时间、数据截止时间、后验收益起点。
- 持有期优化中的最优持有天数只作为后验复盘指标。
- 短线转中长线判断只使用当日以前可见数据。
- 日报/周报生成失败不影响策略跟踪主接口。

### 13.3 Go 测试

如果接入或预留 Go 读聚合边界，至少覆盖：

- summary 聚合。
- items 分页。
- performance 聚合。
- detail partial response。
- Redis/MySQL fallback。
- 内部 token 校验。
- 超时和降级。

### 13.4 Rust 测试

如果接入或预留 Rust 数值计算边界，至少覆盖：

- 最大涨幅。
- 最大回撤。
- rolling return。
- 波动率。
- 胜率。
- 盈亏比。
- 空数组、短数组、NaN、缺失值。

### 13.5 集成测试

覆盖：

- 生产策略候选结果生成跟踪记录。
- 每日行情更新后刷新跟踪快照。
- 前端列表接口正常分页。
- 单票详情接口懒加载走势。
- data_quality 为 partial 时页面不白屏。
- 复盘中心按策略、股票、推荐日期、信号类型、市场状态筛选正常。
- 失败归因筛选和详情展示一致。
- 市场状态分层接口和页面统计一致。
- 策略健康度页面与 performance 统计口径一致。
- Shadow 观测闭环能解释 0 样本原因。
- 防未来函数审计面板能定位异常收益样本。
- 日报/周报能生成 Markdown 和 JSON。

## 14. 验收标准

### 14.1 删除验收

- 策略工作台页面已彻底不可见。
- 市场情绪独立页已彻底不可见。
- 对应前端页面代码已删除或迁移。
- 构建产物不再包含策略工作台页面 chunk。
- 构建产物不再包含市场情绪独立页 chunk。

### 14.2 保留功能验收

- 实时监控正常。
- 实时监控仍显示市场相关强弱信息。
- 选股宝典正常。
- 回测页正常。
- 模拟盘正常。
- 设置页正常。
- 登录和权限正常。

### 14.3 新页面验收

- 策略跟踪页可访问。
- 能看到生产策略推荐股票的跟踪结果。
- 能看到推荐后涨幅、当前涨幅、最大回撤。
- 能看到是否触达买点、是否跌破止损。
- 能看到策略表现统计。
- 能打开单票详情。
- 数据不足时有明确提示。
- 不影响策略排序和交易执行。
- 能按策略、股票、推荐日期、信号类型、市场状态做复盘统计。
- 能看到每条记录的失败归因标签。
- 能区分冲高止盈、冲高回落、趋势延续、未触达买点、跌破支撑。
- 能看到不同市场状态下各策略表现差异。
- 能看到策略健康度评分及样本不足提示。
- Shadow 样本为 0 时能看到明确原因。
- 能看到防未来函数审计字段和异常收益复核标记。
- 能生成每日/每周策略跟踪报告。
- 能看到每个推荐票的最优持有天数、收益/回撤比、是否可短线转中长线观察。

### 14.4 性能验收

- 首屏不一次性加载全部走势。
- 默认列表 limit 不超过 50。
- 单票详情按需加载。
- 页面切换无明显卡顿。
- 前端 build chunk 不因新页面明显膨胀。
- 策略跟踪接口响应时间有日志或测试说明。
- Go/Rust 是否接入生产路径有明确说明。

## 15. 推荐实施顺序

### 阶段一：删除入口与代码清理

1. 移除导航中的策略工作台、市场情绪。
2. `/strategy` 重定向 `/backtest`。
3. `/emotion` 重定向 `/monitor`。
4. 删除独立页面代码。
5. 修复路由和类型测试。

### 阶段二：后端跟踪能力

1. 定义 tracking schema。
2. 实现生产策略候选筛选。
3. 实现首次推荐快照。
4. 实现每日跟踪刷新。
5. 实现涨幅、回撤、买点、止损统计。
6. 增加 API。

### 阶段三：Go/Rust 性能边界

1. 评估现有 Go read service 是否可承接策略跟踪读聚合。
2. 若可承接，接入 summary/items/performance/detail 的读聚合、分页、缓存和 partial response。
3. 若短期不承接，保留 Python 实现但预留接口边界和 metrics。
4. 评估现有 Rust 数值计算能力是否可承接最大涨幅、最大回撤、rolling return、波动率等计算。
5. 若可承接，接入 Python wrapper 并补 parity 测试。
6. 若短期不承接，保留 Python fallback 但明确迁移边界。

### 阶段四：前端策略跟踪 MVP

1. 新增 `/strategy-tracking`。
2. 加入导航。
3. 实现总览指标。
4. 实现今日有效、涨幅榜、风险榜、策略表现四个 tab。
5. 接入分页接口。
6. 增加空状态和错误状态。

### 阶段五：单票详情与一键复盘

1. 实现详情抽屉。
2. 懒加载走势。
3. 标注推荐日、买点区、止损线、最高点。
4. 增加生命周期时间轴。
5. 增加日期复盘摘要。

### 阶段六：增强复盘与归因

1. 实现策略复盘中心。
2. 实现失败归因标签。
3. 实现市场状态分层统计。
4. 实现单票详情增强字段。
5. 实现冲高回落、异常收益、数据不足识别。

### 阶段七：策略质量与 Shadow 闭环

1. 实现策略健康度评分。
2. 实现 Shadow 观测闭环接口。
3. 实现 Shadow 为 0 的原因诊断。
4. 实现模型观测记录与策略跟踪样本关联。

### 阶段八：防未来函数审计与报告

1. 实现防未来函数审计字段。
2. 实现异常收益复核标记。
3. 实现持有期优化与短线转中长线观察。
4. 实现每日策略跟踪报告。
5. 实现每周策略跟踪报告。

### 阶段九：验证与上线

1. 前端 lint/test/build。
2. 后端 pytest。
3. Go test。
4. Rust test。
5. 路由 smoke。
6. 页面截图检查。
7. 线上部署后验证 `/monitor`、`/playbook`、`/strategy-tracking`、`/backtest`、`/paper`。

## 16. 明确不做

本轮不做：

- 不删除后端策略能力。
- 不删除回测能力。
- 不删除模拟盘策略字段。
- 不让策略跟踪结果自动影响排序。
- 不用策略跟踪结果自动买卖。
- 不把市场情绪数据从实时监控中移除。
- 不引入新的大体量图表库。
- 不进行无边界重构。

## 17. 最终输出要求

开发完成后必须输出：

1. 完成情况。
2. 修改过的关键文件。
3. 删除的前端页面代码范围。
4. 新增的策略跟踪能力。
5. Go 是否接入策略跟踪读聚合路径；如果未接入，说明原因和预留边界。
6. Rust 是否接入策略跟踪数值计算路径；如果未接入，说明原因和预留边界。
7. 前端性能优化点。
8. 新增/修改的测试。
9. 实际运行的验证命令和结果。
10. 是否发现并处理了代码坏味道。
11. 未完成项、原因和下一步。
12. 策略复盘中心、失败归因、市场状态分层、策略健康度、Shadow 闭环、防未来函数审计、日报周报、持有期优化分别完成到什么程度。

## 18. 可直接使用的开发提示词

```text
请在 `/Users/j/Documents/gupiao` 项目中，严格按照 `/Users/j/Documents/gupiao/docs/platform-slimming-and-strategy-tracking-development-plan-2026-05-29.md` 进行完整开发。

目标：
1. 删除前端“策略工作台”整个功能及对应前端代码，不影响后端策略能力、回测、选股宝典、模拟盘和设置页。
2. 删除前端“市场情绪”独立页签及对应前端代码，但实时监控界面的市场情绪、市场宽度、龙头强度、data_quality、pulse 等相关信息必须保留。
3. 新增“策略跟踪”功能页，展示已有生产策略选出的可买入、接近买点、观察确认股票，从首次推荐日起到信号结束期间的涨幅、回撤、买点触达、止损触发、生命周期状态、策略表现统计和单票详情。
4. 新页面优先复用现有组件、类型、格式化函数、API 封装和样式体系，前端展示要紧凑、高密度、性能友好。

执行要求：
- 不要只做文档或壳实现，必须完成真实功能开发。
- 修改前先用 `rg` 查清路由、导航、页面、store、API、候选策略和测试调用链。
- 删除前端页面代码时要确认没有被其他模块复用；可复用组件先迁移到共享目录，再删除页面专属代码。
- 不删除或削弱后端策略能力，不改变生产策略选股口径、排序口径、风控口径、回测口径和模拟盘账本。
- `/strategy` 应重定向到 `/backtest`，`/emotion` 应重定向到 `/monitor`。
- 顶部导航移除“策略工作台”和“市场情绪”，新增“策略跟踪”。
- 策略跟踪只做观察、复盘和统计，不得自动影响策略排序、模拟盘交易或真实交易。
- 后验表现统计必须和推荐当日信号隔离，防止未来函数污染策略。
- 数据不足、行情缺失、接口失败、暂无推荐、刷新中等状态必须有明确空状态和降级展示。
- 每个新增/修改点都要补测试。
- 必须同步完成策略跟踪增强能力：策略复盘中心、失败归因、市场状态分层、单票详情增强、策略健康度评分、Shadow 观测闭环、防未来函数审计面板、每日/每周策略跟踪报告。
- 每条策略跟踪记录必须能解释：是否触达买点、最高涨幅、最大回撤、是否止损、是否冲高回落、失败归因、市场状态、数据质量、是否异常收益。
- Shadow 样本为 0 时必须返回并展示明确原因，例如没有模型观测记录、没有符合条件信号、数据缺失、策略未启用、时间窗口未到、任务未运行、写入失败或 schema mismatch。
- 防未来函数审计必须展示信号生成时间、数据截止时间、回看窗口、后验收益计算起点、数据来源和异常收益复核标记。
- 每个推荐票必须增加持有期统计：最优持有天数、最优退出日期、最优收益、承受回撤、收益/回撤比、利润回吐、是否适合短线转波段/中长线观察。
- 持有期最优结果属于后验复盘指标，不能用于反推推荐当日信号；短线转中长线判断只能使用当日以前可见数据。

性能要求：
- 必须把性能设计纳入实现，不允许做成“功能可用但大数据量卡顿”的页面。
- 后端按“Python 编排 + Go 读聚合 + Rust 数值计算”的边界设计。
- Python 负责策略跟踪生命周期生成、后台刷新、数据落库、业务规则编排和 fallback。
- Go 优先用于读多写少、高并发、批量聚合接口，包括策略跟踪 summary、items、performance、detail 的读取聚合、分页、缓存、partial response、Redis/MySQL fallback。
- Rust 优先用于纯数值计算，包括最大涨幅、最大回撤、rolling return、ATR、波动率、胜率、盈亏比等基础数组计算；Python wrapper 必须处理空数组、短数组、NaN、缺失值。
- 如果当前已有 Go/Rust 基础设施可复用，优先接入现有服务；不要重复造新服务。
- 如果某项 Go/Rust 改造会明显拉长开发周期，先保留 Python 实现，但必须预留清晰接口边界、metrics、日志和后续迁移点，不能写死。
- 策略跟踪列表接口必须后端分页，默认 limit 不超过 50，不允许前端一次性拉全量再过滤。
- 聚合统计必须后端完成，前端只做展示，不承担大规模收益、回撤、胜率计算。
- 单票走势、K 线、时间轴必须懒加载，只在打开详情抽屉时请求。
- 前端图表必须按需加载，避免首屏打包过大。
- 表格数据需要稳定 rowKey、分页、排序参数和请求去抖，避免筛选时重复请求。
- 大列表优先使用 antd Table 分页；如单页超过 100 行，必须使用虚拟滚动或降低默认 page size。
- 页面状态应使用 React Query 或项目现有 query 模式缓存，避免重复请求同一数据。
- 避免大对象进入 React state；列表接口不要返回完整 payload_json，详情接口再按需返回。
- data_quality 为 partial/unavailable 时页面必须降级展示，不能白屏。
- 性能验收必须包括：首屏不加载全量历史走势、列表默认分页、详情按需加载、前端 build chunk 无明显膨胀、策略跟踪接口响应时间有日志或测试说明、Go/Rust 是否接入生产路径有明确说明。

代码质量硬性要求：
- 拒绝代码坏味道，不允许为了赶进度写临时补丁、重复逻辑、巨型组件、巨型函数、隐式副作用或难以测试的代码。
- 单个新增或大幅修改文件尽量控制在 500 行以内；如果超过，必须拆分为服务、schema、hook、组件、工具函数或测试文件。
- 不重复造轮子，优先复用项目已有组件、store、API client、格式化函数、表格、空状态、图表和样式 token。
- 不把业务逻辑堆在 React 组件里；数据转换、状态判断、生命周期计算应放到独立 helper/service，并补单元测试。
- 不写魔法数字和散落字符串；策略状态、生命周期状态、排序字段、data_quality 状态要集中定义。
- 不用大段 inline style 新造页面风格；优先复用现有紧凑布局和共享样式。
- 不吞异常；接口失败、数据缺失、partial response 必须可观测并在 UI 降级展示。
- 不引入无必要的新依赖，尤其是大体积图表库或状态库。
- 不做破坏性重构；只围绕本需求清理和新增。
- 不留下无用代码、死路由、未使用 import、重复测试 fixture 或注释掉的旧实现。
- TypeScript 和 Python 类型要尽量明确，避免 `any`、裸 `dict`、裸 `object` 扩散。
- 后端聚合逻辑要可测试、可回放，不能依赖前端做大规模计算。
- 所有删除都要经过引用检查，确保不是共享能力。

验收要求：
- 前端 lint/test/build 通过。
- 后端相关 pytest 通过。
- Go 相关测试通过，至少覆盖被接入或预留的策略跟踪读聚合边界。
- Rust 相关测试通过，至少覆盖被接入或预留的数值计算边界。
- 路由测试覆盖 `/strategy`、`/emotion`、`/strategy-tracking`。
- 策略跟踪后端测试覆盖生产策略过滤、首次推荐、生命周期结束、最大涨幅、最大回撤、买点触达、止损触发、数据缺失降级。
- 策略跟踪增强测试覆盖失败归因、冲高回落、市场状态分层、策略健康度、Shadow 0 样本原因、防未来函数审计、异常收益标记、日报周报生成。
- 持有期优化测试覆盖最优持有天数、最大收益/回撤折中、利润回吐、短线转中长线资格，以及不使用未来数据。
- 前端测试覆盖导航变化、策略跟踪空状态、列表、详情抽屉、分页、错误状态和性能友好行为。
- 验证实时监控、选股宝典、回测页、模拟盘、设置页不受影响。
- 最后检查是否存在明显代码坏味道：重复逻辑、超大文件、未使用代码、页面级样式膨胀、异常吞掉、测试缺口。

最终输出：
1. 完成情况。
2. 修改过的关键文件。
3. 删除的前端页面代码范围。
4. 新增的策略跟踪能力。
5. Go 是否接入策略跟踪读聚合路径；如果未接入，说明原因和预留边界。
6. Rust 是否接入策略跟踪数值计算路径；如果未接入，说明原因和预留边界。
7. 前端性能优化点。
8. 新增/修改的测试。
9. 实际运行的验证命令和结果。
10. 是否发现并处理了代码坏味道。
11. 未完成项、原因和下一步。
```
