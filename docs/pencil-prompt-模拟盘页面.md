# Pencil 设计提示词：模拟盘执行台页面

> 将以下提示词直接输入 Pencil，生成模拟盘交易执行台的完整前端页面。
> 当前项目已有 TradingWorkspace.tsx 作为 shell 容器，请生成独立的 PaperTradingPage 组件及其子组件。

---

## 项目上下文

项目名称：**WEIS Quant Trading Platform / A股短线做T助手**
技术栈：React 18 + TypeScript + Vite
设计系统已定义在 `WEB_FRONTEND_UI_SPEC.md`，需严格遵循。
页面以 `PaperTradingPage` 组件形式嵌入 `TradingWorkspace` 的 `page === "paper"` 路由。

---

## 设计系统速查

**颜色变量**（请使用 CSS 变量，不要硬编码色值）：
- 页面背景：`--bg: #eef2f7`
- 深色面板/顶栏：`--bg-deep: #0b1422` / `--bg-panel: #111b2d`
- 卡片背景：`--bg-soft: rgba(255,255,255,.94)`
- 弱背景：`--bg-soft-muted: #f6f8fb`
- 主文字：`--text: #162235`
- 次级文字：`--muted: #66758a`
- 品牌强调色：`--accent: #d6a55c`（金色）
- **A股核心规则：红色代表上涨/盈利/做多（--price-up: #c62828），绿色代表下跌/亏损/做空（--price-down: #1f8b4c），灰色代表中性（--price-flat: #162235）**
- 正向/正T：`--positive: #178a5e`（深绿系）
- 反向/风险：`--negative: #c34a36`（红系）
- 观望/警告：`--warning: #a16207`（橙色）

**字体**：`"IBM Plex Sans", "Inter", "PingFang SC", "Microsoft YaHei", sans-serif`

**圆角**：小8px / 中12px / 大18px / 超大22px

**间距**：页面栅格 gap 12-16px，卡片 padding 10-14px，表格单元格 8-10px

**布局约束**：主工作区最大宽度 `min(1480px, 100%)`

**Panel 样式**：
- Studio Panel：近白底 + 浅灰蓝边框 + 弱阴影 + 可带顶部 1px 金色强调线
- Panel Header：左侧 KICKER 英文小标签（大写等宽感）+ 中文主标题 + 右侧状态 chip/按钮/更新时间

**按钮体系**：
- `primary-button`：深蓝底白字，主操作
- `ghost-button`：白底透明边框，次级操作
- `gold` class：品牌金色，特殊操作如"刷新持仓价格"
- 危险操作使用红色文字/浅红底
- 禁用态统一 opacity 0.5 + cursor not-allowed

**数字格式化规则**：
- 金额大数：`formatAmount(n)` 转万/亿显示
- 价格：`formatPrice(n)` 保留 2-3 位小数
- 百分比：`formatPct(n)` 保留 2 位小数带 %
- 整数评分/数量：`formatNumber(n)` 直接 format
- 缺失值统一显示 `--`

---

## 页面结构：模拟盘执行台

该页面包含以下区域，从上到下按网格布局排列：

### 区域 A — 页面顶栏（Hero Panel）

- 左侧 KICKER：`PAPER TRADING`
- 中文标题：**模拟盘执行台**
- 右侧操作按钮组（水平排列）：
  1. `刷新`按钮（ghost-button）—— 重新加载所有模拟盘数据
  2. `暂停模拟` / `恢复模拟`按钮 —— 根据账户状态切换文案。paused 时显示"恢复模拟"，active 时显示"暂停模拟"。使用 ghost-button
  3. `刷新持仓价格`按钮（gold class）—— 触发行情批量刷新
- 下方一行灰色说明文字：`模拟盘只用于记录策略执行效果，不代表真实交易指令。`（muted 颜色）
- 所有按钮在 loading 期间 disabled

### 区域 B — 登录面板（未登录状态，条件渲染）

当 `loginRequired === true` 时显示，取代区域 C-G：

- Panel Header：KICKER `ACCOUNT` + 标题 `登录后使用模拟盘`
- 说明文字：`模拟账户按用户隔离。登录或注册后，委托、持仓、成交和绩效会保存到你的账户下。`（muted）
- 表单区域（两列布局）：
  - 第一列：标签 `账号` + input（autoComplete="username"，绑定 `authDraft.username`）
  - 第二列：标签 `密码` + input（type="password"，autoComplete="current-password"，绑定 `authDraft.password`）
- 按钮组：
  - `登录`（primary-button）—— 调用登录 API
  - `注册并进入`（ghost-button）—— 调用注册 API
- 加载状态：按钮 disabled 且显示 loading

### 区域 C — 资产指标面板（Metric Grid）

一行 7 个指标卡片，等宽排列：

| 标签 | 数据字段 | 格式化 | 颜色语义 |
|------|---------|--------|---------|
| 总资产 | `account.total_assets` | formatAmount | 中性 |
| 可用资金 | `account.cash_available` | formatAmount | 中性 |
| 持仓市值 | `account.market_value` | formatAmount | 中性 |
| 浮动盈亏 | `account.unrealized_pnl` | formatNumber | 正数红色(up)、负数绿色(down) |
| 总收益率 | `performance.total_return_pct` | formatPct | 正数红色、负数绿色 |
| 净胜率 | `performance.net_win_rate_pct` | formatPct | 中性 |
| 状态 | `account.status` | 文字 | paused→"已暂停"（橙色），active→"运行中"（绿色） |

每个指标卡片样式：
- 浅色背景圆角卡片
- 上方灰色小字标签
- 下方大号加粗数值
- 根据 tone 字段（"up"/"down"/"neutral"）切换文字颜色

### 区域 D — 录入模拟委托面板（Order Entry Form）

Panel Header：标题 `录入模拟委托`

表单采用 2 列 × 4 行的网格布局，最后一行全宽：

**第一行：**
- 左：标签 `代码` + text input（v-model `draft.symbol`）
- 右：标签 `名称` + text input（v-model `draft.name`）

**第二行：**
- 左：标签 `方向` + select（v-model `draft.side`），选项：`买入`(buy) / `卖出`(sell)
- 右：标签 `委托类型` + select（v-model `draft.order_type`），选项：`市价`(market) / `限价`(limit)

**第三行：**
- 左：标签 `数量` + text input（v-model `draft.quantity`），placeholder `100 股整数倍`
- 右：标签 `限价` + text input（v-model `draft.price`），placeholder `限价单必填`

**第四行：**
- 左：标签 `撮合现价` + text input（v-model `draft.current_price`）
- 右：标签 `策略来源` + text input（v-model `draft.strategy_key`），placeholder `如 first_board`

**全宽行：**
- 标签 `执行理由` + text input 全宽（v-model `draft.reason`）

底部：`提交模拟委托`按钮（primary-button，full width）。loading 时 disabled。

提交成功后显示成功 toast，提交被拒显示 reject_reason 红色提示。

### 区域 E — 模拟持仓面板（Positions Panel）

Panel Header：左侧标题 `模拟持仓` + 右侧灰色标签 `{n} 只`

持仓列表采用紧凑卡片列表（`stock-list compact`）：

每条持仓行显示（水平排列）：
1. **股票名称**（加粗）+ 代码（灰色小字，同一行）
2. 持仓数量 / 可卖数量（格式：`持仓 1200 / 可卖 900`）
3. 成本价 / 最新价（格式：`成本 3.450 / 现价 3.478`，用 formatPrice）
4. 浮动盈亏百分比（带颜色：正红负绿，用 formatPct）

空状态：显示 `暂无模拟持仓`（empty-state class，居中灰色文字）

每个持仓卡片左侧可有一条 3px 竖线指示颜色：
- 浮盈 → 红色线
- 浮亏 → 绿色线
- 无行情 → 灰色线

### 区域 F — 委托记录面板（Orders Panel）

Panel Header：标题 `委托记录`

列表形式展示最近 12 条委托（`line-list`）：

每条委托行显示：
1. **方向 + 代码**（加粗）：`买入 510300` 或 `卖出 300750`
2. 类型 + 状态（chips）：`市价` / `限价` + `已成交`(绿色) / `已拒绝`(红色) / `待成交`(橙色) / `已撤销`(灰色)
3. 数量（格式：`{n} 股`）
4. 成交均价（格式：`成交 {price}`，用 formatPrice）
5. 如果有 reject_reason，以红色 warn 文字显示

空状态：显示 `暂无委托`

### 区域 G — 成交与绩效面板（Trades Panel）

Panel Header：标题 `成交与绩效`

上方一行统计 pills（`context-row`）：
- 成交笔数：`performance.total_trades`
- 胜率：`performance.win_rate_pct`（formatPct）
- 平均单笔：`performance.avg_trade_return_pct`（formatPct，带颜色）
- 最大回撤：`performance.max_drawdown_pct`（formatPct，通常为负数显示绿色）

下方列表展示最近 8 条成交（`line-list`）：
每条成交行显示：
1. **方向 + 代码**：`买入 510300` 或 `卖出 300750`
2. 数量：`{n} 股`
3. 成交价：formatPrice
4. 成交时间：`trade_time`，格式化为 `YYYY-MM-DD HH:mm:ss`

空状态：显示 `暂无成交`

### 区域 H — 策略绩效面板（Strategy Performance Panel）

Panel Header：标题 `策略绩效`

表格形式（`paper-performance-table`），表头行：
| 分组 | 成交 | 胜率 | 净胜率 | 均收 | PF |

表格不显示边框，用细线分隔行。最多显示 10 条。

每行数据：
- `key`：分组名（如 `first_board`），加粗。空值显示"未标注"
- `trades`：成交笔数，整数
- `win_rate_pct`：formatPct
- `net_win_rate_pct`：formatPct
- `avg_return_pct`：formatPct，正红负绿
- `profit_factor`：formatNumber，>1 为正向

空状态：显示 `暂无策略绩效`

### 区域 I — 市场状态绩效面板（Market State Performance Panel）

Panel Header：标题 `市场状态绩效`

表格样式和字段与区域 H 完全一致，数据源为 `marketPerformance`。

空状态：显示 `暂无市场状态绩效`

---

## 交互行为

### 数据加载

- 页面首次进入时，调用 `load()` 并行请求 7 个 API（account、positions、orders、trades、performance、by-strategy、by-market-state）
- 使用 `Promise.allSettled`，部分失败不影响其他数据展示
- 加载期间显示局部 loading（对应面板内的数据区域出现浅色骨架屏），不要整页闪烁
- 加载完成后 `loading` 状态清空

### 鉴权处理

- API 返回 401 时，自动尝试 `refreshSession()` 刷新 token
- 刷新失败 → 设置 `loginRequired = true`，进入登录面板
- 登录/注册成功后 → 清空 `loginRequired`，重新 load

### 提交委托

- 前端校验：代码不为空、数量为 100 的整数倍
- 调用 `createPaperOrder` API
- 成功 → 绿色 toast "模拟委托已成交" 或显示 `reject_reason`
- 自动重新 load 数据

### 暂停/恢复

- 切换账户状态，显示 toast
- paused 时所有委托录入表单置灰（暗示不可用，但不需要强制 disabled）

### 刷新持仓价格

- 仅刷新行情，不重新加载全部数据
- 显示 loading 态

### 错误处理

- 所有 API 异常统一以红色 error toast 展示
- 网络异常显示具体错误信息
- 不因单个 API 失败阻塞整个页面

---

## TypeScript 类型定义

以下类型定义需在生成的代码中严格使用：

```typescript
// ---- Account ----
interface PaperAccount {
  id: number;
  name: string;
  initial_cash: number;
  cash_available: number;
  frozen_cash: number;
  market_value: number;
  total_assets: number;
  realized_pnl: number;
  unrealized_pnl: number;
  max_drawdown_pct: number;
  status: "active" | "paused";
  today_return_pct: number;
}

// ---- Position ----
interface PaperPosition {
  id: number;
  symbol: string;
  name: string;
  quantity: number;
  available_quantity: number;
  frozen_quantity: number;
  cost_basis: number;
  latest_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  strategy_sources: string[];
  opened_at: string;
}

// ---- Order ----
type PaperOrderStatus = "pending" | "filled" | "partial" | "rejected" | "cancelled";

interface PaperOrder {
  id: number;
  account_id: number;
  symbol: string;
  name: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  price: number | null;
  quantity: number;
  filled_quantity: number;
  avg_fill_price: number | null;
  status: PaperOrderStatus;
  reject_reason: string | null;
  source: string;
  strategy_key: string;
  reason: string;
  created_at: string;
}

// ---- Trade ----
interface PaperTrade {
  id: number;
  order_id: number;
  account_id: number;
  symbol: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  gross_amount: number;
  commission: number;
  stamp_tax: number;
  transfer_fee: number;
  net_amount: number;
  strategy_key: string;
  trade_time: string;
}

// ---- Performance ----
interface PaperPerformance {
  total_return_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  net_win_rate_pct: number;
  avg_trade_return_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  profit_factor: number | null;
  stop_loss_rate_pct: number;
  total_trades: number;
  avg_hold_days: number;
  win_loss_ratio: number | null;
}

// ---- Grouped Performance ----
interface PaperGroupedPerformance {
  key: string;
  trades: number;
  win_rate_pct: number;
  net_win_rate_pct: number;
  avg_return_pct: number;
  profit_factor: number | null;
}

// ---- Form Drafts ----
interface PaperOrderDraft {
  symbol: string;
  name: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  quantity: string;        // string 因为来自 input
  price: string;
  current_price: string;
  strategy_key: string;
  reason: string;
}

interface PaperAuthDraft {
  username: string;
  password: string;
}
```

---

## 页面 Props 接口

```typescript
interface PaperTradingPageProps {
  account: PaperAccount | null;
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  performance: PaperPerformance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  draft: PaperOrderDraft;
  authDraft: PaperAuthDraft;
  loginRequired: boolean;
  setDraft: (draft: PaperOrderDraft) => void;
  setAuthDraft: (draft: PaperAuthDraft) => void;
  loading: string;                       // 当前 loading 的 key，空字符串表示无 loading
  onRefresh: () => void;
  onRefreshQuotes: () => void;
  onSubmitOrder: () => void;
  onTogglePause: () => void;
  onLogin: () => void;
  onRegister: () => void;
}
```

---

## 格式化函数

以下函数从 `workspaceFormatters` 导入，生成代码时只需 import 并使用：

```typescript
import { formatAmount, formatNumber, formatPct, formatPrice } from "./workspaceFormatters";

// formatAmount(123456) → "12.35万"
// formatNumber(82.5) → "82.50"
// formatPct(0.086) → "8.60%"
// formatPrice(3.478) → "3.478"
```

---

## 颜色工具函数

```typescript
function accountTone(value?: number | null): "up" | "down" | "neutral" {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral";
  if (value > 0) return "up";    // 红色
  if (value < 0) return "down";  // 绿色
  return "neutral";              // 灰色
}
```

---

## 布局 CSS Class 命名

使用以下 className 体系（与项目现有 CSS 保持一致）：

- 页面网格容器：`page-grid paper-grid`
- Panel 容器：`panel paper-hero` / `panel paper-login` / `panel paper-order` / `panel paper-positions` / `panel paper-orders` / `panel paper-trades` / `panel paper-performance` / `panel paper-market-performance`
- Panel 标题区：`panel-title`
- 指标网格：`metric-grid paper-metrics`
- 单个指标卡片：`metric {tone}`（tone 为 "up"/"down"/"neutral"）
- 上下文行：`context-row`
- 信息 pill：`info-pill`
- 表单网格：`form-grid`
- 操作按钮组：`actions`
- 持仓行：`stock-list compact` + 子项 `paper-row`
- 委托/成交行：`line-list` + 子项 `paper-row`
- 绩效表格：`paper-performance-table` + `paper-performance-head` + `paper-performance-row`
- 空状态：`empty-state`
- 全宽按钮：`full` class
- 提示文字：`muted` class
- 警告文字：`warn` class
- KICKER 标签：`hint` class

---

## 状态覆盖清单

生成代码时必须覆盖以下所有状态：

| 状态 | 区域 | 表现 |
|------|------|------|
| 未登录 | B 替代 C-G | 显示登录面板，隐藏所有业务面板 |
| 加载中 | C-G | 局部骨架屏，不整页闪烁 |
| 空账户 | C | 指标全为 `--` |
| 有数据 | C-G | 正常展示 |
| 持仓为空 | E | 显示 `暂无模拟持仓` |
| 委托为空 | F | 显示 `暂无委托` |
| 成交为空 | G | 显示 `暂无成交` |
| 策略绩效为空 | H | 显示 `暂无策略绩效` |
| 市场绩效为空 | I | 显示 `暂无市场状态绩效` |
| 已暂停 | C | 状态显示"已暂停"橙色 |
| 运行中 | C | 状态显示"运行中"绿色 |
| 委托提交中 | D | 按钮 disabled + loading |
| 错误提示 | 全局 | 红色 error toast |
| 成功提示 | 全局 | 绿色 success toast |
| 刷新中 | A | 对应按钮 disabled |

---

## 响应式要求

- 桌面（>1280px）：指标面板 7 列，表单 2 列，持仓/委托/成交/绩效左右分栏
- 笔记本（1024-1280px）：指标面板 4 列 + 3 列，表单保持 2 列
- 平板（768-1024px）：指标面板 3 列，表单单列，面板上下堆叠
- 手机（<768px）：指标面板 2 列，所有面板单列全宽，表单单列，字号适当缩小

---

## 生成要求

1. 生成**完整可运行**的 React TypeScript 组件代码
2. 使用函数组件 + Hooks
3. 从 `workspaceFormatters` 导入格式化函数（不要重新实现）
4. 所有 className 使用上述命名体系
5. 严格遵循 A 股红涨绿跌的颜色规则
6. 包含所有空状态、加载状态、错误状态的处理
7. 各子组件（Metric、PositionRow、OrderRow、TradeRow、GroupedPerformanceTable、Empty 等）拆分为独立的小组件，不要写在一个巨大的 render 函数里
8. 代码注释使用中文

---

## 效果参考

生成的页面应该看起来像一个**专业金融交易工作台**，类似 Bloomberg Terminal / Wind 金融终端的简洁版：

- 信息密度高，但不拥挤
- 色系统一克制，金色作为唯一强调色
- 数据优先，装饰最小化
- 表格紧凑，无大块空白
- 操作按钮触手可及但不喧宾夺主
- 中文主文案 + 英文小标签辅助
