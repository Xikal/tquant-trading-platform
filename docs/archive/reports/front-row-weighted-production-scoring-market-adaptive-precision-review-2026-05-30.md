# 前排加权生产评分策略行情自适应精度审查

生成日期：2026-05-30
审查对象：前排加权生产评分组合策略结果与收益报告
新增审查条件：信号少本身不是问题，但必须足够精准；牛市/修复行情可以多给信号，普跌/退潮/弱行情应主动少给或不给信号。

相关文件：

- `/Users/j/Documents/gupiao/docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`
- `/Users/j/Documents/gupiao/docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.md`
- `/Users/j/Documents/gupiao/docs/reports/front-row-weighted-production-scoring-codex-strict-review-2026-05-30.md`

## 1. 修订后的总体结论

新增条件成立：不能再把全局信号日留存 `52.47%` 单独作为否决理由。对短线低吸策略来说，弱行情主动少出信号是正确方向，关键要看不同市场状态下是否做到：

- 牛市/普涨/修复行情：信号可以多，且收益、PF、胜率、平均单笔必须同步提升。
- 普跌/退潮/弱轮动行情：信号可以少，甚至应当空仓，但留下来的少量信号必须足够精准。
- 退潮行情：原则上不新开仓。

按这个新条件复核后，结论仍然是不进入小流量生产观察，继续 Shadow/Paper。理由不再是“信号少”本身，而是：

1. `front_row_weighted` 在 `broad_rally` 和 `repair` 中表现明显改善，这是正向证据。
2. `high_flyer_retreat` 下没有生产候选，符合退潮不新开仓原则。
3. `low_volume_wait` 样本少但表现好，方向正确，但样本只有 `25` 条，不足以放行。
4. `fast_rotation` 样本很少但不精准，PF 只有 `0.33`，平均单笔 `-2.336%`，必须继续压制。
5. `weight_support_active` 样本很少但精度不足，PF `1.12`、胜率 `42.50%`、平均单笔 `0.233%`，不能作为生产依据。
6. 现有报告只有按市场状态的样本拆分，缺少按市场状态的信号日、最长无票、真实组合资金路径和 OOS 证据。

所以，新的阻断项应从单一的 `signal_day_retention_below_75pct` 修订为：

- `market_state_adaptive_precision_evidence_incomplete`
- `weak_state_precision_failed_fast_rotation`
- `weight_support_active_precision_insufficient`
- `oos_sample_too_thin`
- `field_level_future_leak_evidence_missing`

## 2. 新条件下的核心判断

旧逻辑：信号日留存低于 75% 直接阻断。
新逻辑：信号少可以接受，但必须证明“少得对、少得准、少在弱行情、多在强行情”。

本轮数据对新逻辑的支持程度如下：

| 审查项 | 当前结果 | 结论 |
|---|---|---|
| 强行情是否多给信号 | `broad_rally + repair` 占 `front_row_weighted` 样本约 94.95% | 符合方向 |
| 弱行情是否少给信号 | `fast_rotation + low_volume_wait + weight_support_active` 合计 78 条 | 符合少信号方向 |
| 退潮是否不新开仓 | `high_flyer_retreat` 为 0 条 | 符合方向 |
| 少信号是否足够精准 | `low_volume_wait` 准，`fast_rotation` 不准，`weight_support_active` 不够准 | 未通过 |
| 是否有市场状态信号日证据 | 缺少 per-market-state signal_days | 未通过 |
| 是否有足够 OOS 证据 | 2026Q2 只有 6 条样本 | 未通过 |

结论：策略已经体现出“行情自适应收缩”的雏形，但还没有通过“少而准”的生产审查。

## 3. 按市场状态拆分审查

### 3.1 市场状态表现表

| 市场状态 | baseline 样本 | weighted 样本 | 样本留存 | weighted max5 | 相对 baseline | weighted PF | weighted 胜率 | 平均单笔 | 审查判断 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| broad_rally | 1667 | 829 | 49.73% | 26.95% | +6.04% | 2.46 | 57.52% | 1.126% | 可多给信号且精度提升 |
| repair | 2293 | 637 | 27.78% | 77.40% | +32.60% | 2.15 | 56.77% | 1.103% | 可多给信号且精度提升 |
| fast_rotation | 164 | 13 | 7.93% | -5.01% | +10.90% | 0.33 | 23.08% | -2.336% | 少但不准，应继续压制或禁开 |
| low_volume_wait | 96 | 25 | 26.04% | 1.33% | +2.36% | 3.18 | 66.67% | 1.906% | 少且准，但样本过小 |
| weight_support_active | 407 | 40 | 9.83% | 2.76% | +20.24% | 1.12 | 42.50% | 0.233% | 少但精度不足，仅观察 |
| high_flyer_retreat | 165 | 0 | 0.00% | 0.00% | +0.00% | 0.00 | 0.00% | 0.000% | 主动空仓方向正确 |

### 3.2 强行情：broad_rally

`broad_rally` 下，`front_row_weighted` 的样本从 baseline 的 `1667` 降到 `829`，留存 `49.73%`。这个减少可以接受，因为精准度明显提升：

- max5 真实组合：`20.91% -> 26.95%`
- PF：`1.31 -> 2.46`
- 胜率：`48.33% -> 57.52%`
- 平均单笔：`0.382% -> 1.126%`

审查结论：强行情中不是无脑减少信号，而是保留了接近一半样本，并显著提高质量。这是支持生产评分方向的正证据。

但仍需补充：

- broad_rally 下的信号日留存。
- broad_rally 下的日均候选数。
- broad_rally 下 max5/max10 排名边际收益。
- broad_rally OOS 独立验证。

### 3.3 修复行情：repair

`repair` 是当前策略最强的市场状态：

- baseline 样本 `2293`，weighted 样本 `637`，留存 `27.78%`
- max5 真实组合：`44.80% -> 77.40%`
- PF：`1.33 -> 2.15`
- 胜率：`50.59% -> 56.77%`
- 平均单笔：`0.462% -> 1.103%`

审查结论：修复行情中，前排加权明显有效。它保留的信号不算多，但收益质量提升明显。此状态可以作为后续 Paper 重点观察对象。

风险：

- `repair` 对总收益贡献过大，可能导致策略依赖修复行情。
- 需要验证不同修复阶段：初修复、中段修复、尾段修复是否都有效。
- 需要防止用事后市场状态定义把修复行情“回填”到信号日。

### 3.4 快速轮动：fast_rotation

`fast_rotation` 是当前最大问题之一。weighted 确实把样本压到很少，只剩 `13` 条，留存 `7.93%`，但少量信号并不精准：

- max5 真实组合：`-5.01%`
- PF：`0.33`
- 胜率：`23.08%`
- 平均单笔：`-2.336%`
- 候选信号最大回撤：`-25.309%`

审查结论：这里不是“少而准”，而是“少但仍错”。快速轮动下应进一步收缩，甚至生产禁开，只保留观察池。

建议：

- `fast_rotation` 下 production_score 上限降低到观察区间。
- 只有 `soft_buy_now + core_leader/leader_hot + 低风险 + 强板块确认` 才允许 Paper。
- 在没有额外验证前，fast_rotation 不应进入生产收益候选池。

### 3.5 缩量等待：low_volume_wait

`low_volume_wait` 下样本很少，只有 `25` 条，但表现较好：

- max5 真实组合：`1.33%`
- 相对 baseline：`+2.36%`
- PF：`3.18`
- 胜率：`66.67%`
- 平均单笔：`1.906%`
- 最大回撤：`-3.318%`

审查结论：这是“少而准”的正向证据，但样本太少，不能放行。它可以继续 Paper，不能生产。

建议：

- 保留低频高精度候选。
- 弱市场总仓位仍应 `<= 40%`，甚至可以降到 `<= 20%`。
- 至少补到 `>=100` 条成交样本或多个独立低量阶段后再判断。

### 3.6 权重支撑活跃：weight_support_active

`weight_support_active` 下 weighted 样本只有 `40` 条，留存 `9.83%`。相对 baseline 的 max5 从 `-17.48%` 改成 `2.76%`，方向改善，但精度不够：

- PF：`1.12`
- 胜率：`42.50%`
- 平均单笔：`0.233%`
- 最大回撤：`-16.671%`

审查结论：这类行情虽然过滤后不再大亏，但仍谈不上精准。不能生产，只能观察。

建议：

- 提高该状态下 production_score 阈值。
- 要求更强的前排层级或板块热度确认。
- 把 `weight_support_active` 从“可进攻”降为“谨慎观察/低仓 Paper”。

### 3.7 高标退潮：high_flyer_retreat

baseline 下仍有 `165` 个样本，候选信号表现为负；weighted 下生产候选为 `0`。这符合“普跌/退潮行情信号少一些，甚至不新开仓”的要求。

审查结论：退潮不新开仓是正确设计，应保留为生产硬约束。

但还要补充：

- 确认 `high_flyer_retreat` 的市场状态生成时间不晚于信号时间。
- 增加 `risk_release` 的独立统计，如果样本缺失也要说明。
- 输出退潮状态下被阻断候选数量和阻断原因。

## 4. 信号少是否构成问题

在新增条件下，信号少不再自动构成问题。正确的审查方式是按行情状态判断。

### 4.1 可以接受信号少的情况

以下情况信号少是合理的：

- 退潮、普跌、风险释放状态。
- 快速轮动、低量等待状态。
- 个股和板块不满足前排条件。
- 只有 near_entry，尚未进入 buy_now / soft_buy_now。
- 评分高但交易执行条件不满足。

### 4.2 不能接受信号少的情况

以下情况信号少仍是问题：

- broad_rally 或 repair 中长期无票。
- 强行情中只剩极少数票，导致错过大部分可交易机会。
- 信号少但 PF、胜率、平均单笔没有明显提升。
- 信号少但由事后过滤造成，而不是信号日前可知状态造成。
- 信号少导致 OOS 样本长期不足，无法验证稳定性。

本轮数据说明：`broad_rally` 和 `repair` 中信号减少后质量提升，方向正确；但 `fast_rotation` 和 `weight_support_active` 中还没有做到足够精准。

## 5. 对原 75% 信号日门槛的修订

原报告把信号日留存 `52.47%` 作为硬阻断。新增条件下，这个结论需要修订。

修订后：

- 全局信号日留存不再作为唯一硬门槛。
- 必须改为市场状态分层留存和精准度门槛。
- 强行情要有足够覆盖。
- 弱行情可以低覆盖，但必须高精准或直接空仓。

建议把原门槛改成：

| 市场状态 | 覆盖要求 | 精准度要求 | 当前结果 |
|---|---|---|---|
| broad_rally | 不宜过低，应保留主要机会 | PF >= 1.8，平均单笔 >= 0.7% | 通过初筛 |
| repair | 可中等覆盖，重质量 | PF >= 1.8，平均单笔 >= 0.7% | 通过初筛 |
| fast_rotation | 可以很少 | PF >= 1.5，平均单笔 > 0 | 未通过 |
| low_volume_wait | 可以很少 | PF >= 1.8，平均单笔 >= 0.8% | 指标通过但样本不足 |
| weight_support_active | 低覆盖，谨慎 | PF >= 1.5，平均单笔 >= 0.5% | 未通过 |
| high_flyer_retreat / risk_release | 原则上 0 新开仓 | 生产候选为 0 | high_flyer_retreat 通过 |

因此，新的结论不是“因为全局信号少而失败”，而是“行情自适应精度证据不完整，且部分弱状态少而不准”。

## 6. 收益真实性复核

在行情自适应视角下，收益真实性评价更清晰：

正向证据：

- 收益主要来自 `broad_rally` 和 `repair`，符合短线低吸策略应在可交易行情中出手的逻辑。
- `front_row_weighted` 把强/修复行情样本占比提高到约 94.95%。
- 退潮状态下生产候选为 0，避免了 baseline 在退潮中的负收益样本。
- `repair` 和 `broad_rally` 的 PF、胜率、平均单笔都有同步提升，不只是收益率提升。

负向证据：

- `fast_rotation` 少量信号仍然亏损，说明弱状态过滤不够硬。
- `weight_support_active` 虽然相对 baseline 改善，但精度不足。
- `low_volume_wait` 表现好但样本太少。
- 缺少 per-market-state 信号日、最长无票和 OOS 验证。
- 现有收益仍可能受样本筛选、市场状态定义、幸存者偏差影响。

结论：行情自适应方向是对的，但不能证明收益已经可生产。

## 7. max5 / max10 复核

新增条件不改变 max5/max10 的审查结论。

当前仍建议：

- Paper 主口径使用 max5。
- max10 暂不生产。
- max10 只能在 `broad_rally` 和 `repair` 中重新做分层验证。
- 弱行情不应因为 max10 提高持仓上限。

需要新增的验证：

| 验证项 | 要求 |
|---|---|
| broad_rally 下 max5/max10 对比 | 判断强行情是否可以扩到 max10 |
| repair 下 max5/max10 对比 | 判断修复行情是否可以适度扩仓 |
| weak states 下 max5/max10 对比 | 原则上不扩仓，只验证禁开是否更优 |
| production_score 排名分桶 | 验证第 1-5 名和第 6-10 名边际收益 |

## 8. front_row_only 复核

新增条件不会改变 `front_row_only` 禁止生产硬过滤的结论。

虽然信号少可以接受，但 front_row_only 的问题不是“少”本身，而是：

- 样本过窄，只有 `194` 条。
- 信号日只有 `88` 天，最长无票 `42` 天。
- 只按前排硬过滤，缺少市场状态、风险、信号状态、策略先验的组合判断。
- `low_volume_wait` 和 `weight_support_active` 下表现差。
- max10 收益低于 baseline。

因此，`front_row_only` 仍只能作为对照，不得生产。

## 9. near_entry 复核

新增条件下，`near_entry` 的定位更明确：

- 牛市/修复行情中，near_entry 可以扩大观察池，但不能进入生产收益排行。
- 弱行情中，near_entry 应更偏观察，不应提前转生产。
- 普跌/退潮中，near_entry 也不应绕过退潮不开仓规则。

当前 `near_entry_production_score_count=0` 正确，应保留。

需要补充：

- 按市场状态统计 near_entry 转化率。
- broad_rally / repair 下 near_entry 到 buy_now 的转化质量。
- weak states 下 near_entry 的误报率。

## 10. 未来函数复核

新增条件使未来函数审计更重要，因为市场状态本身会直接决定“多出信号”还是“少出信号”。

必须补字段级证据：

- `market_state` 的生成时间。
- `market_state_category` 的生成时间。
- `market_state_strength` 的生成时间。
- `sector_heat`、`industry_rank`、`leader_strength_rank` 的生成时间。
- 每条候选的 `signal_date`、`feature_asof_date`、`decision_generated_at`。

尤其要防止：

- 用收盘后市场状态决定当日盘中信号。
- 用未来板块涨幅回填 `repair` 或 `broad_rally`。
- 用后验龙头地位回填前排强度。

没有字段级证据前，`future_leak_check=passed` 不能作为生产放行依据。

## 11. 过拟合复核

新增条件下，过拟合审查必须按市场状态做，而不是只看总表。

必须补：

1. 每个市场状态独立 OOS。
2. 每个市场状态 walk-forward。
3. 每个市场状态参数冻结后复跑。
4. 强行情和弱行情分别做排名分桶。
5. `repair` 行情内部再拆：初修复、中段修复、尾段修复。

当前最大问题仍是 OOS 太薄。2026Q2 只有 `6` 条样本，不能证明“少而准”。

## 12. 报告展示修订

报告必须新增“行情自适应精度表”，不能只展示总样本留存。

建议主表改为：

| 市场状态 | baseline 样本 | weighted 样本 | 样本留存 | weighted max5 | PF | 胜率 | 平均单笔 | 状态结论 |
|---|---:|---:|---:|---:|---:|---:|---:|---|

同时取消把 `signal_day_retention_below_75pct` 作为唯一 blocker 的写法，改成：

```text
global_signal_day_retention=reference_only
market_state_adaptive_gate=required
strong_market_coverage_required=true
weak_market_precision_required=true
retreat_market_new_position_blocked=true
```

还需要补充：

- 各市场状态的信号日留存。
- 各市场状态的最长无票。
- 各市场状态的真实组合 max5/max10。
- 各市场状态的 OOS 表现。

## 13. 必须整改项

### P0

1. 把准入逻辑从“全局信号日留存 >= 75%”改为“市场状态自适应覆盖 + 精准度门槛”。
2. 增加按市场状态的信号日、最长无票、日均候选数统计。
3. `fast_rotation` 下生产候选必须进一步压制，当前 PF `0.33` 不允许生产。
4. `weight_support_active` 下不得生产放行，当前 PF `1.12`、胜率 `42.50%` 不够精准。
5. `high_flyer_retreat` 和 `risk_release` 保持不新开仓。
6. 补字段级未来函数审计，尤其是 market_state 和 front_row_strength。
7. 补 OOS 样本，不能用 2026Q2 的 6 条样本证明泛化。

### P1

1. broad_rally / repair 单独做 max5/max10 回测。
2. low_volume_wait 单独积累样本，验证少而准是否稳定。
3. repair 行情拆成初修复、中段修复、尾段修复。
4. 增加 production_score 排名分桶，验证强行情是否可以扩仓。
5. 按市场状态做交易成本、滑点、涨跌停、停牌验证。
6. 增加市场状态迁移测试，例如 repair 转 fast_rotation、broad_rally 转 high_flyer_retreat。

### P2

1. 增加行情状态解释字段，让用户知道为什么今天多信号或少信号。
2. 增加观察池转化看板。
3. 增加弱行情空仓天数说明，避免用户把少信号误判为系统失效。
4. 增加按市场状态的月度报告。

## 14. 下一阶段准入门槛

### 14.1 强行情准入

适用于 `broad_rally`、`repair`。

| 条件 | 门槛 |
|---|---:|
| 市场状态内成交样本 | >= 300 |
| 市场状态内信号日 | >= 60 |
| PF | >= 1.8 |
| 胜率 | >= 54% |
| 扣成本后平均单笔 | >= 0.7% |
| 真实组合最大回撤 | <= 12% |
| 相对 baseline max5 超额 | >= +10pct |

### 14.2 弱行情准入

适用于 `fast_rotation`、`low_volume_wait`、`weight_support_active`。

| 条件 | 门槛 |
|---|---:|
| 信号数量 | 可以少 |
| PF | >= 1.6 |
| 胜率 | >= 55% |
| 扣成本后平均单笔 | >= 0.6% |
| 真实组合最大回撤 | <= 6% |
| 连续亏损控制 | 不超过 3 笔 |
| 不达标处理 | watch_only 或不新开仓 |

### 14.3 退潮行情准入

适用于 `high_flyer_retreat`、`risk_release`。

| 条件 | 门槛 |
|---|---:|
| 新开生产仓 | 0 |
| production_score | 不生成或强制低于组合候选阈值 |
| near_entry | 仅观察 |
| 允许动作 | 风险提示、持仓处理、观察池记录 |

### 14.4 全局准入

| 条件 | 门槛 |
|---|---:|
| 完整数据 | 至少 24 个月 |
| 字段级未来函数违规 | 0 |
| OOS 成交样本 | >= 150 |
| OOS 覆盖市场状态 | 至少包含强行情和弱行情 |
| near_entry 进入 production_score | 0 |
| production_sort_replaced | false，直到审批通过 |

## 15. 最终建议

最终建议：继续 Shadow/Paper，不进入小流量生产观察。

但结论逻辑需要修订：

旧结论：因为信号日留存低于 75%，所以阻断。
新结论：信号少可以接受，但当前还没有完整证明“少而准”；其中 `fast_rotation` 明确少而不准，`weight_support_active` 精度不足，`low_volume_wait` 样本太少，OOS 太薄。

可肯定的部分：

- `broad_rally` 和 `repair` 下前排加权有效。
- 退潮不新开仓方向正确。
- 策略已经具备行情自适应收缩雏形。

不能放行的部分：

- 弱状态精度没有全部过关。
- 市场状态分层证据缺少信号日和 OOS。
- 未来函数仍缺字段级审计。
- max10 仍不应生产。

下一步应围绕“行情状态自适应精度”继续 Paper，而不是单纯追求全局信号日留存。
