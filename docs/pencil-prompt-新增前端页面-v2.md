# Pencil 提示词：新增前端页面（v2）

**日期**：2026-05-02
**用途**：发给 Pencil 生成前端界面，每节为一个独立页面/组件
**项目**：TQuant 维斯量化交易平台
**技术栈**：React 18 + TypeScript + Vite

---

## 全局设计上下文（每节公用，不需重复输入）

所有页面嵌入 `TradingWorkspace` 容器，7 个 tab 导航：实时监控 → 量化分析 → 选股宝典 → 研究复盘 → 模拟盘 → 绩效。

**设计系统令牌**：
- `--bg: #eef2f7`（页面背景）
- `--bg-panel: #fff`（面板背景）
- `--text: #162235`（正文）
- `--muted: #66758a`（辅助文字）
- `--accent: #d6a55c`（金色强调）
- `--price-up: #c62828`（涨/盈利，A 股红色）
- `--price-down: #1f8b4c`（跌/亏损，A 股绿色）
- `--line: rgba(15,23,42,0.08)`（分割线）
- `--radius-md: 10px`（卡片圆角）
- `--shadow: 0 6px 18px rgba(15,23,42,0.06)`（卡片阴影）
- 字体：`"IBM Plex Sans", "PingFang SC", "Microsoft YaHei"`，数字用 `"IBM Plex Mono"`
- 字号：标题 18-20px，正文 13-14px，辅助 11-12px

**组件规范**：
- 所有数据区块使用 `.panel` class
- 面板标题样式：小号 muted eyebrow 文字 + h2 标题 + 可选 hint 副标题
- 空态：居中 muted 文字
- 加载态：骨架屏（`.skeleton-line` class）
- 错误态：浅红背景面板
- A 股红涨绿跌：`.up` class 红色、`.down` class 绿色

**布局**：CSS Grid 四列，`.page-grid` > `.panel`，响应式三档（>1320px 四列、≤1320px 两列、≤1120px 单列）。

---

## 一、市场宽度监控面板

### 功能总结

在"实时监控"页顶部嵌入一个市场情绪指标条，展示全局市场状态，帮助交易者在一秒内判断"今天适不适合做低吸"。指标数据来自新增的 `GET /api/market/breadth` 端点。此面板不是独立页面，而是 MonitorPage 顶部的横向组件。

**数据指标**（从左到右）：

| 指标 | 说明 | 展示形式 |
|------|------|---------|
| 涨跌比 | 上涨家数:下跌家数，如 2381:1523 | 数字 + 右侧红绿分割条 |
| 涨停/跌停 | 当日涨停家数和跌停家数 | 红色数字(涨停) / 绿色数字(跌停) |
| 炸板率 | 开板数 ÷ 涨停数 × 100% | 百分比 + 颜色分级：<30% 绿/30-50% 黄/>50% 红 |
| 连板梯度 | 2板/3板/4板+ 各自数量 | 三个数字块 |
| 北向净流入 | 当日沪深港通北向资金净流入(亿) | 带正负号金额，红正绿负 |
| 更新时间 | 数据刷新时间 | 小号 muted 文字 |

**交互**：全只读，无点击动作。数据每 60 秒自动刷新一次（独立于监测页的 30 秒轮询）。

---

### Pencil 提示词

```
Design a "Market Breadth" indicator strip for a Chinese A-share quantitative trading platform's real-time monitor page.

CONTEXT:
- Platform: "维斯量化交易平台" (Weisi Quant)
- This is a horizontal strip of 6 market-wide sentiment indicators, placed at the top of the Monitor Page
- Purpose: help traders instantly assess if "today is a good day for low-buy strategies"
- Tone: data-dense, dashboard-style, Bloomberg-terminal aesthetic
- All data is read-only, auto-refreshes every 60 seconds

LAYOUT:
- Full-width horizontal strip, 1 row, 6 equal-width cells
- Thin gold top border (--accent: #d6a55c) to distinguish from the monitor content below
- Light background (#f8fafc), subtle divider lines between cells
- Height: compact, ~60-72px

CELLS (left to right):

1. UP/DOWN RATIO
   - Label: "涨跌比" (small muted text)
   - Main: "2,381 : 1,523" (large bold numbers, up count in red, down count in green)
   - A mini horizontal bar below the numbers showing red/green proportion

2. LIMIT UP / LIMIT DOWN
   - Label: "涨停 / 跌停" (muted)
   - Main: two numbers side by side — "47 / 12" (limit-up in red #c62828, limit-down in green #1f8b4c)
   - Separated by a subtle slash

3. BLOW-UP RATE (炸板率)
   - Label: "炸板率" (muted)
   - Main: "32.5%" (percentage)
   - Color varies: ≤30% green (healthy), 30-50% amber (#a16207 warning color), >50% red (dangerous)
   - Sub-text: "开板 15 / 涨停 47" in smaller muted text

4. BOARD GRADIENT (连板梯度)
   - Label: "连板梯度" (muted)
   - Three small blocks side by side:
     "2板 18" | "3板 7" | "4板+ 3"
   - Each block: small label on top, count below
   - Use subtle background tints to distinguish levels

5. NORTH-BOUND FLOW (北向资金)
   - Label: "北向净流入" (muted)
   - Main: "+24.5 亿" (big number, red if positive / green if negative, with arrow icon ▲ or ▼)
   - Sub-text: "沪股通 +18.2 | 深股通 +6.3"

6. UPDATE TIME
   - Small muted text: "更新于 14:35:02"
   - No label needed
   - Right-aligned within its cell

TECHNICAL NOTES:
- Use CSS variables from the design system (--muted, --price-up, --price-down, --warning, --accent)
- Font: "IBM Plex Sans" for labels, "IBM Plex Mono" for numbers
- No charting library — pure CSS and text
- The strip should be a single div container with 6 flex children

RESPONSIVE:
- Desktop (>1320px): horizontal strip, all 6 cells visible
- Tablet (≤1320px): wrap to 2 rows of 3 cells
- Mobile (≤1120px): stack vertically, each cell full width

STATES:
- Loading: skeleton shimmer across all 6 cells
- Error: replace strip with a compact red alert bar "市场宽度数据获取失败"
- Empty: show muted placeholder values "—" in each cell
```

---

## 二、策略回测对比工作台

### 功能总结

在研究复盘页中新增一个"策略对比"子 tab（当前已有"信号复盘"和"回测"两个 tab）。该工作台同时运行多个策略在同一个回看窗口，横向对比：胜率曲线、Sharpe 比率、最大回撤、月度收益分布。目的是让交易者在选择策略时有量化依据，而非靠感觉。

**数据来源**：`GET /api/research/strategy-validation/compare?strategies=X,Y,Z&days=180`

**页面结构**（从上到下）：

| 区块 | 内容 |
|------|------|
| 控制栏 | 多选策略（checkbox 列表，11 个策略）+ 时间范围下拉（30/60/90/180/360 天）+ "开始对比"按钮 |
| 总览卡片行 | 每个选中策略一张卡片：策略名、总交易笔数、胜率、Sharpe、最大回撤、利润因子。最佳指标高亮（金色边框） |
| 胜率曲线图 | 多线折线图，x=时间，y=累计胜率%，每个策略一条线（不同颜色） |
| 收益分布图 | 按月度分组，每个策略一组箱线或柱状图，展示月收益分布 |
| 详细表格 | 全指标对比表格：策略名、交易笔数、胜率、净胜率、均收、Sharpe、最大回撤、利润因子、PBO 概率 |

---

### Pencil 提示词

```
Design a "Strategy Comparison Workbench" page section for a Chinese A-share quantitative trading platform.

CONTEXT:
- Platform: "维斯量化交易平台" (Weisi Quant)
- This is a new tab called "策略对比" inside the existing ResearchPage (研究复盘)
- Purpose: run multiple strategies side-by-side over the same backtest window, compare win rate curves, Sharpe ratios, max drawdowns, and monthly return distributions
- Target user: quantitative trader deciding which strategy to trust for live paper trading
- Tone: analytical, data-dense, professional — like QuantConnect or Zipline tearsheets

PAGE STRUCTURE (top to bottom):

1. CONTROL BAR
   - Full-width, light background (#f8fafc), rounded panel
   - Left: multi-select strategy list. Show all 11 strategies as checkboxes with Chinese names:
     ☑ 首板回调  ☑ 原始低吸法  ☑ 量能低吸  ☑ 分歧转一致
     ☐ 均线支撑  ☐ 位置支撑  ☐ 涨停突破回踩  ☐ 收盘强势承接
     ☐ 中军VWAP回踩  ☐ 主线首分歧  ☐ 深度低吸(因子)
     Selected ones have a subtle gold accent
   - Center: time range dropdown (30日 / 60日 / 90日 / 180日 / 360日)
   - Right: "开始对比" primary button (gold accent background, white text)
   - Also show "上次对比时间: 2026-05-02 15:05" in muted text below the button

2. SUMMARY CARD ROW
   - One card per selected strategy (auto-fit grid, min 220px per card)
   - Each card shows:
     - Strategy Chinese name (bold, top)
     - Trade count: "128 笔" (muted)
     - Win rate: "62.3%" (red if >50%, green if <50%)
     - Sharpe: "1.82" (bold — higher is better)
     - Max drawdown: "-8.5%" (always shown in green/down color since drawdown is negative)
     - Profit factor: "2.15"
   - The BEST value in each metric across all cards gets a gold border highlight
   - Card background: white, subtle shadow, rounded corners

3. WIN RATE CURVE CHART
   - Panel title: "累计胜率曲线" with hint "按交易日累计"
   - Multi-line chart: x-axis = trading date, y-axis = cumulative win rate (%)
   - One line per selected strategy, different color per strategy
   - Strategy color palette: red #c62828, blue #2b6cb0, green #1f8b4c, purple #805ad5, orange #c05621, teal #0d7377, gold #d6a55c
   - Use pure inline SVG (viewBox 800x250), no charting library
   - Grid lines: subtle light gray
   - Tooltip on hover: show date + strategy name + win rate value
   - Legend below chart: colored dots + strategy names

4. MONTHLY RETURN DISTRIBUTION
   - Panel title: "月度收益分布" with hint "按自然月统计，箱体为 25%-75% 区间"
   - Simplified box-and-whisker or grouped bar chart per strategy per month
   - Use pure SVG, show median as bold line, quartile range as colored box, whiskers as thin lines
   - Color: matching strategy colors from the win rate chart
   - X-axis: month labels (2025-11, 2025-12, 2026-01, ...)
   - Below chart: note "箱体越窄表示策略表现越稳定"

5. DETAIL COMPARISON TABLE
   - Panel title: "全指标对比" with hint "红色高亮 = 最佳，黄色标注 = PBO > 0.3 警告"
   - Table columns: 策略 | 交易笔数 | 胜率 | 净胜率 | 均收 | Sharpe | 最大回撤 | 利润因子 | PBO概率
   - Header row: light gray background, bold
   - Data rows: strategy names on left (bold), numbers in monospace, best value in each column highlighted with light red (#fff4f1) background
   - PBO column: if > 0.3, show in warning amber with ⚠ icon, hover shows tooltip "过拟合风险较高"
   - Sortable by clicking column headers (arrow indicator)
   - Default sort: by Sharpe descending

STATES:
- No data yet (before first compare): centered empty state "选择策略并点击开始对比，查看多策略横向回测表现"
- Loading: skeleton in the summary card row area + shimmer on chart areas
- Error: red alert panel "策略对比数据获取失败，请稍后重试"
- Single strategy selected: still show comparison UI but note "仅选中 1 个策略，建议选择 2 个以上进行横向对比"
- PBO > 0.3: warning banner above results "以下策略的 PBO 过拟合概率较高，实盘使用需谨慎：[策略名列表]"

RESPONSIVE:
- Desktop: cards in a row, 2-chart grid below table
- Tablet: cards wrap to 2 columns, charts stack vertically
- Mobile: single column, table becomes horizontal-scrollable
```

---

## 三、因子权重调节面板

### 功能总结

在系统设置页中新增"因子权重"子面板。当前因子权重硬编码在 `shared.py` 的 `LowBuyThresholds.FACTOR_WEIGHTS` 中，用户无法调整。此面板提供滑块界面，允许调节 13 个因子的权重，并实时预览 priority_board 排名变化。

**数据来源**：
- `GET /api/settings/factor-weights`（获取当前权重）
- `PUT /api/settings/factor-weights`（保存权重）
- `POST /api/screeners/low-buy/priority-board/preview?limit=5&factor_weights=...`（预览改动后的排名）

**页面结构**：

```
┌─────────────────────────────────────────────────────┐
│  因子权重调节                                        │
│  调整各因子对优先级排名的贡献度，权重越高影响越大     │
├──────────────────────┬──────────────────────────────┤
│  13 个因子滑块列表    │  实时预览                     │
│                      │                              │
│  深度低吸因子  ──●── │  当前 Top 5:                  │
│  趋势回弹因子  ──●── │  1. 000001 平安银行 89.2 →    │
│  板块集中度    ──●── │  2. 600519 贵州茅台 87.1 →    │
│  缩量质量      ──●── │  3. 000858 五粮液   85.3 ↑    │
│  缺口风险      ──●── │  4. 601318 中国平安 84.0 ↓    │
│  ...           ...   │  5. 300750 宁德时代 83.5 →    │
│                      │                              │
│  [恢复默认] [保存]    │  箭头表示与默认权重相比的      │
│                      │  排名变化 (↑升 ↓降 →不变)      │
└──────────────────────┴──────────────────────────────┘
```

**交互**：拖动滑块 → 右侧预览区实时更新（debounce 500ms）。恢复默认按钮一键重置。保存按钮将权重写入后端。

---

### Pencil 提示词

```
Design a "Factor Weight Adjustment" panel for a Chinese A-share quantitative trading platform's settings page.

CONTEXT:
- Platform: "维斯量化交易平台" (Weisi Quant)
- This is a new settings sub-panel on the Settings Page
- Purpose: allow quantitative traders to adjust the weight of 13 factors that influence strategy priority ranking
- Key interaction: drag sliders on the left → real-time preview of ranking changes on the right
- Tone: professional, precise, data-informed — like an audio equalizer but for trading signals

LAYOUT: Two-column split (60% left, 40% right)

LEFT COLUMN — Factor Sliders:

- Panel header: "因子权重" with subtitle "权重越高，该因子对优先级排名的影响越大。范围 0.0 - 2.0，默认值为灰色竖线标记。"
- 13 factor rows, each containing:

  Factor name (Chinese)     Slider track            Current value
  ─────────────────────     ──────────────────      ─────
  深度低吸因子               [====●========]         1.00
  趋势回弹因子               [======●======]         0.80
  板块集中度因子             [========●====]         1.20
  缩量质量因子               [====●========]         1.00
  缺口风险因子               [==========●==]         1.50
  波动率环境因子             [======●======]         0.70
  时间效率因子               [=====●=======]         0.60
  信号新鲜度因子             [====●========]         0.50
  板块资金流因子             [======●======]         0.70
  大单资金流因子             [===●=========]         0.40
  价格结构因子               [=======●=====]         0.90
  事件风险因子               [=====●=======]         0.60
  承接质量因子               [====●========]         0.50

- Each slider:
  - Track: light gray background, rounded
  - Active fill: gold (#d6a55c) from left edge to thumb
  - Thumb: small circle, gold border, white fill, 16px diameter
  - Default value indicator: subtle gray vertical line at the default weight position
  - Hover: thumb enlarges slightly, shows precise value tooltip
  - Labels: factor name on left (13px, bold if weight ≠ default), numeric value on right (monospace)
  - Changed rows: subtle gold left border to indicate modification

- Below sliders: two buttons side by side
  - "恢复默认" (outline/ghost button) — resets all sliders to default values
  - "保存设置" (primary gold button) — saves current weights to backend
  - Disabled state when no changes have been made

RIGHT COLUMN — Real-time Preview:

- Panel header: "排名预览" with subtitle "拖动左侧滑块后实时更新。箭头表示与默认权重相比的排名变化。"
- Shows current Top 5 from priority_board with current weights applied
- Each row:
  - Rank number (bold gold digit)
  - Stock code + name (e.g., "000001 平安银行")
  - Score (e.g., "89.2")
  - Direction arrow:
    → unchanged (muted gray)
    ↑ moved up from default-weight ranking (green, as improvement)
    ↓ moved down from default-weight ranking (red, as warning)
  - Subtle row background change for moved stocks

- Below the list: small muted note "预览基于最近一次全量扫描结果，实际盘中排名可能因行情变化而不同"
- If preview is loading (debounce during slider drag): show subtle shimmer on the list items

STATES:
- Loading initial weights: skeleton placeholder rows on left, empty right panel
- No changes made: "保存设置" button disabled, "恢复默认" hidden
- Weights saved: brief green success toast "因子权重已保存" (auto-dismiss 2s)
- Save error: red inline error "保存失败，请检查网络后重试"
- Preview error: right panel shows muted "预览数据暂不可用，权重调整仍可保存"

RESPONSIVE:
- Desktop: two columns side by side
- Tablet: stack vertically (sliders on top, preview below)
- Mobile: same stacking, slider labels shortened if needed

TECHNICAL:
- Debounce slider changes 500ms before triggering preview API call
- Use CSS variables throughout
- Slider component: native <input type="range"> with custom CSS styling
- No heavy library — pure CSS + minimal React state
```

---

## 四、交易标签系统

### 功能总结

在模拟盘交易记录中增加标签功能。每笔成交记录旁可"添加标签"，用于事后复盘分类。绩效面板扩展为按标签分组统计。

此功能涉及两个页面的改动：
1. **模拟盘页面**（PaperTradingPage）：成交记录表新增"标签"列和添加按钮
2. **绩效面板**（PerformanceDashboard）：新增"标签统计"区块

**标签预设**：按策略执行、冲动交易、追高、止损过早、按计划止盈、抄底过早、日内回转（T+0 成功）、日内回转（T+0 失败）。

---

### Pencil 提示词

```
Design a "Trade Tagging System" UI for a Chinese A-share paper trading platform. This involves two parts: (A) tag management on trade records, and (B) tag-based performance statistics.

CONTEXT:
- Platform: "维斯量化交易平台" (Weisi Quant)
- Part A is an addition to the existing PaperTradingPage (模拟盘执行台)
- Part B is an addition to the existing PerformanceDashboard (绩效看板)
- Purpose: let traders tag each trade for post-hoc review, then see which behaviors make money

---

PART A — Trade Tagging on PaperTradingPage

ADD TO the existing trade records table (成交记录):

- Add a new column "标签" between "成交价" and "成交时间" in the trades table
- Each cell shows:
  - If tagged: small colored tag pill(s), e.g. "[按策略执行]" in green, "[追高]" in red
  - If untagged: subtle "+ 添加标签" text in muted color, clickable
- Click "+" or an existing tag pill opens a small popover:

  POPOVER DESIGN:
  - Position: anchored to the clicked cell, opens downward
  - Background: white, shadow, rounded 10px, padding 12px
  - Title: "选择标签" with "×" close button
  - 8 preset tags shown as selectable chips:
    [按策略执行] [冲动交易] [追高] [止损过早] [按计划止盈] [抄底过早] [T+0成功] [T+0失败]
  - Each chip: rounded pill, 28px height, click to toggle (gray outline → filled color)
    Color coding by tag type:
    - Discipline tags (按策略执行, 按计划止盈, T+0成功): green tint (#e8f5e9 bg, #1f8b4c border)
    - Mistake tags (冲动交易, 追高, 止损过早, 抄底过早, T+0失败): red tint (#fce4e4 bg, #c62828 border)
  - Multi-select allowed (one trade can have multiple tags)
  - Bottom: "确定" button (primary) to save, "取消" link to dismiss
  - Saved tags appear as stacked pills in the cell (max 3 visible + "+N" overflow)
  - Hover over tag pill shows full tag name tooltip

---

PART B — Tag Statistics on PerformanceDashboard

ADD A NEW SECTION below the existing Market Heatmap section on the PerformanceDashboard:

- Section title: "交易行为分析" with hint "按标签分组统计，复盘哪些行为在赚钱"

LAYOUT: Two sub-sections side by side

LEFT (60% width): Tag Performance Table
- Table columns: 标签 | 笔数 | 胜率 | 净胜率 | 均收 | 总盈亏
- Header: muted background, bold labels
- Rows:
  - One row per tag, sorted by total PnL descending
  - Tag name as colored pill (matching the Part A colors)
  - Numbers in monospace
  - Positive PnL in red, negative in green
  - Best-performer row: subtle gold left border
  - Worst-performer row: subtle warning amber left border
- Empty state: "暂无交易标签数据，在模拟盘成交记录中为交易添加标签后出现。"

RIGHT (40% width): Tag Distribution Donut
- A simple donut/pie chart showing tag distribution by trade count
- Use pure SVG: a circle with colored arc segments
- Center of donut: total trade count in large bold number
- Legend below: colored dot + tag name + count + percentage
- Colors: use distinguishable palette (green shades for discipline, red shades for mistakes)
- Empty state: same as table

BOTTOM: Insight Summary (full width)
- A light gold-bordered box
- Title: "标签洞察"
- Auto-generated text based on tag performance, e.g.:
  "按策略执行的交易胜率最高 (68.2%)，冲动交易的亏损占比最大 (-¥3,240)。建议减少追高操作，坚持按计划止盈。"
- This is plain text generated by backend LLM, displayed as formatted paragraph
- If no data: "添加至少 10 笔带标签的交易后，系统将自动生成行为洞察。"

STATES:
- No tagged trades: both table and donut show empty states
- Loading: skeleton over the section
- Error: muted "标签统计暂不可用"

RESPONSIVE:
- Desktop: table + donut side by side
- Tablet/mobile: stack vertically, donut above table
```

---

## 五、飞书 Bot 配置与绑定页面

### 功能总结

新增独立设置页面（或设置页的子面板），用于管理飞书 Bot 的连接配置。用户可在此页面：绑定自己的飞书账号、配置推送偏好、查看飞书 Bot 状态。

**此页面作为 SettingsPage 的新子面板**，或作为独立页面从 Topbar 的用户菜单进入。

**页面结构**：

| 区块 | 内容 |
|------|------|
| 飞书绑定状态 | 显示当前绑定状态（未绑定/已绑定），头像 + 姓名 + 解绑按钮 |
| 二维码扫描区 | 飞书绑定二维码（由后端生成），扫描后自动关联 |
| 推送偏好 | 多选开关：日报推送、成交通知、风控告警、盘前简报 |
| 推送测试 | 发送测试消息按钮 |
| Bot 状态 | Bot 在线状态、最近推送时间、消息配额剩余 |

---

### Pencil 提示词

```
Design a "Feishu Bot Settings" panel for a Chinese A-share quantitative trading platform's settings page.

CONTEXT:
- Platform: "维斯量化交易平台" (Weisi Quant)
- This is a new settings sub-panel accessible from the Settings Page or user menu
- Purpose: bind the user's Feishu (Lark) account to receive trade alerts and daily reports via Feishu bot
- Target user: Chinese quant trader who wants mobile notifications when away from desktop

LAYOUT: Single column, stacked sections

SECTION 1 — Binding Status
- Panel with light background (#f8fafc)

  UNBOUND STATE:
  - Large illustration area: a simple Feishu logo icon (blue gradient circle with white bird/wing shape)
    Note: use a simple CSS-drawn icon or a placeholder circle — don't use actual Feishu brand assets
  - Title: "绑定飞书账号"
  - Description: "绑定后可接收模拟盘日报、成交通知和风控告警。"
  - A QR code placeholder area (200x200px, light gray dashed border, "二维码加载中" text)
    Real QR code will be rendered by backend API via <img> tag
  - Sub-text below QR: "使用飞书扫描二维码完成绑定"
  - Small note: "首次绑定后，可在飞书中 @维斯量化 查询持仓和绩效"

  BOUND STATE (replaces unbound UI):
  - Left: user's Feishu avatar (48px circle) + name (bold) + "飞书已绑定" (green small text)
  - Right: red outline button "解绑" — click shows confirmation dialog "解绑后将不再接收飞书推送，确认解绑？" with [取消] [确认解绑]
  - Below: "绑定时间: 2026-04-15 14:30" in muted text

SECTION 2 — Push Preferences
- Panel title: "推送偏好"
- Four toggle switches in a vertical list:

  1. 收盘日报    [toggle ON]    每日 15:05 推送当天战绩总结和 LLM 点评
  2. 成交通知    [toggle ON]    模拟盘每笔成交后实时推送
  3. 风控告警    [toggle ON]    连续亏损、单日大亏时立即告警
  4. 盘前简报    [toggle OFF]   交易日 9:20 推送主要指数、热点板块和自选开盘价

- Each row: label (bold, left), toggle switch (right), description (small muted below label)
- Toggle: iOS-style pill switch, gold (#d6a55c) when ON, light gray when OFF
- Auto-save: toggle change triggers instant save (no explicit save button needed)
- Saving indicator: brief "已保存" checkmark that fades after 1s

SECTION 3 — Test Push
- Compact row:
  - Text: "发送测试消息到飞书" (muted)
  - Gold outline button: "发送测试"
  - On click: button shows loading spinner, then success "已发送 ✓" (green) or error "发送失败 ✗" (red)
  - Result auto-clears after 3 seconds

SECTION 4 — Bot Status
- Minimal status bar at bottom
- Shows:
  - Green dot + "Bot 在线" (if connected) or gray dot + "Bot 离线" (if disconnected)
  - "最近推送: 2026-05-02 15:05" (muted, right-aligned)
  - "今日已推送: 3 条" (muted)

STATES:
- Loading: skeleton lines for all sections
- QR code loading: spinner inside QR placeholder area
- Bind error: "绑定失败，请刷新二维码后重试" in red
- Unbind confirmation: centered modal dialog (see above)
- Push preference save error: inline red text below the failed toggle

RESPONSIVE: Single column works well on all breakpoints — no layout change needed.

TECHNICAL NOTES:
- Use CSS variables from the design system
- Toggle switches: pure CSS implementation (hidden checkbox + styled label)
- QR code: simple <img> tag with src from backend API
- No heavy libraries needed
```

---

## 落地指引

| 页面/组件 | 新建/修改 | 插入位置 |
|----------|----------|---------|
| MarketBreadth | 新建 `MarketBreadth.tsx` | MonitorPage 顶部，监测列表上方 |
| StrategyCompare | 新建 `StrategyCompare.tsx` | ResearchPage，新增 `"compare"` tab |
| FactorWeights | 新建 `FactorWeights.tsx` | SettingsPage，新增子面板 |
| TradeTags | 修改 `PaperTradingPage.tsx` | 成交记录表新增标签列 + 弹窗 |
| TagStats | 修改 `PerformanceDashboard.tsx` | 市场热力图下方新增"交易行为分析"区块 |
| FeishuSettings | 新建 `FeishuSettings.tsx` | SettingsPage 新增子面板，或从 Topbar 用户菜单进入 |

所有组件在 `TradingWorkspace.tsx` 中通过 `React.lazy` 懒加载：
```tsx
const MarketBreadth = lazy(() => import("./MarketBreadth"));
const StrategyCompare = lazy(() => import("./StrategyCompare"));
const FactorWeights = lazy(() => import("./FactorWeights"));
const FeishuSettings = lazy(() => import("./FeishuSettings"));
```

---

*本文档每个 Pencil 提示词均为独立可用的英文 prompt，可直接复制粘贴到设计工具中。设计系统令牌和项目上下文在各节开头已统一说明。*
