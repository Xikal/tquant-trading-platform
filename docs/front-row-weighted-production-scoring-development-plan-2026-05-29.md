# 前排加权生产排序模型开发文档

## 1. 背景与结论

基于 2026-05-29 的 24 个月策略回测与前排过滤 A/B 报告，本次不采用“只要前排票”的硬过滤生产方案。

核心结论：

1. 前排纯过滤会显著压缩样本，容易出现长期无票。
2. 旧报告中的“总收益率”统一按“每日信号等权复利收益”理解，不能当作真实组合收益。
3. 生产收益排行只允许 `buy_now` 和 `soft_buy_now` 进入。
4. `near_entry` 只能进入观察池和提醒链路，禁止进入生产收益排行。
5. 新方案采用“前排加权、后排降权、极端后排剔除、真实组合约束”的排序模型。
6. 首次上线必须先走 Shadow 排序和 Paper 组合回测，不直接替换生产排序。

## 2. 已有报告证据

### 2.1 前排硬过滤结论

| 口径 | baseline | front_row_only |
| --- | ---: | ---: |
| 样本 | 65557 | 1320 |
| 成交 | 59520 | 1210 |
| 信号日 | 400 | 219 |
| 每日信号等权复利收益 | 569.85% | 259.34% |
| 最大回撤 | -19.11% | -28.48% |
| 胜率 | 46.00% | 48.76% |
| PF | 1.25 | 1.30 |
| 平均单笔 | 0.337% | 0.386% |

留存结果：

| 指标 | 留存 |
| --- | ---: |
| 样本留存 | 2.01% |
| 成交留存 | 2.03% |
| 信号日留存 | 54.75% |

判断：

- PF 和平均单笔略有提升，但样本和信号日损失过大。
- 最大回撤没有改善，反而更差。
- 生产不能采用 `front_row_only` 硬过滤。
- 前排信息应作为排序加权和后排惩罚使用，而不是作为唯一准入条件。

### 2.2 信号状态表现

| 状态 | 样本/成交 | PF | 平均单笔 | 生产处理 |
| --- | ---: | ---: | ---: | --- |
| `soft_buy_now` | 827 / 788 | 1.85 | 0.832% | 高优先生产候选 |
| `buy_now` | 3965 / 3865 | 1.09 | 0.145% | 需叠加风控和前排过滤 |
| `near_entry` | 60765 / 54867 | 1.26 | 0.344% | 只进观察池，不进生产排行 |

判断：

- `soft_buy_now` 历史质量明显好于 `buy_now`，应提高排序权重。
- `buy_now` 不能只按原始状态直接生产买入，应结合风控、市场状态和前排强度。
- `near_entry` 样本极大，混入生产排行会污染生产收益判断。

## 3. 模型目标

本次新增两个分数，严格分离生产与观察：

### 3.1 生产排序分

字段名：

```text
production_score
```

用途：

1. 真实组合候选池排序。
2. Paper 组合回测排序。
3. 后续小流量生产观察排序。

准入限制：

1. 只允许 `buy_now` 和 `soft_buy_now` 进入。
2. `near_entry` 的 `production_score` 必须为 `null`。
3. 被硬风险拦截的候选必须直接剔除。

### 3.2 观察排序分

字段名：

```text
watch_score
```

用途：

1. 观察池排序。
2. 推荐提醒。
3. 后续买点触发跟踪。
4. Shadow 观测和策略跟踪中心。

准入范围：

1. 允许 `near_entry`。
2. 允许 `observe_confirmed`。
3. 允许未达生产阈值但仍有跟踪价值的 `buy_now` / `soft_buy_now`。
4. 不参与生产收益排行。

## 4. 核心打分公式

### 4.1 生产分

建议实现为 0 到 100 分：

```text
production_score =
  base_score
+ signal_state_score
+ strategy_prior_score
+ front_row_strength_score
+ strategy_front_interaction_score
+ market_state_score
+ entry_structure_score
+ risk_quality_score
+ portfolio_occupancy_score
+ external_factor_score
- laggard_penalty
- retreat_penalty
- abnormal_penalty
```

建议默认：

```text
base_score = 50
```

最终分数：

```text
production_score = clamp(0, score_cap, raw_score)
```

其中 `score_cap` 由后排、弱市场、退潮市场和硬风险共同决定。

### 4.2 观察分

```text
watch_score =
  watch_base_score
+ signal_state_watch_score
+ strategy_prior_watch_score
+ front_row_watch_score
+ entry_structure_score
+ market_state_watch_score
- risk_penalty
- abnormal_penalty
```

建议默认：

```text
watch_base_score = 45
```

`watch_score` 不用于生产买入，只用于观察排序和后续触发买点。

## 5. 信号状态权重

### 5.1 生产权重

| 状态 | production_score 处理 |
| --- | ---: |
| `soft_buy_now` | +16 |
| `buy_now` | +8 |
| `observe_confirmed` | `null` |
| `near_entry` | `null` |
| `watch` / `avoid` | `null` |

### 5.2 观察权重

| 状态 | watch_score 处理 |
| --- | ---: |
| `soft_buy_now` | +14 |
| `buy_now` | +10 |
| `observe_confirmed` | +6 |
| `near_entry` | +10 |
| `watch` | +2 |
| `avoid` | -20 |

## 6. 策略先验权重

策略先验来自已有 24 个月报告和前排 A/B 结果。该权重只作为初始工程配置，后续必须通过真实组合 max5 / max10 回测校验。

| 策略名称 | strategy_key | production 先验 | watch 先验 | 处理 |
| --- | --- | ---: | ---: | --- |
| 首板回调 | `first_board` | +14 | +12 | 核心策略 |
| 均线通道波段 | `ma_channel_band` | +10 | +12 | 无明确买点时只观察 |
| 龙头回踩波段 | `leader_pullback_band` | +8 | +10 | 需增强明确买点 |
| 量能低吸 | `volume_shrink` | +5 | +6 | 不给额外前排奖励 |
| 深度低吸 | `deep_pullback` | +4 | +8 | 样本少，生产 cap |
| 长洗 N 字冲高 | `n_pattern_long_wash` | +3 | +6 | 高回撤，只 Shadow 小权重 |
| 原始低吸法 | `classic_retrace` | +2 | +4 | 辅助观察 |
| 均线支撑 | `ma_support` | +2 | +4 | 辅助观察 |
| 收盘强势承接 | `late_session_strong_support` | +3 | +5 | 可观察 |
| 中军 VWAP/均线回踩 | `core_midcap_vwap_ma5_retrace` | +1 | +4 | 需市场过滤 |
| 位置支撑 | `breakout_support` | 0 | +3 | 降权观察 |
| 涨停突破回踩 | `limit_up_breakout_retrace` | -2 | +2 | 降权观察 |
| 趋势龙回头 | `trend_rebound` | -3 | +2 | 降权观察 |
| 短洗 N 字冲高 | `n_pattern_short_wash` | -10 | +1 | 暂停生产，只研究 |
| 分歧转一致 | `divergence_consensus` | -10 | +1 | 暂停生产，只研究 |
| 主线首分歧低吸 | `sector_mainline_first_divergence_low_buy` | -10 | +1 | 暂停生产，只研究 |
| 主线涨停缩量回调 | `mainline_limitup_shrink_retrace_reclaim` | -10 | +1 | 暂停生产，只研究 |

策略暂停生产的实现要求：

1. 暂停生产策略仍可计算 `watch_score`。
2. 暂停生产策略的 `production_score` 默认设为 `null`，或强制 cap 到 60 以下。
3. 不删除策略，不影响研究回测和 Shadow 观测。

## 7. 前排/后排因子

### 7.1 分层定义

新增或复用字段：

```text
front_row_tier
```

建议取值：

| front_row_tier | 含义 |
| --- | --- |
| `core_leader` | 龙头 + 核心主线 + 强度 rank <= 3 |
| `leader_hot` | 龙头/强跟随 + 热门板块 |
| `strong_follower` | 强跟随 + 次热门板块 |
| `middle` | 普通中排 |
| `laggard` | 后排 |
| `cold_laggard` | 冷门板块 + 后排 |
| `unknown` | 数据不足 |

### 7.2 前排强度分

| 分层 | production_score | watch_score |
| --- | ---: | ---: |
| `core_leader` | +14 | +12 |
| `leader_hot` | +10 | +9 |
| `strong_follower` | +5 | +6 |
| `middle` | 0 | +2 |
| `laggard` | -8 | -4 |
| `cold_laggard` | -14 | -8 |
| `unknown` | -2 | 0 |

### 7.3 极端后排剔除

满足以下任一条件时，直接剔除生产候选：

1. `front_row_tier = cold_laggard` 且市场状态为弱势或退潮。
2. 板块处于退潮，个股同时为后排。
3. 出现硬风险标签，例如数据异常、停牌、ST、退市风险、流动性不足。
4. 近端冲高回落明显，且成交量放大、承接弱。

## 8. 策略与前排交互权重

前排加权不能一刀切，需要按策略适配。

| 策略 | strategy_key | 交互加分 |
| --- | --- | ---: |
| 首板回调 | `first_board` | +6 |
| 龙头回踩波段 | `leader_pullback_band` | +6 |
| 长洗 N 字冲高 | `n_pattern_long_wash` | +4 |
| 收盘强势承接 | `late_session_strong_support` | +3 |
| 均线支撑 | `ma_support` | +2 |
| 均线通道波段 | `ma_channel_band` | +1 |
| 量能低吸 | `volume_shrink` | 0 |
| 位置支撑 | `breakout_support` | 0 |
| 趋势龙回头 | `trend_rebound` | -1 |
| 深度低吸 | `deep_pullback` | -1 |

规则：

1. 只有 `front_row_tier` 属于 `core_leader`、`leader_hot`、`strong_follower` 时才触发交互加分。
2. `volume_shrink` 不因前排额外加权，因为报告显示前排过滤后表现变差。
3. `n_pattern_long_wash` 仅允许小加权，并受最大回撤 cap 约束。
4. `n_pattern_short_wash` 不触发生产交互加分。

## 9. 市场状态分

| 市场状态 | production_score | watch_score | 处理 |
| --- | ---: | ---: | --- |
| `broad_rally` | +8 | +6 | 强势行情 |
| `repair` | +6 | +5 | 修复行情 |
| `weight_support_active` | +4 | +4 | 权重支撑 |
| `fast_rotation` | -4 | -2 | 快速轮动 |
| `low_volume_wait` | -8 | -4 | 缩量等待 |
| `high_flyer_retreat` | -18 | -10 | 高位退潮 |
| `risk_release` | -18 | -10 | 风险释放 |
| `unknown` | -2 | 0 | 数据不足 |

退潮市场限制：

```text
high_flyer_retreat / risk_release:
  score_cap = min(score_cap, 50)
  不新开生产仓位，只保留观察和持仓处理
```

弱市场后排限制：

```text
low_volume_wait / fast_rotation + laggard:
  score_cap = min(score_cap, 55)
```

## 10. 入场结构分

入场结构只使用信号日及之前数据，禁止使用后验走势。

| 入场状态 | production_score | watch_score |
| --- | ---: | ---: |
| 买点区内且承接稳定 | +8 | +6 |
| 轻微高于买点但回撤可控 | +4 | +5 |
| 接近买点 | `null` 或 0 | +8 |
| 低于支撑但未破坏结构 | -4 | +2 |
| 跌破止损或结构破坏 | 剔除 | -20 |

`near_entry` 要求：

1. 不生成 `production_score`。
2. 可生成较高 `watch_score`。
3. 后续只有在重新触发 `buy_now` 或 `soft_buy_now` 后，才允许进入生产候选。

## 11. 风控质量分

风控质量基于已有风险字段、筹码派发、流动性、异常收益和数据质量。

| 风控状态 | production_score |
| --- | ---: |
| 止损清晰、盈亏比合格、数据完整 | +6 |
| 止损较近但盈亏比一般 | +2 |
| 派发风险中等 | -6 |
| 派发风险高 | -12 |
| 冲高回落明显 | -10 |
| 数据不足 | -15 |
| 异常收益需复核 | -20 |
| 硬风险 | 剔除 |

硬风险包括：

1. ST、退市、停牌。
2. 流动性不足。
3. 数据缺口影响信号日判断。
4. 信号生成时间晚于收益计算起点。
5. 使用了未来数据或无法证明数据截止时间。

## 12. 分数 cap 规则

cap 在所有加减分之后执行。

| 条件 | cap |
| --- | ---: |
| 普通后排 `laggard` | 68 |
| 弱市场后排 | 55 |
| 退潮市场 | 50 |
| 高回撤策略 `n_pattern_long_wash` | 72 |
| 样本不足策略 `deep_pullback` | 74 |
| 暂停生产策略 | 60 或 `null` |
| 硬风险 | 剔除 |

`near_entry` 不适用生产 cap，因为 `production_score = null`。

## 13. 分数到动作映射

| production_score | 动作 |
| ---: | --- |
| >= 82 | 可进真实组合候选池 |
| 72 - 82 | 轻仓 / Shadow / 人工确认 |
| 60 - 72 | 观察，不进生产组合 |
| < 60 | 放弃 |
| `null` | 不参与生产排行 |

观察动作：

| watch_score | 动作 |
| ---: | --- |
| >= 78 | 重点观察，触发买点后优先复核 |
| 65 - 78 | 普通观察 |
| 50 - 65 | 低优先观察 |
| < 50 | 不展示或折叠 |

## 14. 组合约束

真实组合和 Paper 组合必须使用资金占用口径，不能按信号无限复利。

### 14.1 持仓约束

```text
最大持仓：max5 / max10 两档同时回测
同票持有中禁止重复买入
持仓期间占用资金
```

### 14.2 集中度约束

```text
同一策略单日最多 2 只
同一板块最多 2 只
弱市场总仓位 <= 40%
退潮市场不新开仓，只处理持仓
```

### 14.3 排序优先级

```text
soft_buy_now + 首板回调 + 前排核心主线
> soft_buy_now + 龙头回踩/均线通道明确触发
> buy_now + 首板回调 + 前排
> buy_now + 其他策略
> near_entry 观察
```

## 15. 后端开发方案

### 15.1 新增评分模块

建议新增：

```text
backend/app/services/low_buy/production_scoring.py
```

核心对象：

```python
class ProductionScoreResult:
    production_score: float | None
    watch_score: float | None
    decision: str
    front_row_tier: str
    score_cap: float | None
    score_components: dict[str, float]
    exclusion_reasons: list[str]
    warning_tags: list[str]
```

核心函数：

```python
score_low_buy_candidate_for_production(
    candidate,
    *,
    market_context,
    portfolio_context=None,
    mode="shadow",
) -> ProductionScoreResult
```

### 15.2 配置化权重

建议新增配置文件或常量模块：

```text
backend/app/services/low_buy/production_scoring_config.py
```

配置内容：

1. 信号状态权重。
2. 策略先验权重。
3. 前排分层权重。
4. 策略与前排交互权重。
5. 市场状态权重。
6. cap 规则。
7. 暂停生产策略列表。

要求：

1. 所有阈值必须集中配置。
2. 代码中不散落魔法数字。
3. 回测报告必须记录配置版本。

### 15.3 接入优先榜

接入位置建议：

```text
backend/app/services/low_buy/priority_board.py
backend/app/services/low_buy/result_materialized.py
backend/app/services/low_buy/history.py
```

第一阶段只做 Shadow：

1. 计算并返回 `production_score` / `watch_score`。
2. 不改变当前生产优先榜排序。
3. 不改变策略原始 `score`。
4. 不改变买卖信号生成。

第二阶段 Paper 回测：

1. 回测脚本支持按 `production_score` 排序。
2. 使用 max5 / max10 真实组合口径。
3. 记录所有跳过原因。

第三阶段小流量：

1. 只在开关开启时用于生产候选排序。
2. 默认仍保留旧排序作为 fallback。

### 15.4 API 字段

优先榜、策略跟踪和回测结果建议新增字段：

```json
{
  "production_score": 86.5,
  "watch_score": 72.0,
  "production_decision": "portfolio_candidate",
  "front_row_tier": "core_leader",
  "score_cap": 100,
  "score_components": {
    "signal_state": 16,
    "strategy_prior": 14,
    "front_row_strength": 14,
    "market_state": 8,
    "risk_quality": 2
  },
  "exclusion_reasons": [],
  "warning_tags": ["front_row_weighted"]
}
```

兼容要求：

1. 旧前端字段不删除。
2. 新字段允许为空。
3. 未启用 Shadow 时返回 `null`，不影响现有页面。

## 16. 前端开发方案

### 16.1 优先榜展示

新增展示：

1. 生产排序分。
2. 观察排序分。
3. 前排/后排标签。
4. 生产动作标签。
5. 降权原因。

展示原则：

1. 普通用户优先看动作，不先看公式。
2. 高分票展示“可进组合候选”。
3. `near_entry` 展示“观察中，触发买点后再评估”。
4. 后排票展示“后排降权”或“弱市场后排，不建议开仓”。

### 16.2 策略跟踪中心

策略跟踪中心新增筛选：

1. 生产候选。
2. 观察候选。
3. 前排核心。
4. 后排降权。
5. 暂停生产策略。

新增解释字段：

1. 为什么进生产候选。
2. 为什么只观察。
3. 为什么被降权。
4. 为什么被剔除。

## 17. 回测开发方案

### 17.1 新增回测变体

在现有 24 个月回测基础上新增变体：

```text
baseline
front_row_only
front_row_weighted_shadow
front_row_weighted_max5
front_row_weighted_max10
```

其中：

1. `baseline` 使用现有口径。
2. `front_row_only` 只作为对照，不进生产。
3. `front_row_weighted_shadow` 只计算分数，不改变成交。
4. `front_row_weighted_max5` 使用新排序和最大 5 持仓。
5. `front_row_weighted_max10` 使用新排序和最大 10 持仓。

### 17.2 必须输出的指标

整体指标：

1. 样本数。
2. 成交数。
3. 信号日数。
4. 最长无票天数。
5. 真实组合收益。
6. 每日信号等权复利收益。
7. 最大回撤。
8. Sharpe。
9. 胜率。
10. PF。
11. 平均单笔。
12. 平均持仓。
13. 资金利用率。
14. 换手率。

组合约束指标：

1. max5 跳过数。
2. max10 跳过数。
3. 同票持有中重复买入跳过数。
4. 同策略单日超限跳过数。
5. 同板块超限跳过数。
6. 退潮市场不开仓跳过数。
7. 弱市场仓位上限跳过数。

分层指标：

1. 按信号状态。
2. 按策略。
3. 按策略族。
4. 按市场状态。
5. 按前排分层。
6. 按季度。
7. 按样本内、验证集、样本外。

### 17.3 报告输出

新增报告：

```text
docs/reports/front-row-weighted-production-scoring-backtest-YYYY-MM-DD.md
docs/reports/front-row-weighted-production-scoring-backtest-YYYY-MM-DD.json
```

报告必须包含：

1. 与 baseline 的对比。
2. 与 front_row_only 的对比。
3. max5 / max10 真实组合结果。
4. `buy_now` / `soft_buy_now` / `near_entry` 分开展示。
5. `near_entry` 不进入生产收益排行的说明。
6. 每日信号等权复利收益和真实组合收益分开展示。
7. 样本缩水和空窗风险。
8. 异常收益和未来函数审计。

## 18. 防未来函数要求

所有评分字段必须满足：

1. 信号生成时间不得晚于信号使用时间。
2. 前排强度只能使用信号日及之前可见数据。
3. 市场状态只能使用信号日及之前可见数据。
4. 板块热度只能使用信号日及之前可见数据。
5. 后验收益从信号日之后开始计算。
6. 不允许用后续涨幅反推前排标签。
7. 回测输出必须包含 `signal_time`、`data_cutoff_time`、`return_start_time`。

审计失败处理：

1. 该样本不得进入生产回测。
2. 报告标记为 `future_function_risk`。
3. 回测整体给出风险提示。

## 19. 防过拟合要求

训练和验收必须分层：

```text
train: 2024Q3 - 2025Q4
validation: 2026Q1
oos: 2026Q2
```

要求：

1. 参数先在训练段固定。
2. 验证段只做一次确认，不反复调参。
3. 样本外只做验收，不根据样本外结果继续调权重。
4. 禁止随机切分。
5. 使用时间顺序切分和 purged gap。
6. 报告必须展示季度稳定性，不能只看总收益。

## 20. 验收标准

### 20.1 Shadow 验收

必须满足：

1. 所有候选都能计算 `watch_score`。
2. `near_entry` 的 `production_score` 恒为 `null`。
3. 硬风险样本有明确剔除原因。
4. 旧排序不受影响。
5. API 向后兼容。

### 20.2 Paper 回测验收

建议进入小流量观察的最低条件：

| 指标 | 要求 |
| --- | --- |
| max5 真实组合收益 | 高于 baseline max5 |
| max10 真实组合收益 | 高于 baseline max10 |
| PF | 不低于 baseline，目标 >= 1.20 |
| 最大回撤 | 低于或不高于 baseline |
| 信号日留存 | 不低于 baseline 75% |
| 最长无票天数 | 不显著高于 baseline |
| `soft_buy_now` 表现 | 保持优势，不被低质量 `buy_now` 稀释 |
| 样本外结果 | 不出现明显失效 |

不允许上线的情况：

1. 真实组合收益改善只来自单个季度。
2. max5 改善但 max10 明显恶化，且原因不清楚。
3. 信号日大幅减少，出现长期无票。
4. 最大回撤扩大。
5. `near_entry` 被误纳入生产排行。
6. 发现未来函数或后验标签污染。

## 21. 开发任务拆分

### 阶段一：Shadow 评分

1. 新增生产评分配置。
2. 新增生产评分服务。
3. 接入优先榜结果，但不改变排序。
4. 接入策略跟踪展示字段。
5. 新增单元测试。

交付物：

```text
production_score / watch_score 字段可见
旧生产排序不变
near_entry 不产生 production_score
```

### 阶段二：回测对比

1. 回测脚本支持 `front_row_weighted` 变体。
2. 回测脚本支持 max5 / max10 真实组合。
3. 输出新 Markdown 和 JSON 报告。
4. 对比 baseline、front_row_only、weighted。
5. 输出空窗天数和跳过原因。

交付物：

```text
front-row-weighted-production-scoring-backtest-YYYY-MM-DD.md
front-row-weighted-production-scoring-backtest-YYYY-MM-DD.json
```

### 阶段三：小流量生产观察

前置条件：

1. Shadow 正常。
2. Paper 回测达标。
3. 无未来函数风险。
4. 样本外未明显失效。

小流量只放行：

```text
soft_buy_now
first_board
front_row_tier in core_leader / leader_hot / strong_follower
market_state not in high_flyer_retreat / risk_release
production_score >= 82
```

## 22. 推荐开发顺序

1. 先做配置和评分纯函数。
2. 写单元测试锁定权重和 cap。
3. 接入 Shadow 字段。
4. 跑现有测试，确认旧排序不变。
5. 改回测脚本支持 weighted 变体。
6. 跑 24 个月 max5 / max10 回测。
7. 生成对比报告。
8. 根据报告决定是否进入小流量，不在代码开发阶段提前放行。

## 23. 测试清单

后端单元测试：

1. `soft_buy_now` 分数高于同条件 `buy_now`。
2. `near_entry` 的 `production_score` 为 `null`。
3. 后排票 cap 到 68。
4. 弱市场后排 cap 到 55。
5. 退潮市场 cap 到 50。
6. 暂停生产策略不能进入生产候选。
7. 硬风险直接剔除。
8. `volume_shrink` 不触发前排额外交互加分。
9. `first_board` 前排核心票获得强加权。
10. API 缺少新字段时旧逻辑兼容。

回测测试：

1. weighted 变体能正常生成报告。
2. max5 / max10 持仓占用生效。
3. 同票持有中重复买入跳过。
4. 同策略单日最多 2 只生效。
5. 同板块最多 2 只生效。
6. 退潮市场不新开仓生效。
7. `near_entry` 不进入生产收益排行。

## 24. 风险与回滚

主要风险：

1. 权重主观性较强，容易过拟合已有报告。
2. 前排标签数据质量不足会影响排序。
3. 强行提高 `soft_buy_now` 可能降低信号频率。
4. 后排 cap 太严格可能漏掉有效后排机会。
5. 市场状态识别滞后会误杀行情修复初期机会。

回滚方式：

1. Shadow 阶段关闭新字段展示。
2. Paper 阶段只废弃回测变体，不影响生产。
3. 小流量阶段通过配置开关恢复旧排序。
4. 保留 baseline 报告作为对照。

建议配置开关：

```text
LOW_BUY_WEIGHTED_PRODUCTION_SCORING_ENABLED=false
LOW_BUY_WEIGHTED_PRODUCTION_SCORING_MODE=shadow
```

## 25. 最终交付标准

完成后必须具备：

1. 一套可配置的生产/观察双分数模型。
2. `near_entry` 与 `buy_now` / `soft_buy_now` 完全分离。
3. 前排加权、后排降权、极端后排剔除逻辑可解释。
4. 真实组合 max5 / max10 回测报告。
5. 防未来函数和防过拟合审计字段。
6. Shadow 到 Paper 到小流量的上线链路。
7. 默认不改变现有生产排序，除非显式打开配置。
