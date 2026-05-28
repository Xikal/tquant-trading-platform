# 策略优化与 ETF 做T 增强方案

日期：2026-05-27  
范围：A 股量化交易 Web 平台策略体系、ETF/做T、回测验收、模拟盘、Go/Rust 性能链路  
原则：只基于当前代码与文档分析；策略相关判断与生产决策仍以 Python 为真源；Go 只承担读链路/BFF 加速；Rust 只承担金融指标计算加速。

## 1. 当前策略体系完整评估

### 1.1 生产/研究边界

当前低吸策略已经有清晰分层：

- 生产核心策略：`first_board`、`volume_shrink`、`n_pattern_long_wash`、`n_pattern_short_wash`，定义在 `backend/app/services/low_buy/strategy_policy.py`。
- 生产辅助策略：`late_session_strong_support`、`core_midcap_vwap_ma5_retrace`、`sector_mainline_first_divergence_low_buy`、`mainline_limitup_shrink_retrace_reclaim`。
- 研究策略和因子策略被明确排除在强买入主路径外，研究/因子权重为 0，不参与生产强买入。

结论：生产策略边界基本合理，未发现研究策略直接污染生产强买入口径。

### 1.2 低吸与选股逻辑

当前候选生成以硬规则为主，不是纯打分：

- `backend/app/services/low_buy/candidate_rules.py` 覆盖首板回踩、缩量回踩、突破回踩、背离共振等候选规则。
- `backend/app/services/low_buy/candidate_rules_mainline.py` 覆盖尾盘强支撑、主线中军 VWAP/MA5 回踩、主线首分歧低吸、主线涨停缩量回踩再收回。
- `backend/app/services/low_buy/candidate_prefilters.py` 在进入细规则前做金额、缩量、回撤、均线、风险等预过滤。
- `backend/app/services/low_buy/candidate_scoring.py` 对候选做结构分、量价分、支撑分、热点和主线加权。

结论：低吸基础逻辑不是空壳，已经具备结构过滤、风险过滤、主线过滤和优先级排序。但当前打分仍偏启发式，尚未把期望收益、滑点后收益、容量和 Profit Factor 统一纳入排序。

### 1.3 市场状态与板块强弱

当前系统已具备市场状态和盘中 Pulse：

- `backend/app/services/low_buy/market_state_rules.py` 定义 `broad_rally`、`repair`、`low_volume_wait`、`fast_rotation`、`weight_support`、`weight_support_active`、`high_flyer_retreat`、`risk_release` 等状态。
- `backend/app/services/market/hourly_snapshot.py` 已包含 9:30、10:30、11:30、13:00、14:00、15:00 全市场小时快照窗口。
- `backend/app/services/market/pulse.py` 已把市场宽度、情绪温度、龙头强度合成盘中 Pulse。
- `backend/app/services/market/sector_relative_strength.py` 已能按板块相对强弱排序。

结论：市场强弱反馈已经落地。短板是板块轮动更偏当前截面，缺少昨日/今日主线重合度、热点衰减、高标断层速度、炸板晋级关系等连续性指标。

### 1.4 回测与验证

当前回测分析器已覆盖：

- 总收益、最大回撤、Sharpe、Sortino、Calmar、基准 alpha、Information Ratio。
- 胜率、Profit Factor、多空方向拆分、按策略拆分、拒单原因。
- Walk-forward、OOS、PBO 风险和市场状态归因。

对应文件：

- `backend/app/services/backtest/analyzer.py`
- `backend/app/services/backtest/validator.py`
- `backend/app/services/backtest/regime_walkforward.py`
- `backend/app/services/backtest/engine.py`

结论：普通低吸策略回测底座可用。ETF 做T 和 SmartT 仍缺分钟级真实回测，不能用日线代理结果替代日内策略验收。

### 1.5 ETF 与做T 当前状态

当前 ETF 做T 能力主要由以下模块组成：

- `backend/app/services/sector_etf_t0.py`：从低吸优先级榜推导行业 ETF 替代机会。
- `backend/app/services/paper/scheduler_etf.py`：基于 ETF 机会池生成模拟盘自动买入委托。
- `backend/app/services/paper/dynamic_exit.py`：对 `sector_etf_t0` 使用较短止盈/止损/时间退出。
- `backend/app/services/paper/smart_t.py`：对已有持仓做洗盘加仓。
- `backend/app/services/paper/smart_t_exit.py`：对 SmartT 当日加仓进行退出。
- `backend/app/services/paper/smart_t_backtest.py`：提供 SmartT 日线代理验证。

当前 ETF 做T 的实质是“行业 ETF 替代 + 影子跟踪 + 模拟盘候选自动买入”，还不是完整 ETF 日内 T+0 策略闭环。

## 2. 当前策略问题诊断

### P0. ETF T+0 能力识别过粗，不能直接升生产主路径

影响模块：

- `backend/app/services/paper/symbols.py`
- `backend/app/services/paper/ledger_repair.py`
- `backend/app/services/sector_etf_t0.py`
- `backend/app/services/paper/scheduler_etf.py`

证据：

- `is_etf(symbol)` 只按代码前缀 `15`、`16`、`51`、`58` 判断。
- ETF 当日可用逻辑基于 `is_etf(symbol)`。
- `SECTOR_ETF_PROXIES` 是静态行业代理列表，没有 ETF 分类、T+0 eligibility、交易规则、折溢价、盘口价差、跟踪指数等字段。

为什么是问题：

ETF 品类差异很大，宽基、行业、跨境、债券、黄金、货币、商品 ETF 的流动性、折溢价、交易时段、波动特征和适合做T程度不同。仅凭代码前缀会把品种能力判断过度简化。

业务影响：

可能把不适合日内回转、流动性不足或交易规则不匹配的 ETF 放入自动做T路径，导致模拟盘和未来生产策略产生错误信号。

修复建议：

新增 ETF universe 和交易规则能力表，至少包含：

- `symbol`
- `name`
- `category`: broad_base / sector / cross_border / bond / gold / money / commodity
- `t0_eligible`
- `settlement_rule`
- `tracking_index`
- `min_amount`
- `max_spread_bps`
- `slippage_bps`
- `premium_discount_available`
- `enabled_for_t0`

应补测试：

- `backend/tests/test_etf_universe.py`
- `backend/tests/test_etf_t0_eligibility.py`
- ETF 与普通股票当日可卖差异测试。

### P0. ETF 做T 缺少分钟级回测和真实日内闭环

影响模块：

- `backend/app/services/paper/smart_t_backtest.py`
- `backend/app/services/paper/dynamic_exit.py`
- `backend/app/services/backtest/*`
- `backend/app/services/market/minute_bar_store.py`

证据：

- `smart_t_backtest.py` 明确说明当前是日线代理验证，真实盘中分钟级回测仍需更细分时数据。
- `dynamic_exit.py` 对 `sector_etf_t0` 的退出逻辑是止盈、止损、隔日时间退出，不是完整分钟级 ETF T+0 平仓闭环。

为什么是问题：

ETF 做T 的收益来自日内小价差，手续费、滑点、盘口价差和成交约束会显著影响结果。日线代理验证无法证明日内执行可行性。

业务影响：

如果直接把 ETF 做T 自动化作为生产策略，可能高估胜率和期望收益，低估滑点、手续费和失败交易。

修复建议：

新增 ETF 专用分钟级回测引擎：

- 使用分钟线重放入场、退出、成交价、成交量约束。
- 纳入手续费、滑点、盘口价差、最小价差、成交额容量。
- 输出胜率、期望收益、Profit Factor、最大回撤、Calmar、Sharpe、换手率、容量、滑点敏感性。
- 支持参数热力图和样本外验证。

应补测试：

- `backend/tests/test_etf_t0_backtest.py`
- `backend/tests/test_etf_t0_backtest_costs.py`
- `backend/tests/test_etf_t0_backtest_oos.py`

### P1. 策略排序尚未纳入统一期望收益模型

影响模块：

- `backend/app/services/low_buy/candidate_scoring.py`
- `backend/app/services/low_buy/priority_board.py`
- `backend/app/services/low_buy/performance.py`

证据：

- 候选打分已纳入量价、支撑、热点、策略 bonus，但没有统一把策略历史期望值、Profit Factor、滑点后收益、容量、回撤惩罚作为主排序因子。

为什么是问题：

胜率高不等于期望收益高；高收益也可能由极少样本贡献。当前优先级排序还可以进一步向“可交易后的风险调整收益”靠近。

业务影响：

可能把结构漂亮但历史净边际不足、滑点敏感或容量太小的候选排到过高位置。

修复建议：

新增 `strategy_expected_edge` 层：

- 以策略、市场状态、板块、样本量为维度计算历史期望值。
- 用 Profit Factor、平均收益/平均亏损、最大不利波动、滑点后收益、容量打折。
- 不改变 buy_now/soft_buy_now 结构口径，只影响排序和建议仓位。

应补测试：

- 低样本不放大测试。
- 高胜率低盈亏比降权测试。
- 高滑点/低容量降权测试。

### P1. 板块轮动与龙头强度缺少连续性和衰减模型

影响模块：

- `backend/app/services/market/sector_relative_strength.py`
- `backend/app/services/market/pulse.py`
- `backend/app/services/low_buy/market_state_rules.py`

证据：

- 板块相对强弱可排序，但主要使用当前截面和近端日线数据。
- 历史跟进文档已记录需要补昨日/今日主线重合度、高标断层速度、炸板晋级关系。

为什么是问题：

A 股短线策略对主线延续、轮动衰减和龙头退潮高度敏感。单日强弱容易把一日脉冲误判为新主线。

业务影响：

可能在快速轮动或退潮期过早参与热点回踩，降低胜率和资金效率。

修复建议：

新增板块连续性指标：

- `mainline_overlap_1d`
- `sector_rs_persistence_3d`
- `leader_break_rate`
- `broken_board_promotion_decay`
- `hot_sector_decay_score`

应补测试：

- 单日异动不直接升主线。
- 三日延续提高主线确认。
- 龙头断层导致主线降级。

### P2. 前端 ETF 做T展示还不是专项工作台

影响模块：

- `frontend/src/features/monitor/MonitorPage.tsx`
- `frontend/src/features/paper/PaperTradingPerformance.tsx`
- `frontend/src/features/paper/PaperDetailTabs.tsx`
- `frontend/src/features/backtest/*`

证据：

- 监控页已展示行业 ETF 做T替代机会。
- 模拟盘已展示 ETF T+0 汇总绩效和影子跟踪数据。
- 但缺少 ETF 做T 机会明细、执行记录、失败原因、当日次数、参数热力图、复盘归因。

修复建议：

新增 ETF 做T 专区：

- 实时监控：机会、风险、数据质量、是否可执行。
- 策略工作台：策略状态、验收门槛、研究/生产状态。
- 模拟盘：委托、成交、退出、失败原因、当日次数、连续失败。
- 回测页：分钟回测、参数热力图、五类市场状态验证。

## 3. 策略优化建议

### 3.1 保持现有低吸结构口径不变

禁止把近期绩效、AI 结论或板块热度直接改写 `buy_now`、`soft_buy_now` 结构判断。现有文档 `docs/low-buy-strategy-mechanism.md` 明确说明绩效只影响排序和仓位，不直接替代结构层。

### 3.2 引入可交易后期望收益

新增策略排序因子：

- 历史期望收益。
- Profit Factor。
- 平均盈利 / 平均亏损。
- 最大不利波动。
- 滑点后净收益。
- 成交额容量。
- 市场状态适配度。
- 数据质量。

该层只做排序和仓位缩放，不改变原策略信号。

### 3.3 增强市场状态过滤

重点增强：

- 主线连续性。
- 龙头强度持续性。
- 板块轮动衰减。
- 高标断层速度。
- 退潮期空仓/轻仓 overlay。

### 3.4 强化动态止盈止损

按品种拆分：

- 题材股：更重视炸板、放量滞涨、VWAP 破位。
- 权重股：更重视趋势和市场状态。
- ETF：更重视 VWAP 偏离回归、盘口价差、滑点、跟踪指数。

## 4. 可新增策略设计

| 策略名称 | 适用市场 | 入场条件 | 过滤条件 | 止盈止损 | 仓位规则 | 回测指标 | 上线门槛 | 需要修改文件 | 应补测试 |
|---|---|---|---|---|---|---|---|---|---|
| 主线板块回踩二次确认低吸 | `broad_rally`、`repair`、`weight_support_active` | 主线板块 RS 靠前，个股回踩 MA5/MA10/VWAP 后重新站回，成交量缩而不死 | 过滤 `risk_release`、高炸板率、数据 stale、板块一日游 | 跌破 MA10/VWAP 或结构低点止损；冲高分批止盈 | 0.5-1.0 倍基础仓位，市场弱时降为观察 | 期望收益、PF、最大回撤、Calmar、滑点敏感性 | 五类市场 OOS 通过，且不弱于现有主线策略 baseline | `candidate_rules_mainline.py`、`market_state_rules.py`、`priority_board.py` | 主线确认、失效、OOS、排序不污染测试 |
| 龙头断板后弱转强确认 | 修复、强势分歧 | 龙头断板后重新站回开盘价/VWAP，板块不退潮，量能不过度失控 | 过滤高位 A 杀、连续放量滞涨、退潮期 | 跌破断板低点或 VWAP 失败止损；冲高分批兑现 | 研究期小仓，生产需阶段门控 | 胜率、盈亏比、最大不利波动、隔日表现 | 至少 60 个样本，Walk-forward 通过，模拟盘观察后进入生产 | `candidate_rules.py`、`signal_rules.py`、`strategy_metadata_defaults.py` | 断板识别、弱转强确认、退潮阻断 |
| 高股息/低波防守轮动 | `low_volume_wait`、`risk_release`、`weight_support` | 低波、稳定成交、高股息或防守行业强于市场 | 数据缺股息时仅研究模式；过滤流动性不足 | 趋势破位或防守溢价消失退出 | 轻仓、分散、低换手 | 回撤控制、Calmar、波动率、基准超额 | 数据字段完整，回撤显著低于普通低吸 | 新增防守因子服务、`market_state_rules.py` | 数据缺失、弱市降风险、不可直接生产测试 |
| 指数 ETF 趋势轮动 | 指数趋势明确 | 宽基 ETF MA20/MA60 向上，成交额充足，跟踪指数确认 | 过滤折溢价异常、价差过大、数据 stale | 跌破趋势线退出，移动止盈 | 单 ETF 上限，组合分散 | Sharpe、Calmar、换手率、容量 | 对比沪深300/中证500 baseline 有稳定超额 | 新增 `backend/app/services/etf/*`、`backtest/*` | ETF universe、趋势信号、回测对比 |
| 行业 ETF 相对强弱轮动 | 板块轮动清晰 | 行业 ETF RS 强于宽基，板块强度连续，成交额充足 | 过滤单日异动和主线衰减 | RS 跌出阈值或 VWAP/均线破位退出 | 按行业分散，单行业上限 | RS 稳定性、PF、最大回撤、滑点敏感性 | 不弱于现有 `sector_etf_t0` 影子样本 | `sector_relative_strength.py`、`sector_etf_t0.py` | 板块持续性、行业轮动、ETF 映射 |
| ETF 日内均值回归做T | 高流动性宽基/行业 ETF 震荡 | 分钟价偏离 VWAP/布林下轨，RSI 低位修复，成交量不失真 | 过滤趋势单边、价差过大、成交不足、stale | 回归 VWAP/中轨止盈，跌破阈值止损 | 最大日内次数，单笔低仓位 | 分钟级期望收益、PF、滑点敏感性 | 分钟回测 + OOS + 模拟盘观察通过 | `minute_bar_store.py`、新增 `etf_t0_signal.py` | VWAP、RSI、费用、成交约束 |
| ETF VWAP 偏离回归做T | 高流动性 ETF | 偏离 VWAP 达阈值后出现回归确认 | 过滤盘口价差大、跟踪指数反向、折溢价异常 | 回归 VWAP 或达到最小净收益退出 | 按偏离幅度和流动性缩放 | 净收益、胜率、失败连续性 | 参数稳定，不依赖单一最优阈值 | Rust `vwap` 加速、Python 信号服务 | Rust parity、Python fallback、信号边界 |
| ETF 动态网格做T | 低波高流动 ETF | 波动率稳定，网格间距覆盖费用和滑点 | 过滤趋势单边、成交额不足、连续失败 | 每层止损/止盈，日亏暂停 | 最大网格层数、最大资金占用 | 热力图、容量、最大回撤 | 热力图稳定区间通过，模拟盘观察 | 新增 `etf_grid.py`、`etf_t0_backtest.py` | 网格成交、费用覆盖、风控暂停 |
| 持仓股底仓做T增强 | 已有底仓个股 | 只基于可卖底仓，结合 VWAP、量能、分时结构 | 禁止卖出当日新增仓；过滤数据 stale | 保护底仓，失败次数暂停 | 不增加总风险暴露或受上限约束 | 做T净收益、失败率、底仓保护率 | 与现有 SmartT baseline 对比通过 | `smart_t.py`、`smart_t_exit.py`、`dynamic_exit.py` | T+1、底仓保护、重复交易限制 |
| 市场退潮期空仓/轻仓策略 | `risk_release`、`high_flyer_retreat` | 市场宽度弱、情绪退潮、龙头断层 | 不主动开新仓，仅允许风控退出和极少数防守策略 | 以风险退出为主 | 空仓或极轻仓 | 回撤降低、错失收益可控 | 弱市回撤显著降低，强反弹不严重滞后 | `market_state_rules.py`、`scheduler.py` | 阻断、轻仓、恢复条件 |

## 5. ETF 与做T模块增强方案

### 5.1 ETF 池分类

新增 ETF 池分类：

- 宽基 ETF
- 行业 ETF
- 跨境 ETF
- 债券 ETF
- 黄金 ETF
- 货币 ETF
- 商品 ETF

每类配置不同的：

- 允许交易时段。
- T+0 能力。
- 最小成交额。
- 最大盘口价差。
- 默认滑点。
- 适用策略。
- 是否允许自动交易。

### 5.2 T+0 能力识别

规则：

- 只有 `t0_eligible=true` 且 `enabled_for_t0=true` 的 ETF 才进入 ETF T0 策略。
- 个股只能基于已有可卖底仓做T，不能把当日买入股数当成可卖。
- ETF 同样要检查流动性、盘口价差、数据 stale 和风险暂停状态。

### 5.3 ETF 行情数据

必须补齐：

- 分钟线。
- 成交额。
- 盘口价差。
- 折溢价。
- 跟踪指数。
- 流动性评分。
- 滑点估算。
- 数据质量。

Go `market-read-service` 适合做批量 quote、分钟快照读取和 data_quality 聚合，但不能做策略判断。

### 5.4 ETF 做T信号

首批信号：

- VWAP 偏离回归。
- 布林带下轨/上轨回归。
- RSI 超卖修复。
- 分时趋势转折。
- 成交量异常过滤。
- 跟踪指数联动确认。

Rust `tquant-rs` 可提供 RSI、VWAP、rolling、max drawdown、RankIC 等计算加速；Python 保留 fallback 和策略真源。

### 5.5 做T执行

执行类型：

- ETF 正T：先买后卖，日内回转。
- ETF 反T：先卖后买，基于已有持仓。
- 个股正T：只能在已有底仓保护下做，不能卖当日新增仓。
- 个股反T：先卖已有可卖仓，再按规则买回。

强制约束：

- 底仓保护。
- 最小价差覆盖手续费和滑点。
- 最大日内次数。
- 单日亏损暂停。
- 连续失败暂停。
- 流动性不足暂停。
- 数据 stale 禁止执行。

### 5.6 回测

新增 ETF 专用回测：

- 分钟级回放。
- 手续费/滑点/价差/成交额约束。
- 参数热力图。
- 样本外验证。
- 五类市场状态验证：牛市、震荡、熊市、退潮、强反弹。
- baseline 对比：不交易、持有 ETF、现有 `sector_etf_t0` 影子策略。

### 5.7 UI 展示

实时监控页：

- ETF 做T机会。
- 是否可执行。
- 风险原因。
- 数据质量。
- 今日剩余次数。
- 午盘/收盘复盘结论对 ETF 策略的影响。

模拟盘页：

- ETF 做T委托。
- 成交。
- 退出。
- 失败原因。
- 当日次数。
- 连续失败。
- 复盘归因。

策略工作台：

- ETF 策略状态。
- 研究/观察/小仓验证/生产状态。
- 验收门槛。

回测页：

- ETF T0 回测。
- 参数热力图。
- OOS 稳定性。
- 滑点敏感性。

## 6. 回测与验收标准

所有新增策略必须满足：

- 不只看胜率。
- 必须看期望收益、盈亏比、Profit Factor、最大回撤、Calmar、Sharpe、换手率、容量、滑点敏感性。
- 至少覆盖牛市、震荡、熊市、退潮、强反弹五类市场状态。
- 必须有 baseline 对比。
- 必须做参数稳定性分析，不能只选最优参数。
- 必须进入模拟盘观察期，再考虑生产建议。
- 自动交易必须遵守现有权限、风控和确认机制。

建议阶段门槛：

| 阶段 | 允许行为 | 进入条件 |
|---|---|---|
| research | 只展示研究结果 | 规则和数据链路完成 |
| shadow | 生成影子信号，不下单 | 历史回测初步通过 |
| paper_small | 模拟盘小仓 | OOS 通过，滑点敏感性可接受 |
| paper_normal | 模拟盘正常仓位 | 连续观察期达标 |
| production_candidate | 生产候选 | 风控、权限、告警、回滚全部完成 |

## 7. 需要修改的关键文件路径

后端：

- `backend/app/services/sector_etf_t0.py`
- `backend/app/services/paper/smart_t.py`
- `backend/app/services/paper/smart_t_exit.py`
- `backend/app/services/paper/scheduler_etf.py`
- `backend/app/services/paper/dynamic_exit.py`
- `backend/app/services/paper/symbols.py`
- `backend/app/services/market/minute_bar_store.py`
- `backend/app/services/backtest/*`
- 建议新增：`backend/app/services/etf/*`

前端：

- `frontend/src/features/monitor/MonitorPage.tsx`
- `frontend/src/features/paper/*`
- `frontend/src/features/backtest/*`
- `frontend/src/features/strategy/*`
- `frontend/src/types/market.ts`
- `frontend/src/types/paper.ts`

Go：

- `go-services/market-read-service/*`
- `go-services/bff-gateway/*`

Rust：

- `rust/tquant-rs/src/lib.rs`
- `rust/tquant-rs/src/finance_core.rs`
- `rust/tquant-rs/benches/finance.rs`

测试：

- `backend/tests/test_paper_smart_t.py`
- `backend/tests/test_paper_smart_t_backtest.py`
- `backend/tests/test_paper_auto_trading.py`
- `backend/tests/test_paper_routes.py`
- 新增 ETF 专项测试文件。

## 8. 后端、前端、回测、模拟盘、Go/Rust、缓存任务拆分

### 8.1 后端任务

1. 新增 ETF universe 服务和数据模型。
2. 替换 `is_etf` 前缀判断的生产决策用途，保留兼容兜底。
3. 新增 ETF T0 eligibility 判断。
4. 新增 ETF 分钟特征服务。
5. 新增 ETF T0 信号服务。
6. 拆分 `sector_etf_t0` 的“行业替代建议”和“可执行 ETF T0 信号”。
7. 新增 ETF 风控状态：日亏暂停、连续失败暂停、流动性暂停、stale 暂停。

### 8.2 回测任务

1. 新增 ETF T0 分钟级回测引擎。
2. 新增费用、滑点、价差、成交额约束。
3. 新增参数热力图。
4. 新增五类市场状态验证。
5. 新增 baseline 对比。
6. 回测结果进入策略工作台和回测页。

### 8.3 模拟盘任务

1. ETF 正T/反T 委托链路。
2. 个股底仓做T保护。
3. 当日次数限制。
4. 失败原因记录。
5. 做T复盘归因。
6. 风控暂停和恢复条件。

### 8.4 前端任务

1. 实时监控新增 ETF 做T机会区。
2. 模拟盘新增 ETF 做T执行记录和失败原因。
3. 策略工作台新增 ETF 策略状态卡。
4. 回测页新增 ETF T0 回测和参数热力图。
5. 设置页新增 ETF 参数和 T+0 eligibility 管理入口。

### 8.5 Go 任务

1. `market-read-service` 增加 ETF 批量 quote。
2. 增加分钟快照批量读取。
3. 增加 data_quality 聚合。
4. BFF 聚合 ETF T0 面板数据。
5. 所有 Go 服务只读，不产生策略决策。

### 8.6 Rust 任务

1. 确认 RSI、VWAP、rolling、max drawdown、RankIC parity。
2. 新增 Bollinger/rolling std 如 ETF 回测需要。
3. Python wrapper 保留 fallback。
4. CI 中执行 cargo test、benchmark、Python import/parity。
5. Rust 不直接生成策略信号。

### 8.7 数据缓存任务

1. 分钟线缓存按 `symbol + trade_date + period` 分区。
2. ETF quote 缓存带 `cached_at` 和 `data_quality`。
3. stale 数据禁止执行。
4. Go 读缓存失败时回退 Python/DB，不能返回伪 fresh。

## 9. 测试计划和验收命令

新增测试建议：

- `backend/tests/test_etf_universe.py`
- `backend/tests/test_etf_t0_eligibility.py`
- `backend/tests/test_etf_t0_signal.py`
- `backend/tests/test_etf_t0_backtest.py`
- `backend/tests/test_paper_etf_t0_execution.py`
- `backend/tests/test_etf_t0_risk_pause.py`
- `frontend/src/features/monitor/MonitorEtfT0Panel.test.tsx`
- `frontend/src/features/backtest/EtfT0BacktestPanel.test.tsx`

验收命令：

```bash
cd /Users/j/Documents/gupiao
python -m pytest backend/tests/test_low_buy_*.py backend/tests/test_paper_smart_t*.py backend/tests/test_paper_auto_trading.py backend/tests/test_paper_routes.py -q
python -m pytest backend/tests/test_etf_universe.py backend/tests/test_etf_t0_eligibility.py backend/tests/test_etf_t0_signal.py backend/tests/test_etf_t0_backtest.py -q
python scripts/verify_go_rust_performance_acceptance.py
```

```bash
cd /Users/j/Documents/gupiao/go-services/market-read-service
go test ./...
```

```bash
cd /Users/j/Documents/gupiao/go-services/bff-gateway
go test ./...
```

```bash
cd /Users/j/Documents/gupiao/rust/tquant-rs
cargo test
```

```bash
cd /Users/j/Documents/gupiao/frontend
npm test -- --run
npm run build
```

## 10. 风险清单

### 可以马上做

- ETF universe 和 T+0 eligibility。
- ETF 分类和参数配置。
- 实时监控 ETF 做T机会展示增强。
- 模拟盘 ETF 做T执行记录展示。
- Go 批量读和 data_quality 聚合。
- Rust 指标 parity 和 fallback。

### 必须先回测

- 主线板块回踩二次确认低吸。
- 龙头断板后弱转强确认。
- 高股息/低波防守轮动。
- 指数 ETF 趋势轮动。
- 行业 ETF 相对强弱轮动。
- ETF VWAP/布林/RSI 日内回归。
- ETF 动态网格。

### 暂时不能做

- 把研究策略直接升为生产策略。
- 把所有 ETF 默认视为可 T+0。
- 用日线代理结果证明日内做T。
- 绕过模拟盘风控、权限和确认机制。
- 让 Go/Rust 变成策略结果真源。
- 为了提高信号数量降低现有低吸、风控、回测、模拟盘账本一致性。

## 11. 最终交付物

第一阶段：

- ETF universe 和 T+0 eligibility。
- ETF 做T参数配置。
- ETF 数据质量和流动性检查。
- 实时监控 ETF 做T展示增强。
- 单元测试和回归测试。

第二阶段：

- ETF 分钟级信号服务。
- ETF T0 回测引擎。
- 参数热力图。
- 样本外和五类市场状态验证。

第三阶段：

- 模拟盘 ETF T0 正T/反T 执行。
- 风控暂停与恢复。
- 执行记录和复盘归因。

第四阶段：

- 策略工作台状态治理。
- 生产候选门槛。
- CI 性能验收和 Go/Rust 观测指标。

最终标准：

- 原有低吸、回测、模拟盘账本、风控、认证、权限不被破坏。
- 新增策略先研究、再影子、再模拟盘，不直接进入生产。
- ETF 做T 只对规则允许、数据 fresh、流动性合格、成本覆盖的品种执行。
- Go/Rust 真正进入生产性能链路，但不改变 Python 策略真源。
