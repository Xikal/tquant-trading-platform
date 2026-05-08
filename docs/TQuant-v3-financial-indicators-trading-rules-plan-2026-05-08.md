# TQuant v3 金融指标与交易规则整改及扩展方案

生成日期：2026-05-08

## 一、已落地整改项

### 1. Kelly 仓位接入模拟盘下单

问题：策略绩效层已有 `kelly_half_position_pct`，但模拟盘自动下单仍按固定单票上限计算。

实现：

- 全策略优先级榜补充 `kelly_half_position_pct` 与 `kelly_position_text`。
- 自动交易准入结果 `AdmissionResult` 解析信号内的半 Kelly 仓位。
- `PositionSizer` 下单仓位改为 `min(默认单票上限, 半Kelly上限)`。
- `PositionSizer` 同时接收当前持仓市值，避免已有仓位接近上限时继续加仓。
- 下单快照记录 `position_cap_pct` 与 `position_cap_source`，便于复盘。

验收口径：

- 半 Kelly 为 4% 时，10 万总资产、10 元价格只允许约 400 股。
- 已持仓达到单票上限时，不再生成买入委托。

### 2. 回测市场冲击参数化

问题：回测成交冲击成本的参与率阈值和冲击率写死在 `broker.py`。

实现：

- 新增参数命名空间 `backtest.execution`。
- 默认参数包括：
  - `market_impact_no_turnover_rate`
  - `market_impact_participation_thresholds`
  - `market_impact_rates`
  - `paper_slippage_stock_bps`
  - `paper_slippage_etf_bps`
  - `paper_slippage_mid_liquidity_bps`
  - `paper_slippage_low_liquidity_bps`
  - `paper_slippage_mid_liquidity_amount`
  - `paper_slippage_low_liquidity_amount`
- `BacktestBroker._apply_market_impact()` 改为读取运行期参数。
- `PaperMatchingEngine` 支持按成交额流动性调整滑点。

验收口径：

- 修改参数版本即可调整回测市场冲击，不需要改代码。
- 成交额低的股票模拟滑点更保守，ETF 仍使用较低滑点。

### 3. ETF T+0 行业代理映射去歧义

问题：多个 ETF 代理共享 `半导体`、`芯片` 等别名，匹配顺序会导致不确定选择。

实现：

- 新增 `market.sector_etf_t0.sector_proxy_map` 参数。
- `半导体` 精确映射到 `512480 半导体ETF`。
- `芯片` 精确映射到 `512760 芯片ETF`。
- 扩展消费、白酒、有色、稀土、地产、能源、煤炭、银行等方向。
- 匹配逻辑优先走参数化精确映射，再走只读 fallback aliases。

验收口径：

- `半导体` 与 `芯片` 不再命中同一只 ETF。
- 后续新增行业代理只需调整参数版本。

### 4. 模拟盘时间止损

问题：低吸策略已有持有建议，但模拟盘退出计划没有按策略最大持有天数退出。

实现：

- 自动退出计划读取持仓 `strategy_sources`。
- 通过 `strategy_holding_policy()` 取得策略最大持有天数。
- 持有超过策略验证窗口且浮盈未达到 2% 时，生成 `time_stop` 退出委托。
- 退出原因写入订单快照，前端可展示为“时间规则退出”。

验收口径：

- T+1/T+2 事件型策略超过验证窗口未转强会自动退出。
- 趋势修复型策略仍按自身策略窗口处理。

### 5. MACD 数据有效性标记

问题：MACD 数据不足时返回 `(0,0,0)`，容易被误解为真实 0 轴状态。

实现：

- 新增 `macd_with_validity()` 和 `macd_or_none()`。
- 量化分析指标增加 `macd_valid`。
- 样本不足时继续兼容返回 0，但同时标记 `macd_valid=false`。
- 分析输出增加假设提示：MACD 样本不足时不把 0 轴作为有效多空信号。

验收口径：

- 少于 35 根 K 线时 `macd_valid=false`。
- 前端、Agent、报告可根据该字段避免误读。

### 6. RSI 口径说明

当前 RSI 使用 Wilder 平滑口径，初始均值采用前 `period` 个涨跌幅的 SMA 种子，然后递推平滑。该口径与主流技术分析软件一致，保留不改。

## 二、可扩展金融功能实现方案

### 方向 1：波动率自适应仓位

目标：让仓位同时受 Kelly 胜率质量和个股波动率约束，避免高波动标的用同样仓位。

后端设计：

- 新增参数命名空间 `risk.volatility_sizing`：
  - `target_atr_pct`
  - `max_volatility_position_pct`
  - `min_volatility_position_pct`
  - `atr_window`
  - `volatility_cap_enabled`
- 在优先级榜 item 中补充：
  - `atr_pct`
  - `volatility_position_pct`
  - `final_position_cap_pct`
  - `position_cap_reason`
- `PositionSizer` 最终仓位：

```text
final_cap = min(default_cap, half_kelly_cap, volatility_cap, remaining_single_position_cap)
```

数据来源：

- 日线 ATR / 最新价。
- 当前持仓市值。
- 策略绩效 Kelly。

前端展示：

- 候选详情展示“仓位为什么是 X%”：Kelly 限制、波动限制、已有持仓限制。
- 模拟盘委托快照展示 `position_cap_reason`。

验收：

- 高 ATR 标的仓位自动下降。
- ETF 或低波动标的不会被异常压低。
- 回测报告中输出按 ATR 分桶的收益/回撤。

### 方向 2：ETF T+0 接入模拟盘执行追踪

目标：当个股信号存在 T+1 风险时，用行业 ETF 做 T+0 替代观察，并形成模拟盘影子绩效。

已具备基础：

- ETF T+0 API。
- 前端监控展示。
- 影子样本跟踪。
- ETF T+0 持仓批次可用日已支持当日可卖。

后续实现：

- 新增 `paper_etf_t0_orders` 或复用 `paper_orders.source=sector_etf_t0`。
- 自动交易只在以下条件都满足时生成 ETF 模拟委托：
  - ETF 机会 `bias=positive_t`。
  - `confidence >= 参数阈值`。
  - `expected_edge_pct >= 手续费滑点缓冲`。
  - 市场状态非退潮/风险释放。
  - 同 ETF 当日未重复执行。
- 卖出规则：
  - 达到 `sell_zone` 先卖。
  - 跌破 `stop_loss` 退出。
  - 当日尾盘未达目标则按收盘价模拟退出或保留到观察状态，具体由参数控制。
- 绩效报告：
  - 当日成功率。
  - T+0 净收益。
  - 未成交率。
  - 最大不利波动。
  - 交易成本占比。

前端展示：

- 模拟盘增加“ETF T+0 替代执行”分区。
- 明确显示“这是 ETF 替代方案，不是个股买入指令”。

验收：

- ETF 委托与个股委托来源清晰区分。
- ETF 当日买入后可当日卖出。
- 影子绩效和模拟成交绩效可以对账。

### 方向 3：多腿组合策略（股票 + ETF 对冲）

目标：在研究模式中验证“个股低吸 + 行业/宽基 ETF 对冲”的组合风险收益。

边界：

- 当前平台没有真实融券、期货、期权能力。
- 第一阶段只做模拟盘/研究回测，不给真实交易指令。

后端设计：

- 新增策略类型 `paired_hedge_research`。
- 多腿订单结构：
  - `legs: [{symbol, side, ratio, role}]`
  - `role=alpha_leg/hedge_leg`
- 组合计算：
  - 个股 long。
  - ETF hedge 只在研究中模拟 `sell` 或用反向收益估算。
  - 如果无法真实执行做空，则前端标记“研究估算，不可执行”。
- 风险指标：
  - 组合 beta。
  - 单腿最大回撤。
  - 对冲后净敞口。
  - 对冲成本。
  - 跟踪误差。

前端展示：

- 放在“研究模式”，不进入生产优先榜。
- 显示“模拟对冲，不代表真实可下单”。

验收：

- 不混入普通买入榜。
- 不触发自动交易。
- 回测报告明确标记是否可实际成交。

## 三、上线顺序

1. 完成当前六项金融规则整改并通过后端单测。
2. 波动率自适应仓位先接入优先级榜和模拟盘，不自动放大仓位。
3. ETF T+0 进入模拟盘影子执行，至少沉淀 60 个交易日样本。
4. 多腿组合只做研究回测，不进入生产执行。

## 四、风险控制

- 所有新增能力默认不承诺收益。
- 所有自动执行必须经过手续费、滑点、仓位和市场状态门控。
- 研究能力不得混入生产榜单。
- 外部数据缺失时必须降级为观察或不可用。
