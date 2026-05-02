# Web 前端 UI 生成完整规格

生成日期：2026-04-28

本文档用于直接提供给 AI，生成或重构 `A股短线做T助手 / WEIS Quant Trading Platform` 的 Web 前端 UI。目标不是做营销落地页，而是生成一个可用于实盘辅助决策的高密度金融交易工作台。

## 1. 给 UI 生成 AI 的总指令

你是一个资深金融交易软件 UI 设计与前端实现助手。请根据本文档生成一个 Web 端 UI，要求：

- 面向 A 股短线做T、低吸选股、个股量化分析、信号复盘和系统配置。
- 视觉必须是专业金融工作台风格，信息密度高、结构清晰、可执行，不要做成通用 SaaS 首页。
- 保留所有中文业务文案，英文只作为小型 kicker 或模块辅助标签。
- A 股颜色语义必须遵守：红色代表上涨/盈利/强势，绿色代表下跌/回撤/风险释放，灰色代表中性。
- 优先使用紧凑卡片、表格、指标条、状态胶囊、信号徽章、弹窗详情和右侧诊断面板。
- 页面必须支持桌面大屏、笔记本和移动窄屏响应式布局。
- 所有数据都应从接口或 mock 数据驱动，不要把 UI 做成静态插画。
- 如果要生成 React 代码，建议使用 React 18 + TypeScript + Vite 风格；如果使用其他技术栈，也要保持同样的信息架构和视觉规范。

## 2. 产品定位

产品名称：

- 中文：A股短线做T助手
- 英文品牌：WEIS Quant Trading Platform

核心用途：

- 监控用户自选/持仓标的的日内做T机会。
- 展示全策略低吸优先级榜，辅助用户找到“今日更值得处理”的候选股票。
- 对单个股票进行量化分析、AI 解释、交易规则检查和执行建议。
- 通过信号复盘、回测、Walk-forward 验证策略稳定性。
- 配置数据源、数据库、大模型、风险阈值和策略阈值。

使用场景：

- 盘中快速查看：哪里有机会，哪里有风险，是否可做T。
- 盘前/盘后筛选：低吸候选、策略归因、优先级排序。
- 个股深度分析：正T/反T/观望，入场、卖出、止损、仓位。
- 策略研究：回测结果、样本外分数、交易明细、复盘样本。
- 运维配置：数据库、LLM、数据源和风控参数。

## 3. 技术与接口边界

当前 Web 前端是 React + Vite + TypeScript 单页应用。

推荐实现约束：

- 路由使用 SPA 模式。
- 默认 API 前缀为 `/api`。
- 如果部署到独立域名或移动端壳，应支持环境变量 `VITE_API_BASE_URL`。
- 管理接口可支持 `X-Admin-Token` 请求头，token 可来自 `VITE_ADMIN_API_TOKEN` 或 localStorage。
- GET 接口可以使用短 TTL 缓存和 in-flight 请求去重，避免盘中重复请求。
- 写操作成功后要主动失效相关缓存，例如自选列表、自选信号、运行时配置。

接口基础：

```text
API_BASE=/api
Native/API override=VITE_API_BASE_URL
Admin token header=X-Admin-Token
Admin token storage key=tquant.admin_api_token
```

关键接口：

```text
GET    /instruments?keyword={keyword}&kind={kind}&page=1&page_size=20
POST   /instruments/sync
GET    /watchlist
POST   /watchlist
DELETE /watchlist/{symbol}
GET    /watchlist/signals
POST   /analyze
POST   /ai/decision-support
GET    /settings
PUT    /settings
POST   /settings/database/check
POST   /settings/database/migrate
GET    /settings/runtime
GET    /replays
POST   /backtests
GET    /screeners/low-buy
GET    /screeners/low-buy/history
GET    /screeners/low-buy/quotes
GET    /screeners/low-buy/priority-board
GET    /screeners/low-buy/lifecycle
GET    /screeners/low-buy/execution-backtest
```

## 4. 全局信息架构

Web 端包含 5 个主路由：

| 路由 | 中文导航 | 英文辅助 | 页面目标 |
| --- | --- | --- | --- |
| `/` | 实时监控 | Watchlist | 监控自选/持仓股做T信号，并展示全策略优先榜摘要 |
| `/analysis` | 量化分析 | Analysis | 对单只股票做量化、AI 和执行分析 |
| `/low-buy` | 选股宝典 | Playbook | 展示低吸候选、策略榜单、归因和复盘 |
| `/research` | 研究复盘 | Research | 跑回测、看复盘样本、验证策略稳定性 |
| `/settings` | 系统配置 | Settings | 配置 LLM、数据库、数据源、风控和策略参数 |

全局顶栏信息：

- 左侧品牌：`WEIS Quant Trading Platform`
- 中文副标题：`维斯量化交易平台`
- 当前页面标签：展示当前路由对应中文名。
- 中间导航：实时监控、量化分析、选股宝典、研究复盘、系统配置。
- 右侧 desk chips：
  - `机会`：当前可执行做T数量或可执行候选数量。
  - `风险`：高风险席位数量。
  - `脉冲`：最新刷新时间，格式 `HH:mm:ss`。
- 顶栏滚动后可变为紧凑态，但导航仍可见。

全局机会提示：

- 当 `/watchlist/signals` 出现新的可执行信号时，右上或顶部浮出机会 toast。
- Toast 展示股票名、代码、动作建议和按钮 `查看分析`。
- 不要阻塞用户操作。

## 5. 视觉设计系统

整体风格：

- 浅色金融工作台背景。
- 深色顶栏与部分深色重点面板。
- 金色作为品牌强调色，不要使用默认紫色 SaaS 风格。
- 卡片边框轻、阴影弱，强调清晰排版和密集数据。
- 页面像交易系统和研究终端，不像营销网站。

核心色值：

| 变量 | 建议值 | 用途 |
| --- | --- | --- |
| `--bg` | `#eef2f7` | 页面背景 |
| `--bg-deep` | `#0b1422` | 顶栏/深色区域 |
| `--bg-panel` | `#111b2d` | 深色面板 |
| `--bg-soft` | `rgba(255,255,255,.94)` | 普通卡片 |
| `--bg-soft-muted` | `#f6f8fb` | 弱背景区域 |
| `--line` | `rgba(15,23,42,.08)` | 细分割线 |
| `--line-strong` | `rgba(15,23,42,.14)` | 强分割线 |
| `--text` | `#162235` | 主文字 |
| `--muted` | `#66758a` | 次级文字 |
| `--accent` | `#d6a55c` | 金色强调 |
| `--positive` | `#178a5e` | 正T/正向状态 |
| `--negative` | `#c34a36` | 反T/风险/卖出状态 |
| `--price-up` | `#c62828` | A股上涨红 |
| `--price-down` | `#1f8b4c` | A股下跌绿 |
| `--price-flat` | `#162235` | 平盘 |
| `--warning` | `#a16207` | 观望/警告 |

字体：

```css
font-family: "IBM Plex Sans", "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
```

圆角：

- 小圆角：8px
- 中圆角：12px
- 大圆角：18px
- 超大圆角：22px

间距：

- 页面栅格 gap：12px 到 16px。
- 普通卡片 padding：10px 到 14px。
- 高密度表格单元格 padding：8px 到 10px。
- 交易信号卡片要紧凑，不能一屏只能看一两条。

价格和涨跌色：

- `change_pct > 0`：红色。
- `change_pct < 0`：绿色。
- `change_pct = 0`：深蓝灰或黑色。
- 负收益、回撤、亏损按业务语义显示，若表示下跌本身使用绿色；若表示风险提示可使用红/橙。

## 6. 全局布局组件

### 6.1 App Shell

结构：

- `app-shell`：全局容器。
- `topbar`：粘性顶栏，深色背景。
- `workspace`：主工作区，浅色背景。
- `workspace-inner`：最大宽度 `min(1480px, 100%)`，居中。
- `page-shell`：页面主体，垂直 grid，间距 14px。

布局要求：

- 顶栏三栏：品牌区 / 导航区 / 状态区。
- 主内容宽屏最多 1480px。
- 页面加载可使用轻微 rise-in 动画，但不要过度动效。
- 数据刷新时使用局部 loading，不要整页闪烁。

### 6.2 Studio Panel

用于所有主要业务卡片。

样式：

- 背景：近白色 `rgba(255,255,255,.96)`。
- 边框：浅灰蓝。
- 顶部可有 1px 金色强调线。
- 圆角大，阴影很弱。
- 可容纳 header、summary strip、表格、表单、callout。

### 6.3 Spotlight Panel

用于重点诊断、运行快照、深色统计区域。

样式：

- 背景：深蓝黑渐变。
- 文本：浅色。
- 边框：半透明白色。
- 内部按钮使用透明白底。

### 6.4 Panel Header

组成：

- 左侧 `section-kicker`：英文小标签，大写或等宽感。
- 主标题：中文。
- 右侧可放状态 chip、按钮、更新时间。

示例：

```text
Signal Board
已持仓做T信号扫描
[6 个自选 / 09:41:23 刷新]
```

### 6.5 按钮体系

| 类型 | 用途 | 视觉 |
| --- | --- | --- |
| `primary-button` | 主操作、保存、运行、刷新 | 深蓝底白字 |
| `ghost-button` | 次级操作、查看、刷新诊断 | 白底或透明底边框 |
| `inline-button` | 删除、移除、轻量危险操作 | 红色文字或浅红底 |
| `search-pill` | 快速样本/搜索建议 | 金色弱背景，小卡片 |
| `signal-card-link` | 跳转分析页 | 小型边框按钮 |

### 6.6 状态徽章

做T动作：

| action | 中文显示 | 颜色 |
| --- | --- | --- |
| `positive_t` | 正T | 绿色系 |
| `negative_t` | 反T | 红色系 |
| `hold` | 观望 | 橙色系 |

风险等级：

| risk_level | 中文显示 |
| --- | --- |
| `low` | 低 |
| `medium` | 中 |
| `high` | 高 |

低买信号：

| buy_signal_state | 中文语义 |
| --- | --- |
| `buy_now` | 确定买入 |
| `soft_buy_now` | 谨慎买入 |
| `near_entry` | 接近买点 |
| `watch` | 继续观察 |
| `avoid` | 暂不处理 |

## 7. 数据格式化规则

通用：

- 缺失值显示 `--`。
- 时间优先显示 `HH:mm:ss`，日期显示 `YYYY-MM-DD`。
- 金额大数可显示为 `万`、`亿`，但表格内保持可读。
- 股票代码必须紧邻股票名称显示。
- 股票名称优先加粗，代码作为同一组次级信息。

数字：

- 股票价格：一般 3 位小数，必要时 2 位。
- 百分比：2 位小数并带 `%`。
- 评分：1 位小数或整数。
- 仓位：整数百分比，例如 `30%`。
- 数量：整数，A股交易数量应体现 100 股倍数约束。

文案：

- 提示信息要短，直接说明结果和下一步。
- 不要长段风险提示塞满卡片，长解释放到弹窗或 AI 解读区。
- 表格/卡片首屏必须能看到核心结论。

## 8. 数据模型摘要

### 8.1 QuoteSnapshot

用于实时行情。

```ts
{
  symbol: string
  name: string
  market: string
  instrument_type: string
  last_price: number
  change_pct: number
  change_amount: number
  open_price: number
  high_price: number
  low_price: number
  prev_close: number
  volume: number
  amount: number
  turnover_rate?: number | null
  volume_ratio?: number | null
  timestamp: string
}
```

### 8.2 WatchlistItem

用于用户自选/持仓监控。

```ts
{
  symbol: string
  name: string
  base_position: number
  available_position: number
  cost_basis?: number | null
  memo: string
  created_at?: string
}
```

### 8.3 WatchlistSignal

用于实时监控页面信号卡。

```ts
{
  symbol: string
  name: string
  base_position: number
  available_position: number
  cost_basis?: number | null
  memo: string
  signal: StrategySuggestion
  quote: QuoteSnapshot
  rules: TradingRule
  error?: string | null
}
```

### 8.4 StrategySuggestion

用于正T/反T/观望建议。

```ts
{
  action: "positive_t" | "negative_t" | "hold"
  entry_price?: number | null
  exit_price?: number | null
  position_pct: number
  stop_loss?: number | null
  risk_level: "low" | "medium" | "high"
  signal_score: number
  tradability_score: number
  confidence: number
  expected_profit_pct: number
  scenario: string
  trade_scene?: string
  trade_scene_text?: string
  buyback_trigger?: string
  reasons: string[]
  blocking_rules: string[]
  take_profit?: number | null
  strategy_notes: string
}
```

### 8.5 LowBuyPriorityBoardItem

用于全策略优先级榜。

```ts
{
  symbol: string
  name: string
  strategy_key: string
  strategy_title: string
  strategy_titles: string[]
  strategy_count: number
  latest_price: number
  change_pct: number
  quote_timestamp: string
  buy_signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid"
  buy_signal_text: string
  priority_score: number
  strategy_weight_score: number
  industry_rotation_bonus: number
  industry_rotation_text: string
  action_summary: string
  blocked_reason: string
  trigger_condition?: string
  invalid_condition?: string
  risk_tier?: "block" | "degrade" | "note"
  entry_zone_low: number
  entry_zone_high: number
  stop_loss: number
  suggested_position_pct: number
  suggested_position_text: string
}
```

### 8.6 LowBuyPriorityBoardResult

用于实时监控页的全策略榜和选股宝典榜单。

```ts
{
  as_of_date: string
  latest_trade_date: string
  updated_at: string
  total_candidates: number
  immediate_count: number
  focus_count: number
  track_count: number
  market_state: string
  market_state_text: string
  market_bonus: number
  regime_confidence: number
  state_persistence_days: number
  transition_risk: number
  stock_up_ratio: number
  stock_median_change: number
  limit_up_count: number
  limit_down_count?: number | null
  board_height: number
  promotion_ratio: number
  broken_board_ratio: number
  high_flyer_retreat_ratio: number
  hot_industries: string[]
  hot_industry_source_text: string
  mainline_lifecycle_text?: string
  portfolio_risk?: LowBuyPortfolioRisk
  items: LowBuyPriorityBoardItem[]
}
```

### 8.7 LowBuyCandidate

用于选股宝典候选卡。

核心字段：

```ts
{
  strategy_key: string
  strategy_title: string
  symbol: string
  name: string
  latest_price: number
  change_pct: number
  score: number
  entry_zone_low: number
  entry_zone_high: number
  stop_loss: number
  take_profit: number
  entry_distance_pct: number
  suggested_position_pct: number
  suggested_position_text: string
  buy_signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid"
  buy_signal_text: string
  buy_signal_hint: string
  summary_reason: string
  reasons: string[]
  risks: string[]
  tags: string[]
  position_breakdown_text?: string
  hard_risk?: LowBuyHardRisk
  exit_plan?: LowBuyExitPlan
}
```

### 8.8 AnalysisResponse

用于量化分析页。

```ts
{
  symbol: string
  instrument: Instrument
  quote: QuoteSnapshot
  rules: TradingRule
  sector: SectorSnapshot
  events: MarketEvent[]
  microstructure: MicrostructureSnapshot
  bars: KlineBar[]
  metrics: Record<string, string | number>
  suggestion: StrategySuggestion
  ai: AiInsight
  compliance_notes: string[]
  assumptions: string[]
  analysis_log_id?: number | null
}
```

### 8.9 BacktestResult

用于研究复盘页。

```ts
{
  symbol: string
  total_trades: number
  win_rate: number
  avg_pnl_pct: number
  profit_factor: number
  max_drawdown: number
  walk_forward_score: number
  trades: BacktestTrade[]
}
```

### 8.10 SettingsPayload

用于系统配置页。

```ts
{
  llm_provider: string
  llm_api_key: string
  llm_base_url: string
  llm_model: string
  data_source: string
  data_source_base_url: string
  database_url: string
  risk_max_single_loss_pct: number
  risk_max_daily_loss_pct: number
  risk_pause_after_losses: number
  event_risk_enabled: boolean
  microstructure_enabled: boolean
  strategy_min_amount_stock: number
  strategy_min_amount_etf: number
  strategy_min_amplitude_pct: number
  strategy_max_amplitude_pct: number
  strategy_max_atr_pct: number
  strategy_open_phase_min_tradability: number
  strategy_min_profit_stock_pct: number
  strategy_min_profit_etf_pct: number
  strategy_slippage_stock_bps: number
  strategy_slippage_etf_bps: number
}
```

## 9. 页面一：实时监控 Dashboard

路由：`/`

页面目标：

- 用户打开后第一时间知道：当前持仓/自选有多少，哪些可以做T，哪些高风险，全策略榜有没有新机会。
- 这个页面应是最高频盘中页面。

页面结构：

1. 盘中监控摘要 `Realtime Monitor / 盘中监控摘要`
2. 全策略优先级榜摘要 `Priority Board / 全策略优先级榜`
3. 已持仓做T信号扫描 `Signal Board / 已持仓做T信号扫描`
4. 自选/持仓录入 `Watchlist Builder / 录入底仓约束`
5. 信号详情弹窗 `SignalDetailModal`

### 9.1 盘中监控摘要

顶部大卡片，展示：

- 已持仓自选：自选/持仓标的数量。
- 可执行做T：`positive_t + negative_t` 数量。
- 主看机会：全策略榜 `immediate_count`。
- 重点观察：全策略榜 `focus_count`。
- 仅跟踪：全策略榜 `track_count`。
- 高风险席位：`risk_level === high` 数量。
- 平均质量分：所有 watchlist signal 的平均 `signal_score`。
- 上次刷新：最近 `/watchlist/signals` 更新时间。
- 优先级榜：最新全策略榜更新时间。

操作：

- `同步全市场标的`
- `手动刷新`

### 9.2 全策略优先级榜摘要

模块标题：

- Kicker：`Priority Board`
- 标题：`全策略优先级榜`
- 右侧：链接按钮 `去选股宝典`

上方市场上下文区：

- 市场状态：`market_state_text`
- 市场加分：`market_bonus`
- 状态置信度：`regime_confidence`
- 切换风险：`transition_risk`
- 状态持续天数：`state_persistence_days`
- 热点板块来源：`hot_industry_source_text`
- 热点板块列表：`hot_industries`
- 主线生命周期：`mainline_lifecycle_text`
- 组合风险：`portfolio_risk.risk_level`
- 宽度/情绪：`stock_up_ratio`、`stock_median_change`
- 涨停/跌停：`limit_up_count`、`limit_down_count`
- 连板高度：`board_height`
- 晋级率：`promotion_ratio`
- 炸板率：`broken_board_ratio`
- 高标退潮：`high_flyer_retreat_ratio`

AI 解读：

- 放置 `AiDecisionSupport` 卡片。
- task：`priority_board_summary`
- 按钮文案：`解读榜单`
- 只解释优先级、市场环境、风险，不直接替代交易规则。

榜单表格字段：

| 列 | 内容 |
| --- | --- |
| 序 | 排名 |
| 标的 | 股票名称 + 股票代码 |
| 实时价 | `latest_price` + `change_pct` |
| 状态 | `buy_signal_text` |
| 来源策略 | `strategy_titles`，可多个，紧凑显示 |
| 动作 | `action_summary` 或 `suggested_position_text` |
| 止损 | `stop_loss`、`invalid_condition` |

空状态：

- 文案：`暂无可执行候选，等待下一次全量筛选。`

### 9.3 已持仓做T信号扫描

模块标题：

- Kicker：`Signal Board`
- 标题：`已持仓做T信号扫描`
- 状态 chip：`{signals.length} 个自选 / {lastUpdated} 刷新`

筛选：

- 全部
- 可执行
- 观望
- 高风险

排序：

- 可执行优先。
- `signal_score` 高的优先。
- 同分按 symbol 排序。

信号卡片建议布局：

- 第一行：股票名称 + 股票代码、当前价、涨跌幅、动作徽章、分数。
- 第二行：入场价/卖出价、止损、预期收益、仓位建议、可交易分、风险等级。
- 第三行：场景、原因摘要、阻塞规则。
- 右侧或底部操作：`详情`、`分析`、`编辑`、`移除`。

卡片字段：

- `name`、`symbol`
- `quote.last_price`
- `quote.change_pct`
- `signal.action`
- `signal.signal_score`
- `signal.tradability_score`
- `signal.confidence`
- `signal.expected_profit_pct`
- `signal.entry_price`
- `signal.exit_price`
- `signal.stop_loss`
- `signal.position_pct`
- `signal.trade_scene_text`
- `signal.reasons`
- `signal.blocking_rules`
- `base_position`
- `available_position`
- `cost_basis`
- `rules.turnaround_mode`

交互：

- `详情` 打开信号详情弹窗。
- `分析` 跳转 `/analysis?symbol={symbol}`。
- `编辑` 展开行内持仓编辑器。
- `移除` 调用 `DELETE /watchlist/{symbol}`，成功后刷新 watchlist 和 signals。

### 9.4 录入底仓约束

模块标题：

- Kicker：`Watchlist Builder`
- 标题：`录入底仓约束`

说明卡：

- 文案：`代码、底仓、可卖、成本价决定做T信号是否可执行。`
- 补充：`A股 T+1 下，当日买入通常次日才进入可用数量。`

快速样本：

- `510300 沪深300ETF`
- `159915 创业板ETF`
- `588000 科创50ETF`

表单字段：

- 证券代码：必填。
- 名称备注：可选，若后端可自动补全则可弱化。
- 底仓数量：默认 1000。
- 可卖数量：默认 1000。
- 成本价：可选。
- 备注：可选。

提交按钮：

- `加入自选监控`

## 10. 页面二：量化分析 Analysis

路由：`/analysis`

页面目标：

- 对单个股票给出量化交易建议，辅助用户决定正T、反T或观望。
- 展示行情、K线、规则、AI 解释、执行计划和风控。

页面结构：

1. 分析 Hero `Quant + AI Workbench / 个股量化 + AI 分析页面`
2. 决策横幅 `Decision Banner`
3. 输入控制面板 `Analysis Control Panel`
4. K线/指标面板 `Analysis Chart Panel`
5. 执行计划区 `Analysis Execution Section`
6. 详情弹窗

### 10.1 Hero 和摘要

Hero 文案：

- Kicker：`Quant + AI Workbench`
- 标题：`个股量化 + AI 分析页面`
- 描述：强调量化信号、交易约束、AI 解释三者分离。

摘要卡：

- 当前价
- 涨跌幅
- 可交易分
- 信号分
- 风险等级
- 预期收益
- 规则：T0/T1、是否支持正T/反T

### 10.2 决策横幅

根据 `suggestion.action` 设置色彩和内容：

- `positive_t`：绿色边线，主标题突出 `正T`。
- `negative_t`：红色边线，主标题突出 `反T`。
- `hold`：橙色边线，主标题突出 `观望`。

展示：

- 当前动作
- 交易场景 `trade_scene_text`
- 置信度 `confidence`
- 可交易分 `tradability_score`
- 事件风险摘要
- 关键原因前三条

### 10.3 输入控制面板

表单字段：

- 证券代码：从 query `?symbol=` 初始化，没有则默认 `510300`。
- 搜索建议：调用 `/instruments`。
- 偏好策略：`auto`、`positive_t`、`negative_t`。
- 底仓数量：默认 1000。
- 可卖数量：默认 1000。
- 成本价：可选。
- 启用 AI：`include_ai`
- 启用事件风险：`include_events`
- 启用盘口增强：`include_microstructure`

操作：

- `开始分析`
- 快速样本 pill。

### 10.4 K线与指标面板

要求：

- 深色图表面板。
- 使用 K 线或可替代的蜡烛图/折线图。
- 展示 `bars`，包含 open、close、high、low、volume。
- 顶部展示关键指标，如开盘、最高、最低、成交额、振幅。
- loading 时显示图表骨架，不要空白。

### 10.5 执行计划区

展示：

- 入场价 `entry_price`
- 卖出价 `exit_price`
- 止损 `stop_loss`
- 止盈 `take_profit`
- 仓位比例 `position_pct`
- 预期收益 `expected_profit_pct`
- 交易规则 `rules.notes`
- 合规说明 `compliance_notes`
- 假设 `assumptions`
- 阻塞规则 `blocking_rules`
- AI summary、suggestions、warnings

## 11. 页面三：选股宝典 Low Buy Playbook

路由：`/low-buy`

页面目标：

- 低吸策略工作台。
- 展示全量深筛结果、候选分层、策略表现、原因风险和已买入动作。

策略 tabs：

| key | 标签 |
| --- | --- |
| `classic_retrace` | 原始低吸法 |
| `ma_support` | 均线支撑 |
| `first_board` | 首板回调 |
| `volume_shrink` | 量能低吸 |
| `breakout_support` | 位置支撑 |
| `limit_up_breakout_retrace` | 涨停突破回踩 |
| `divergence_consensus` | 分歧转一致 |
| `deep_pullback` | 深度低吸 |
| `trend_rebound` | 趋势龙回头 |

页面结构：

1. Header `Stock Playbook / 选股宝典`
2. 策略 tabs
3. summary strip
4. 最近表现 `Playbook Performance`
5. 今日主看 `Decision Desk`
6. 候选区：确定买入、接近买点、继续观察
7. 历史/收盘复盘
8. 股票详情、原因风险、买入登记弹窗

### 11.1 Header 和 summary

Header：

- Kicker：`Stock Playbook`
- 标题：`选股宝典`
- 副文案：`全量深筛 + 策略归因 + 买点执行。`

Summary metrics：

- 立即处理
- 重点观察
- 仅跟踪
- 全量深筛
- 缓存状态
- 已验证样本
- 5日达标率
- 5日平均收益
- 5日平均回撤

运行状态：

- `response_mode === full`：显示 `已就绪`
- 非 full：显示 `回退中` 或 `后台缓存仍在补齐`

### 11.2 最近表现

模块标题：

- `最近表现`
- 展示 lookback days、达标率、平均收益、回撤、profit factor。

归因分组：

- 板块归因 `sector_attribution`
- 回撤归因 `retracement_attribution`
- 市场状态归因 `market_state_attribution`
- 行业层级归因 `industry_tier_attribution`

AI 解读：

- task：`strategy_attribution`
- 按钮：`解读归因`

### 11.3 今日主看

展示：

- 主看候选：最高优先级 candidate。
- 备选候选：后 2 个。

每个候选展示：

- 股票名称 + 代码
- 最新价 + 涨跌幅
- 策略
- 评分
- 买点区
- 止损
- 建议仓位
- 行动摘要

### 11.4 候选卡片 PlaybookRow

候选分区：

- `确定买入`：`confirmed_candidates` 中 buy_now/soft_buy_now，最多重点展示 3 个。
- `接近买点`：`candidates` 中 near_entry，最多 5 个。
- `继续观察`：`candidates` 中 watch，最多 5 个，并展示省略数量。

卡片布局建议：

- 第一行：股票名称 + 股票代码、实时价格、评分、策略标签。
- 第二行：买点区、止损、确定买入/接近买点/观察信号。
- 第三行：已买入按钮、原因按钮、详情按钮、分析按钮。
- 扩展区域：summary reason、position breakdown、exit plan、hard risk。

关键字段：

- `name`
- `symbol`
- `latest_price`
- `change_pct`
- `score`
- `strategy_title`
- `summary_reason`
- `buy_signal_text`
- `entry_zone_low`
- `entry_zone_high`
- `stop_loss`
- `take_profit`
- `entry_distance_pct`
- `suggested_position_pct`
- `suggested_position_text`
- `position_breakdown_text`
- `hard_risk`
- `exit_plan`
- `reasons`
- `risks`
- `tags`

操作：

- `原因`：打开原因风险弹窗。
- `详情`：打开股票详情弹窗。
- `已买入`：打开低吸买入登记弹窗，登记到 watchlist/持仓。
- `分析`：跳转 `/analysis?symbol={symbol}`。

### 11.5 选股宝典弹窗

股票详情弹窗：

- 股票名 + 代码。
- 行情、买点、止损、止盈、仓位、策略标签。
- 趋势结构、风险、触发条件、失效条件。

原因风险弹窗：

- reasons 列表。
- risks 列表。
- hard risk tags。
- invalid condition。

已买入弹窗：

- 股票代码自动带入。
- 成本价。
- 买入股数，必须是 100 的倍数。
- 可用数量可默认为 0，符合 A 股 T+1。
- 保存后进入 watchlist/持仓监控。

## 12. 页面四：研究复盘 Research

路由：`/research`

页面目标：

- 用复盘和样本外验证检查信号稳定性。
- 主要看胜率、盈亏比、最大回撤、Walk-forward 分数。

页面结构：

1. Hero `Research + Replay / 信号复盘与 Walk-forward 验证`
2. Summary metrics
3. Backtest Runner
4. Replay Feed
5. Validation Report

### 12.1 Hero

文案：

- Kicker：`Research + Replay`
- 标题：`信号复盘与 Walk-forward 验证`
- 描述：`用复盘和样本外验证检查信号稳定性，核心只看胜率、盈亏比和回撤。`

Summary metrics：

- 回测运行次数或最近运行。
- 复盘样本数。
- 平均 PnL。
- Walk-forward 结果。

### 12.2 Backtest Runner

模块标题：

- Kicker：`Backtest Runner`
- 标题：`运行回测`

快速样本：

- 从 `RESEARCH_PRESETS` 生成 search-pill。

表单字段：

- 证券代码
- 分钟周期：`1m`、`5m`、`15m`
- 样本窗口 `lookback_bars`
- 底仓数量 `initial_position`
- Walk-forward 窗口 `walk_forward_windows`，1 到 8

按钮：

- loading：`计算中...`
- 默认：`运行回测`

提示卡：

- Kicker：`Research Gate`
- 文案：`是否进入生产观察，只看样本外分数、盈亏比和最大回撤。`
- 小字：`样本少时不放大仓位。`

### 12.3 Replay Feed

深色或重点面板。

展示：

- 样本数
- 胜样本
- 平均 PnL
- 最近 8 条复盘记录

记录格式：

```text
{symbol} | {outcome} | PnL {pnl_pct}%
```

空状态：

- `还没有复盘样本，先去分析页生成信号。`

### 12.4 Validation Report

展示：

- 回测标的标题：`{symbol} 回测结果`
- verdict：综合胜率、盈亏比、回撤和 Walk-forward 分数。
- checks grid：若干验证检查项。
- stat ribbon：
  - 总交易数
  - 胜率
  - 平均收益
  - Profit Factor
  - 最大回撤
  - Walk-forward
- 交易明细表：
  - 时间
  - 动作
  - 入场
  - 离场
  - PnL
  - 质量分

## 13. 页面五：系统配置 Settings

路由：`/settings`

页面目标：

- 管理大模型、数据库、数据源、风险控制、策略阈值。
- 让非开发用户也能知道当前系统是否准备好。

页面结构：

1. Hero `System Config / 开放式系统配置`
2. Settings Form
3. Runtime Snapshot sticky panel

### 13.1 配置表单

模块一：LLM Config / 大模型配置

字段：

- 管理令牌：当 `admin_auth_required` 为 true 时显示。
- API Key：密码输入。
- 模型协议：`auto`、`openai_compatible`、`anthropic`
- 接口地址：例如 `https://api.openai.com/v1`
- 模型名：例如 `gpt-4o-mini`

提示：

- `AI 只用于个股解释、收盘复盘和策略归因解读，不参与买入、卖出、仓位和止损硬规则。`

模块二：Data Config / 数据库与数据源

字段：

- 数据库 URL
- 数据源标识
- 数据源基础地址

操作：

- `检测数据库连接`
- `迁移 SQLite 到目标库`

连接结果展示：

- 连接状态
- 数据库类型
- 数据库名
- 当前表数

迁移结果展示：

- 迁移结果
- 复制总行数
- 重启后生效

模块三：Risk Control / 风控参数

字段：

- 单笔最大亏损 %
- 日内最大亏损 %
- 连亏暂停阈值
- 启用事件风险过滤
- 启用盘口增强模块

模块四：Strategy Guardrails / 策略阈值参数

字段：

- 股票最小成交额
- ETF 最小成交额
- 最小振幅 %
- 最大振幅 %
- 最大 ATR 比例 %
- 开盘阶段最小可交易分
- 股票最低目标盈利 %
- ETF 最低目标盈利 %
- 股票滑点基线 bps
- ETF 滑点基线 bps

保存条：

- 有修改：`存在未保存修改` + `保存配置`
- 无修改：`当前配置已同步` + `已保存`

### 13.2 Runtime Snapshot

使用 sticky 右侧面板或宽屏右栏。

展示：

- 数据库：当前数据库模式和 dialect。
- 数据源：当前数据源模式。
- AI 分析：已配置/未配置。
- 单笔风险约束。
- 日内暂停阈值。
- 股票最小成交额。
- ETF 最小成交额。
- 滑点基线。
- 最低目标盈利。

运行诊断：

- 后端数据库 backend。
- 前端产物是否挂载。
- 数据库连通性。
- runtime.env 是否存在。
- API 前缀。
- 数据源地址。
- CORS 或 ready checks 可作为高级信息。

说明列表：

- 默认数据库为本地 SQLite，适合单机开箱即用。
- 数据库切换写入 `backend/data/runtime.env`，后端重启后连接新库。
- 免费数据下盘口数据是近似估计，接入高级源后可替换。

## 14. 全局 AI 解读组件

组件名可叫 `AiDecisionSupport`。

用途：

- 解释榜单。
- 解释策略归因。
- 解释个股分析结果。

输入：

```ts
{
  task: string
  payload: Record<string, unknown>
}
```

输出展示：

- summary：多行文本，保留换行。
- suggestions：建议列表。
- warnings：警告列表。
- confidence：置信度。

约束：

- AI 解读不能改变硬规则。
- 硬规则包括买点、止损、仓位、T+1 可卖数量、风险阻塞。
- UI 要明确区分 `量化硬规则` 和 `AI 解释`。

## 15. 响应式规则

桌面宽屏：

- 顶栏三栏布局。
- Dashboard 可使用两列或主次布局。
- Analysis 可使用左侧输入、右侧图表/执行区。
- Settings 使用表单 + sticky runtime panel。
- 数据表可完整显示。

笔记本：

- 卡片压缩 padding。
- 表格横向滚动。
- Summary strip 自动换行。
- 顶栏导航保持可用。

移动窄屏：

- 顶栏压缩为品牌 + 菜单/状态。
- 页面卡片单列。
- 表格转为卡片或横向滚动。
- 信号卡片核心信息优先：名称代码、价格涨跌、动作、买点/止损、按钮。
- 不要出现横向溢出遮挡主操作。

## 16. 加载、错误、空状态

Loading：

- 卡片内部 loading。
- 按钮文案变化，例如 `刷新中...`、`计算中...`、`处理中...`。
- 图表区域使用 skeleton 或 placeholder。

Error：

- 使用红色短文本 `error-text`。
- 说明具体失败原因。
- 保留用户已输入内容。

Success：

- 使用绿色短文本 `success-text`。
- 例如：`保存成功`、`已加入监控`、`已移除`。

Empty：

- 不要留空白。
- 给出下一步操作。
- 例：`还没有复盘样本，先去分析页生成信号。`

## 17. 关键交互清单

实时监控：

- 手动刷新 watchlist signals。
- 同步 instruments。
- 筛选信号。
- 查看信号详情。
- 跳转个股分析。
- 编辑持仓。
- 移除持仓/自选。
- 新增持仓/自选。

量化分析：

- 搜索股票。
- 切换偏好策略。
- 修改底仓/可卖/成本。
- 开关 AI、事件风险、盘口增强。
- 发起分析。
- 查看图表与执行详情。

选股宝典：

- 切换策略 tab。
- 查看今日主看。
- 查看候选原因。
- 查看候选详情。
- 标记已买入。
- 跳转个股分析。
- 查看策略归因 AI 解读。

研究复盘：

- 选择快速样本。
- 设置周期、窗口、底仓。
- 运行回测。
- 查看回测报告和交易明细。

系统配置：

- 输入 admin token。
- 保存 LLM 配置。
- 检查数据库。
- 执行迁移。
- 保存风控和策略阈值。
- 刷新运行诊断。

## 18. 性能与代码质量要求

UI 生成或实现时必须注意：

- 页面组件拆分，避免单文件超大。
- API 请求统一封装。
- 格式化方法统一放在 utils。
- 价格颜色、百分比格式、时间格式统一复用。
- 大列表使用分页、限制展示数量或虚拟滚动。
- GET 请求应有短缓存，盘中接口避免重复打爆后端。
- 写操作后精准刷新相关数据。
- 弹窗、表单、卡片组件可复用。
- 不要在渲染中写复杂业务计算，放到 selector/view model。
- 不要把策略规则硬编码在 UI；UI 只展示接口结果。

## 19. 视觉验收清单

生成 UI 后检查：

- 顶栏品牌、导航、机会/风险/脉冲状态完整。
- 五个路由页面都存在。
- Dashboard 首屏能看到监控摘要、优先级榜和部分信号。
- 选股宝典不是普通列表，必须有策略 tabs、summary、最近表现、今日主看、候选分区。
- 个股分析必须有输入、决策横幅、K线/行情、执行计划。
- 研究复盘必须有回测表单、复盘 feed、验证报告。
- 系统配置必须有 LLM、数据库、风控、策略阈值和 runtime snapshot。
- A 股涨跌颜色正确：红涨绿跌。
- 股票名称和代码总是紧邻显示。
- 提示文案短、明确。
- 空状态有下一步。
- 表格在窄屏不遮挡主按钮。

## 20. 不要做的事情

- 不要做成宣传页或 landing page。
- 不要使用大面积紫色渐变。
- 不要只展示漂亮卡片但缺少交易字段。
- 不要让 AI 解读看起来像交易指令。
- 不要隐藏止损、仓位、可卖数量、阻塞规则。
- 不要把所有候选做成同等权重，必须体现优先级。
- 不要让一个页面只能看到一张超大卡片。
- 不要把错误提示写成长篇说明。

## 21. 可直接使用的 UI 生成 Prompt

可以把下面这段与本文档一起交给 UI 生成 AI：

```text
请基于《Web 前端 UI 生成完整规格》生成一个 A 股短线做T交易平台 Web UI。

必须生成 5 个页面：实时监控、量化分析、选股宝典、研究复盘、系统配置。
使用专业金融工作台风格，浅色主界面、深色顶栏、金色强调、A股红涨绿跌。
页面要高信息密度、紧凑、整齐、可执行，不要做营销页。
所有中文业务文案必须保留。
所有 UI 使用数据驱动，按文档中的接口和数据模型构造 mock 数据。
重点展示：做T信号、全策略优先级榜、买点区间、止损、仓位、风险、AI 解读、回测结果和运行配置。
请输出可运行的前端代码，并保持组件拆分、公共格式化函数复用、响应式布局和清晰状态处理。
```

## 22. 当前 Web 前端源码映射

主要入口：

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/ShellLayout.tsx`
- `frontend/src/api/base.ts`
- `frontend/src/api/client.ts`
- `frontend/src/types/index.ts`

页面：

- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/pages/LowBuyPage.tsx`
- `frontend/src/pages/ResearchPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`

功能模块：

- `frontend/src/features/dashboard/*`
- `frontend/src/features/analysis/*`
- `frontend/src/features/playbook/*`
- `frontend/src/features/research/*`
- `frontend/src/features/settings/*`
- `frontend/src/features/ai/DecisionSupport.tsx`

样式：

- `frontend/src/styles/index.css`
- `frontend/src/styles/foundation/tokens.css`
- `frontend/src/styles/foundation/chrome.css`
- `frontend/src/styles/foundation/layout.css`
- `frontend/src/styles/components/panels.css`
- `frontend/src/styles/components/actions.css`
- `frontend/src/styles/components/signals.css`
- `frontend/src/styles/components/data-views.css`
- `frontend/src/styles/pages/reporting/dashboard.css`
- `frontend/src/styles/pages/reporting/report-sections.css`
- `frontend/src/styles/pages/reporting/playbook.css`

