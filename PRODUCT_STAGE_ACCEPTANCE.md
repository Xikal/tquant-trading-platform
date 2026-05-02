# 产品阶段验收清单（策略先行后）

## 1. 目标

将 `trading-quant-lead` 已落地的策略护栏，映射为可见、可配、可验证的产品能力，确保后续 UI/全栈开发不偏离策略边界。

## 2. 功能映射

### 2.1 策略引擎 -> 产品能力

- 可交易性硬过滤：
  - UI 展示 `blocking_rules`，并明确观望原因。
  - 当过滤触发时，动作强制为 `hold`，建议仓位为 `0%`。

- 动态阈值与执行成本：
  - UI 展示 `positive_threshold / negative_threshold` 与 `slippage_bps`。
  - 分析页必须可见，不允许只在日志里存在。

- 风险约束：
  - 配置页可调单笔风险、日内风险、连亏暂停。
  - 策略护栏参数可调（成交额、振幅、ATR、开盘阈值、滑点基线）。

### 2.2 配置层 -> 产品能力

- 系统配置页必须提供以下策略参数输入：
  - `strategy_min_amount_stock`
  - `strategy_min_amount_etf`
  - `strategy_min_amplitude_pct`
  - `strategy_max_amplitude_pct`
  - `strategy_max_atr_pct`
  - `strategy_open_phase_min_tradability`
  - `strategy_slippage_stock_bps`
  - `strategy_slippage_etf_bps`

- 配置保存后无需重启（除数据库 URL 切换外）。

### 2.3 监控层 -> 产品能力

- 自选监控接口单标失败不影响整页：
  - 失败标的降级为 `hold`，并返回错误信息。
  - 成功标的保持正常信号输出。

## 3. 验收用例（必须通过）

1. 分析页正常场景：
- 输入 `510300`，返回非空 `suggestion`。
- 展示滑点估计和触发阈值。

2. 分析页阻断场景：
- 将 `strategy_min_amount_etf` 调高到极大值。
- 再分析 `510300`，动作必须变为 `hold`，并出现成交额不足阻断原因。
- 参数恢复后动作恢复可交易状态。

3. 监控页容错场景：
- 自选加入无效代码。
- 监控列表正常渲染，异常标的展示 `hold + error`，其余标的正常。

4. 配置持久化场景：
- 修改策略参数并保存。
- 刷新后参数值保持一致。

## 4. 发布门槛

- `./scripts/qa_smoke.sh` 必须通过。
- 前后端构建必须通过。
- 核心四页流程（监控/分析/配置/研究）至少人工走查 1 轮。
