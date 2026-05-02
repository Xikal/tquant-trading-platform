# 内置模拟盘与 Hermes 自动模拟交易需求文档

适用项目：`gupiao`
文档日期：`2026-05-02`
文档状态：`V1 需求设计稿，可进入产品/后端/前端/Agent 方案评审`

## 1. 背景

当前项目已经具备 A 股短线做T与低吸选股的核心能力，包括：

- 持仓/自选实时监控
- 全策略优先级榜
- 低吸选股宝典
- 个股量化分析
- 回测复盘
- Web 端与 App 端展示
- Agent Safe API / MCP / Hermes / OpenClaw 的长期接入规划

下一阶段需要验证一个关键问题：

> 当前策略信号在真实 A 股交易规则约束下，是否具备稳定正期望。

为避免直接接入实盘账户带来的资金、安全、合规和误操作风险，项目应先建设**内置模拟盘**，并让 Hermes 在严格权限边界内按后端策略规则进行自动模拟交易，以积累可复盘、可统计、可优化的交易样本。

## 2. 目标

### 2.1 产品目标

- 构建项目内置模拟盘，支持账户、持仓、委托、成交、绩效统计。
- 支持 A 股 T+1、100 股整数倍、手续费、印花税、滑点、涨跌停、停牌等基础规则。
- 让 Hermes 只通过受控 API 执行模拟交易，不直接访问数据库、不直接修改策略、不直接操作服务器。
- 自动记录每一笔模拟交易的信号来源、策略依据、执行条件、失效条件和结果。
- 用模拟交易样本验证策略胜率、平均收益、止损率、回撤、盈亏比、Profit Factor。
- 为后续是否保留、优化、下架策略提供数据依据。

### 2.2 技术目标

- 模拟盘作为后端独立模块，不污染现有策略逻辑。
- Web/App 可以读取模拟账户与交易结果。
- Hermes 通过 Agent Safe API 或 MCP 工具调用模拟盘能力。
- 所有自动交易动作默认只作用于模拟盘，严禁接入实盘。
- 支持从“只读建议”逐步升级到“半自动确认”再到“全自动模拟”。

## 3. 非目标

本阶段不做：

- 不接真实券商账户。
- 不接同花顺、广发证券等实盘交易。
- 不允许 Hermes 自行发明交易规则。
- 不允许 Hermes 修改策略参数。
- 不允许 Hermes 直接访问数据库。
- 不允许 Hermes 执行 shell 命令完成交易。
- 不承诺收益，不输出“必涨”“稳赚”等表达。

## 4. 总体架构

```text
行情与策略服务
  ↓
watchlist signals / priority board / stock analysis
  ↓
内置模拟盘 Paper Trading Service
  ↓
账户 / 持仓 / 委托 / 成交 / 绩效
  ↓
Agent Safe API / MCP Tools
  ↓
Hermes Agent
  ↓
模拟交易执行 / 自动复盘 / 异常提醒
```

关键原则：

- 后端策略负责产生信号。
- 模拟盘负责按交易规则撮合与记账。
- Hermes 负责调度、执行模拟委托、总结和提醒。
- 所有交易动作必须有审计日志。

## 5. 用户角色

### 5.1 普通使用者

- 查看模拟账户资产。
- 查看模拟持仓盈亏。
- 查看模拟交易记录。
- 查看策略胜率和收益表现。
- 手动重置或暂停模拟盘。

### 5.2 策略研究者

- 查看不同策略的交易表现。
- 对比市场环境、板块热度、个股地位下的收益差异。
- 判断策略是否应保留、降级、下架或重构。

### 5.3 Hermes Agent

- 定时读取策略信号。
- 生成模拟交易计划。
- 在允许条件下调用模拟盘下单。
- 停止异常交易。
- 生成日报和复盘。

### 5.4 系统管理员

- 配置是否允许自动模拟交易。
- 配置单日最大交易次数、单股最大仓位、最大回撤暂停阈值。
- 查看 Agent 调用审计。

## 6. 核心业务流程

### 6.1 手动模拟交易流程

```text
用户查看信号
  ↓
用户点击模拟买入/模拟卖出
  ↓
后端校验资金、持仓、100 股倍数、T+1、涨跌停
  ↓
创建模拟委托
  ↓
模拟撮合
  ↓
生成成交与持仓变更
  ↓
更新绩效
```

### 6.2 Hermes 只读建议流程

```text
Hermes 定时读取信号
  ↓
读取模拟账户与持仓
  ↓
生成候选交易计划
  ↓
返回“建议模拟委托”
  ↓
不自动下单
```

适用阶段：接入初期。

### 6.3 Hermes 半自动流程

```text
Hermes 生成交易计划
  ↓
用户确认
  ↓
Hermes 调用模拟下单 API
  ↓
模拟盘执行
  ↓
生成交易记录与复盘
```

适用阶段：策略验证中期。

### 6.4 Hermes 全自动模拟流程

```text
Hermes 定时运行
  ↓
读取信号、账户、持仓、市场上下文
  ↓
按后端策略信号与固定执行规则筛选
  ↓
调用模拟盘 API 下单
  ↓
记录执行原因
  ↓
异常触发熔断
  ↓
收盘生成报告
```

适用阶段：模拟盘稳定且风控规则完善之后。

## 7. 模拟盘交易规则

### 7.1 A 股基础规则

- 买入数量必须是 100 股整数倍。
- 卖出数量不得超过可用数量。
- 当日买入股票当天不可卖，次一交易日转为可用。
- 停牌标的不可成交。
- 涨停时买入可成交概率需受限或不成交，取决于撮合模型。
- 跌停时卖出可成交概率需受限或不成交，取决于撮合模型。
- ETF 可按其交易规则单独配置，默认仍采用 100 份整数倍。

### 7.2 成本费用

默认费用参数建议：

| 项目 | 默认值 | 说明 |
|---|---:|---|
| 佣金 | 0.025% | 买卖双边 |
| 最低佣金 | 5 元 | 单笔最低 |
| 印花税 | 0.05% | 仅卖出 |
| 过户费 | 0.001% | 可配置 |
| 滑点 | 5 bps | 股票默认 |
| ETF 滑点 | 2 bps | ETF 默认 |

所有费用必须可配置，不能硬编码在策略逻辑中。

### 7.3 撮合模型

第一阶段采用简化撮合：

- 市价买入：按当前价 + 滑点成交。
- 市价卖出：按当前价 - 滑点成交。
- 限价买入：若当前价小于等于限价，则成交。
- 限价卖出：若当前价大于等于限价，则成交。
- 涨跌停、停牌、无行情时拒单。

第二阶段增强：

- 根据盘口流动性、成交额、量比估计成交概率。
- 对涨停排队、跌停排队做保守估计。
- 支持部分成交。

## 8. 数据模型

### 8.1 模拟账户 PaperAccount

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 账户 ID |
| name | string | 账户名称 |
| initial_cash | decimal | 初始资金 |
| cash_available | decimal | 可用现金 |
| frozen_cash | decimal | 冻结现金 |
| market_value | decimal | 持仓市值 |
| total_assets | decimal | 总资产 |
| realized_pnl | decimal | 已实现盈亏 |
| unrealized_pnl | decimal | 浮动盈亏 |
| max_drawdown | decimal | 最大回撤 |
| status | string | active / paused |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 8.2 模拟持仓 PaperPosition

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 持仓 ID |
| account_id | int | 账户 ID |
| symbol | string | 股票代码 |
| name | string | 股票名称 |
| quantity | int | 总持仓 |
| available_quantity | int | 可用数量 |
| frozen_quantity | int | 冻结数量 |
| cost_basis | decimal | 成本价 |
| latest_price | decimal | 最新价 |
| market_value | decimal | 市值 |
| unrealized_pnl | decimal | 浮盈亏 |
| unrealized_pnl_pct | decimal | 浮盈亏比例 |
| opened_at | datetime | 首次建仓时间 |
| updated_at | datetime | 更新时间 |

### 8.3 T+1 批次 PaperPositionLot

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 批次 ID |
| account_id | int | 账户 ID |
| symbol | string | 股票代码 |
| quantity | int | 批次数量 |
| available_date | date | 可卖日期 |
| cost_price | decimal | 批次成本 |
| source_order_id | int | 来源委托 |

用途：

- 精确处理当日买入次日可卖。
- 支持后续按批次计算收益。

### 8.4 模拟委托 PaperOrder

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 委托 ID |
| account_id | int | 账户 ID |
| symbol | string | 股票代码 |
| name | string | 股票名称 |
| side | string | buy / sell |
| order_type | string | market / limit |
| price | decimal | 委托价格 |
| quantity | int | 委托数量 |
| filled_quantity | int | 成交数量 |
| avg_fill_price | decimal | 平均成交价 |
| status | string | pending / filled / rejected / cancelled |
| reject_reason | string | 拒单原因 |
| source | string | manual / hermes / backtest |
| strategy_key | string | 策略来源 |
| signal_snapshot | json | 下单时信号快照 |
| reason | string | 下单理由 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 8.5 模拟成交 PaperTrade

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 成交 ID |
| order_id | int | 委托 ID |
| account_id | int | 账户 ID |
| symbol | string | 股票代码 |
| side | string | buy / sell |
| price | decimal | 成交价 |
| quantity | int | 成交数量 |
| gross_amount | decimal | 成交金额 |
| fee | decimal | 手续费 |
| tax | decimal | 印花税 |
| net_amount | decimal | 净金额 |
| trade_time | datetime | 成交时间 |

### 8.6 模拟绩效 PaperPerformanceSnapshot

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 快照 ID |
| account_id | int | 账户 ID |
| snapshot_date | date | 统计日期 |
| total_assets | decimal | 总资产 |
| daily_return_pct | decimal | 日收益 |
| cumulative_return_pct | decimal | 累计收益 |
| max_drawdown | decimal | 最大回撤 |
| win_rate | decimal | 胜率 |
| profit_factor | decimal | Profit Factor |
| stop_loss_rate | decimal | 止损率 |
| trade_count | int | 交易数 |

### 8.7 Agent 执行日志 PaperAgentRun

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 执行 ID |
| agent_name | string | Agent 名称 |
| mode | string | readonly / confirm / auto |
| started_at | datetime | 开始时间 |
| finished_at | datetime | 结束时间 |
| status | string | success / failed / halted |
| planned_orders | int | 计划委托数 |
| executed_orders | int | 执行委托数 |
| skipped_orders | int | 跳过委托数 |
| error_message | string | 错误 |
| summary | string | 执行摘要 |

## 9. 后端 API 需求

统一前缀建议：

```text
/api/paper
```

### 9.1 账户接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/paper/account` | GET | 获取模拟账户概览 |
| `/api/paper/account` | POST | 创建或初始化模拟账户 |
| `/api/paper/account/reset` | POST | 重置模拟账户 |
| `/api/paper/account/pause` | POST | 暂停自动模拟交易 |
| `/api/paper/account/resume` | POST | 恢复自动模拟交易 |

### 9.2 持仓接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/paper/positions` | GET | 获取模拟持仓 |
| `/api/paper/positions/{symbol}` | GET | 获取单只模拟持仓 |
| `/api/paper/positions/refresh` | POST | 刷新持仓行情与盈亏 |

### 9.3 委托与成交接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/paper/orders` | GET | 获取委托列表 |
| `/api/paper/orders` | POST | 创建模拟委托 |
| `/api/paper/orders/{order_id}` | GET | 获取委托详情 |
| `/api/paper/orders/{order_id}/cancel` | POST | 撤销委托 |
| `/api/paper/trades` | GET | 获取成交列表 |

### 9.4 绩效接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/paper/performance` | GET | 获取总体绩效 |
| `/api/paper/performance/by-strategy` | GET | 按策略统计 |
| `/api/paper/performance/by-market-state` | GET | 按市场环境统计 |
| `/api/paper/performance/by-industry` | GET | 按板块统计 |

### 9.5 Agent 专用接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/paper/agent/plan` | GET | 生成当前模拟交易计划 |
| `/api/paper/agent/execute` | POST | 执行模拟交易计划 |
| `/api/paper/agent/report` | GET | 获取 Agent 模拟交易报告 |
| `/api/paper/agent/runs` | GET | 获取 Agent 执行记录 |
| `/api/paper/agent/halt` | POST | 立即停止自动模拟 |

## 10. 关键 API 示例

### 10.1 创建模拟委托

请求：

```json
{
  "symbol": "510300",
  "side": "buy",
  "order_type": "market",
  "price": null,
  "quantity": 1000,
  "source": "hermes",
  "strategy_key": "first_board",
  "reason": "信号分 82，风险低，价格进入计划买点区。",
  "signal_snapshot": {
    "action": "positive_t",
    "signal_score": 82,
    "risk_level": "low",
    "entry_zone": "3.480-3.520",
    "stop_loss": 3.430
  }
}
```

响应：

```json
{
  "order_id": 1024,
  "status": "filled",
  "symbol": "510300",
  "side": "buy",
  "filled_quantity": 1000,
  "avg_fill_price": 3.515,
  "fee": 5.0,
  "message": "模拟委托已成交"
}
```

### 10.2 生成 Agent 交易计划

响应：

```json
{
  "generated_at": "2026-05-02 10:30:00",
  "mode": "readonly",
  "market_state": "震荡修复",
  "planned_orders": [
    {
      "symbol": "510300",
      "name": "沪深300ETF",
      "side": "buy",
      "quantity": 1000,
      "order_type": "market",
      "strategy_key": "volume_shrink",
      "confidence": 76,
      "reason": "价格接近支撑区，缩量回调，市场状态允许试仓。",
      "invalid_condition": "跌破 3.430 或板块转弱则取消。"
    }
  ],
  "skipped": [
    {
      "symbol": "002859",
      "reason": "风险等级 high，跳过自动模拟交易。"
    }
  ]
}
```

### 10.3 Agent 执行模拟交易计划

请求：

```json
{
  "mode": "auto",
  "max_orders": 5,
  "dry_run": false,
  "confirm_token": null
}
```

响应：

```json
{
  "run_id": 88,
  "status": "success",
  "planned_orders": 3,
  "executed_orders": 2,
  "skipped_orders": 1,
  "summary": "本轮执行 2 笔模拟委托，跳过 1 笔高风险标的。"
}
```

## 11. Hermes 接入需求

### 11.1 Hermes 工具

建议暴露以下工具：

| 工具名 | 权限 | 用途 |
|---|---|---|
| `get_paper_account` | read | 获取模拟账户 |
| `get_paper_positions` | read | 获取模拟持仓 |
| `get_watchlist_signals` | read | 获取持仓做T信号 |
| `get_priority_board` | read | 获取全策略优先级榜 |
| `get_paper_trade_plan` | read | 生成模拟交易计划 |
| `execute_paper_trade_plan` | write_simulation | 执行模拟交易计划 |
| `get_paper_performance` | read | 获取模拟盘绩效 |
| `get_paper_agent_report` | read | 获取模拟交易报告 |
| `halt_paper_agent` | write_simulation | 停止自动模拟交易 |

### 11.2 Hermes 系统提示词要求

Hermes 必须遵守：

- 你只能进行模拟盘交易。
- 你不能接触真实交易账户。
- 你不能发明买卖规则。
- 你必须基于后端返回的信号、买点、止损、仓位、风险等级执行。
- 你必须跳过 high risk 标的。
- 你必须跳过 blocking_rules 非空的标的。
- 你必须遵守单轮最大委托数、单日最大委托数、单股最大仓位。
- 你必须记录每笔交易理由。
- 接口异常、行情过期、连续失败时必须停止交易。
- 输出只能使用“模拟交易”“倾向”“验证”，不能使用“稳赚”“保证收益”。

### 11.3 Hermes 执行频率

建议：

| 时间段 | 频率 | 说明 |
|---|---:|---|
| 09:25-09:30 | 只读 | 不自动交易 |
| 09:30-10:30 | 每 60 秒 | 主要执行窗口 |
| 10:30-11:30 | 每 120 秒 | 降低频率 |
| 13:00-14:30 | 每 120 秒 | 观察与执行 |
| 14:30-14:55 | 每 60 秒 | 尾盘策略窗口 |
| 14:55 后 | 只读 | 不新增买入，可做风控复盘 |

## 12. 自动模拟交易规则

### 12.1 通用准入

必须同时满足：

- 模拟账户状态为 active。
- 当前不是熔断状态。
- 行情数据未过期。
- 标的未停牌。
- 委托数量为 100 股整数倍。
- 单轮委托数未超限。
- 单日委托数未超限。
- 单股仓位未超限。
- 策略信号包含明确止损。

### 12.2 正T模拟买入准入

建议条件：

- `action = positive_t` 或今日T倾向为 `positive_t`。
- `signal_score >= 75`。
- `tradability_score >= 70`。
- `risk_level != high`。
- `blocking_rules` 为空。
- 当前价格在买点区或距离买点区不超过阈值。
- 市场状态不是退潮或高风险。
- 所属板块不是明显退潮。
- 账户现金足够。

### 12.3 反T模拟卖出准入

建议条件：

- `action = negative_t` 或今日T倾向为 `negative_t`。
- `available_quantity > 0`。
- `signal_score >= 70`。
- 当前价格接近卖出区或冲高区。
- 板块分歧、放量滞涨或市场风险抬升。
- 卖出后保留必要底仓。

### 12.4 观望与禁用

必须跳过：

- `risk_level = high`
- `blocking_rules` 非空
- 无止损
- 无行情
- 行情过期
- 停牌
- 跌停卖出
- 涨停追买
- 当日已触发最大亏损
- Agent 连续失败达到阈值

## 13. 风控与熔断

### 13.1 账户级风控

建议默认：

- 单日最大模拟亏损：2%
- 单只标的最大仓位：20%
- 单策略最大仓位：40%
- 单日最大委托数：20
- 单轮最大委托数：5
- 连续失败次数：3 次后停止 Agent
- 连续止损次数：3 次后停止当日新增买入

### 13.2 策略级风控

- 策略 20 笔样本内净胜率低于 45%，暂停自动执行。
- 策略止损率高于 35%，暂停自动执行。
- 策略平均净收益小于 0，暂停自动执行。
- 退潮期只允许观察，不允许自动低吸。

### 13.3 Agent 熔断

触发条件：

- 后端 `/readyz` 异常。
- 行情时间过期。
- 下单接口连续失败。
- 生成计划为空但 Agent 仍尝试下单。
- 单日亏损超限。
- 同一标的重复下单超限。

熔断后：

- 停止自动模拟交易。
- 生成异常报告。
- 推送提醒。

## 14. 绩效评估

### 14.1 总体指标

必须统计：

- 总收益率
- 年化收益率，可选
- 最大回撤
- 胜率
- 净胜率
- 平均单笔收益
- 平均盈利
- 平均亏损
- 盈亏比
- Profit Factor
- 止损率
- 交易次数
- 平均持仓周期

### 14.2 分组指标

必须支持：

- 按策略分组
- 按市场状态分组
- 按板块分组
- 按买入时间段分组
- 按正T/反T/观望倾向分组
- 按信号分区间分组
- 按风险等级分组

### 14.3 样本要求

建议：

- 单策略少于 50 笔，只能作为观察。
- 单策略 50-200 笔，作为灰度验证。
- 单策略超过 200 笔，才可考虑生产权重提升。
- 必须做样本外验证。

## 15. Web/App 展示需求

### 15.1 Web 端

建议新增或扩展：

- 模拟账户概览页
- 模拟持仓列表
- 模拟委托/成交记录
- 策略绩效面板
- Hermes 自动模拟执行记录
- 熔断与异常日志

重点展示：

- 总资产
- 今日盈亏
- 累计收益
- 最大回撤
- 当前持仓
- 可用数量
- 成本价
- 当前价
- 浮盈亏
- 策略来源
- 最近交易理由

### 15.2 App 端

建议保持轻量：

- 模拟账户资产
- 模拟持仓
- 今日 Agent 交易记录
- 今日风险提醒
- 一键暂停自动模拟

App 不建议展示复杂回测细节。

## 16. Agent Safe API / MCP 集成

模拟盘工具应纳入统一 Tool Registry：

- `get_paper_account`
- `get_paper_positions`
- `get_paper_orders`
- `create_paper_order`
- `get_paper_performance`
- `get_paper_trade_plan`
- `execute_paper_trade_plan`
- `halt_paper_agent`

权限建议：

| 工具 | 权限 |
|---|---|
| 查询类 | read |
| 创建模拟委托 | write_simulation |
| 执行交易计划 | write_simulation |
| 停止 Agent | write_simulation |
| 重置账户 | dangerous |

默认：

- `read` 开启。
- `write_simulation` 需要显式配置开启。
- `dangerous` 默认关闭。

## 17. 实施阶段

### 第一阶段：内置模拟盘基础能力

交付：

- 账户、持仓、委托、成交模型。
- 基础撮合。
- T+1 规则。
- 手续费、印花税、滑点。
- 手动模拟下单 API。
- 账户与持仓查询 API。

验收：

- 可以手动买入。
- 当日买入不可卖。
- 次日转可卖。
- 卖出不能超过可用数量。
- 资金、持仓、成本价计算正确。

### 第二阶段：绩效统计

交付：

- 总体绩效。
- 按策略绩效。
- 按市场状态绩效。
- 按板块绩效。
- 交易明细复盘。

验收：

- 能看到胜率、平均收益、最大回撤、止损率。
- 能区分策略表现。

### 第三阶段：Agent 只读计划

交付：

- `/api/paper/agent/plan`
- Hermes 读取但不执行。
- 生成候选模拟委托计划。

验收：

- Hermes 能输出模拟交易计划。
- 不会自动下单。

### 第四阶段：半自动模拟

交付：

- 用户确认后执行。
- 每笔交易记录 Agent reason。
- 支持一键暂停。

验收：

- 用户确认前不会下单。
- 执行记录可追溯。

### 第五阶段：全自动模拟

交付：

- 定时自动执行。
- 熔断机制。
- 单日限额。
- 收盘报告。

验收：

- Agent 只在模拟盘操作。
- 风控触发后停止。
- 每日生成报告。

### 第六阶段：策略反馈闭环

交付：

- 根据模拟交易表现标记策略状态。
- 低效策略自动降权或暂停模拟。
- 生成策略优化建议。

验收：

- 能明确看到哪些策略有正期望，哪些需要下架。

## 18. 测试要求

### 18.1 单元测试

必须覆盖：

- 买入资金校验。
- 卖出可用数量校验。
- 100 股整数倍校验。
- T+1 可用数量转换。
- 费用计算。
- 成本价更新。
- 止损触发统计。
- 最大回撤计算。
- Agent plan 生成。
- Agent execute 权限控制。

### 18.2 集成测试

必须覆盖：

- 从信号到模拟委托。
- 从委托到成交。
- 从成交到持仓。
- 从持仓到绩效。
- Agent 调用只读计划。
- Agent 自动执行被权限开关阻止。

### 18.3 回归测试

确保不影响：

- `/api/watchlist/signals`
- `/api/screeners/low-buy/priority-board`
- `/api/analyze`
- `/api/app/home`
- Web/App 现有功能

## 19. 安全要求

- 默认不启用自动模拟交易。
- 默认不启用 write_simulation 工具。
- 重置账户属于 dangerous 操作。
- 所有 Agent 执行必须记录审计。
- 所有敏感字段脱敏。
- Agent 不接真实账户。
- Agent 不保存券商密码。
- Agent 不执行服务器命令。
- Agent 不直接访问数据库。

## 20. 验收标准

V1 完成标准：

- 可以创建模拟账户。
- 可以查询模拟账户与持仓。
- 可以手动创建模拟委托。
- 能正确处理买入、卖出、T+1、费用、成本价。
- 可以查看成交记录。
- 可以查看基础绩效。
- 可以生成 Agent 模拟交易计划。
- Hermes 可以只读调用计划接口。
- 自动执行默认关闭。
- 不影响现有 Web/App/策略接口。

V2 完成标准：

- Hermes 可在模拟盘中半自动执行。
- 支持用户确认。
- 支持熔断。
- 支持日报。
- 支持按策略统计胜率和收益。

V3 完成标准：

- Hermes 可全自动模拟交易。
- 策略表现可持续统计。
- 支持策略降权/暂停建议。
- 能形成策略优化闭环。

## 21. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| Agent 误下单 | 模拟结果失真 | 默认关闭自动执行，加入限额与熔断 |
| 策略本身无正期望 | 自动化无法改善收益 | 用绩效统计反推策略下架或优化 |
| 行情延迟 | 成交与真实情况偏差 | 标记行情时间，过期拒绝交易 |
| 撮合过于理想化 | 高估收益 | 引入滑点、涨跌停、成交概率 |
| 过拟合 | 回测好但模拟差 | 强制样本外与分市场环境统计 |
| 权限过大 | 安全风险 | Agent 只走 API，禁止数据库和 shell |

## 22. 下一步建议

优先级建议：

1. 先实现模拟账户、持仓、委托、成交。
2. 再实现 T+1、费用、成本价、基础绩效。
3. 再实现 Agent 只读交易计划。
4. 再接 Hermes 读取计划和生成日报。
5. 最后再开放半自动/全自动模拟交易。

第一阶段不要追求复杂撮合，先保证账户与交易规则正确。真正的价值在于持续积累策略执行样本，而不是让 Agent 立即“自动赚钱”。

