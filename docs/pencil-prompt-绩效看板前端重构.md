# Pencil 提示词：模拟盘绩效看板 —— 前端页面重构

## 一、功能总结

绩效看板是一个**复盘分析页**，用于追踪模拟盘长期表现，为策略调整提供数据参考。核心流程：每个交易日收盘后（15:05），后端自动归档当日所有模拟交易数据（按策略分组、按市场状态分组），可选调用 LLM 生成中文战绩点评，前端以趋势图和指标卡的形式展示。页面面向量化交易者，强调数据的专业性和可解读性，不走花哨风格。

页面由 6 个逻辑区块组成，从上到下：

| 区块 | 数据来源 | 交互方式 |
|------|---------|---------|
| 顶栏 Hero | `GET /api/paper/performance/dashboard?days=N` | 选择时间范围（7/30/90/180 天）+ 手动刷新按钮 |
| 指标条 MetricStrip | 同上 | 只读，4 个指标卡（总资产、累计收益、最新净值日期、更新时间） |
| 资产曲线图 | `equity_curve[]`（时序） | 纯 SVG 折线图，x=日期，y=总资产，悬停 tooltip |
| 胜率趋势图 | `win_rate_trend[]`（时序） | 纯 SVG 折线图，x=日期，y=净胜率% |
| 战绩总结（LLM 点评） | `today_report`（单日） | 只读文本框：overall_summary 段落、strategy_highlights 标签列表、risk_alerts 警示列表、suggestion 建议 |
| 策略趋势表 | `strategy_trend[]`（聚合） | 按均收排序的表格：策略名、成交笔数、胜率、净胜率、均收，最多显示 8 行 |
| 市场状态热力 | `market_perf_heatmap[]`（聚合） | 卡片网格：每个市场状态一张卡片，显示成交笔数、平均胜率、平均收益，颜色区分盈亏 |

---

## 二、Pencil 提示词

将以下内容直接输入给 Pencil（或类似 AI 设计工具）：

```
Design a "Paper Trading Performance Dashboard" page for a Chinese A-share quantitative trading platform.

CONTEXT:
- The platform is called "维斯量化交易平台" (Weisi Quant)
- Target users: quantitative traders reviewing simulated trading results
- The page is read-only, used for post-market analysis (no trading actions)
- Tone: professional, data-dense but calm, financial-tool aesthetic — not flashy
- Chinese A-share color conventions: red = up/profit (#c62828), green = down/loss (#1f8b4c)
- Design system tokens: bg #eef2f7, panel bg white, text #162235, muted #66758a, accent #d6a55c (gold), radius 10px, shadow subtle

PAGE STRUCTURE — 6 sections in a 4-column CSS Grid layout:

1. HERO BAR (full width, top)
   - Left: eyebrow "PAPER PERFORMANCE", title "模拟盘绩效看板", a subtle gold top border
   - Right: a `<select>` dropdown (7日 / 30日 / 90日 / 180日) + a ghost "刷新" button
   - Minimal height, clean, establishes page context

2. METRIC STRIP (full width, below hero)
   - 4 equal-width metric cards in a row
   - Each card: label (small muted text) + value (large bold number)
   - Cards: 总资产 (neutral), 累计收益 (red if positive, green if negative), 最新净值点 (date text), 更新时间 (timestamp)

3. EQUITY CURVE + WIN RATE TREND (2 columns, side by side)
   - Left panel "资产曲线": a line chart showing total_assets over time, gold (#d2a45e) stroke
   - Right panel "胜率趋势": a line chart showing net_win_rate_pct over time, red stroke
   - Charts: clean SVG lines, minimal grid background, subtle dots at data points, date axis at bottom showing range start/end
   - Both panels: title + hint subtitle, ~170px chart height

4. PERFORMANCE REPORT (left column, 2/3 width in desktop) — the LLM-generated daily commentary
   - Panel title "战绩总结" with the report date as subtitle
   - A paragraph of Chinese text (the overall_summary)
   - A "策略亮点" block: tags showing strategy name + LLM comment, light gray background
   - A "风险提醒" block: warning items in a list, each with level indicator (info/warning/danger)
   - A "建议" block: gold-bordered box with a lightbulb icon and LLM suggestion text
   - If no report: show an empty state "暂无每日复盘，收盘归档或手动归档后显示。"

5. STRATEGY TREND TABLE (right column, 1/3 width in desktop)
   - Panel title "策略趋势" with subtitle "按平均收益排序"
   - A bordered table with columns: 策略 | 成交 | 胜率 | 净胜率 | 均收
   - Header row: light gray background, muted text, bold
   - Data rows: strategy name bold, numbers in monospace, 均收 colored red/green
   - Max 8 rows, sorted by average return descending
   - Empty state: "暂无策略绩效归档"

6. MARKET HEATMAP (full width, bottom)
   - Panel title "市场状态热力" with subtitle "查看哪些环境更适合模拟执行"
   - Auto-fit grid of cards (min 180px each)
   - Each card: market state name (bold), trade count, win rate, avg return
   - Cards with positive avg return: pink-tinted background (#fff4f1)
   - Cards with negative avg return: green-tinted background (#f0fbf4)
   - Empty state: "暂无市场状态归档"

RESPONSIVE BEHAVIOR:
- Desktop (>1320px): 4-column grid, sections as described above
- Tablet (1320px down): 2-column grid, all sections stack narrower
- Mobile (1120px down): single column, all sections full-width

INTERACTION STATES:
- Loading: each panel shows subtle skeleton shimmer while data fetches
- Error: a light red alert banner above the charts
- Empty: each panel has a dedicated empty-state message in muted text, centered

TYPOGRAPHY:
- Font: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei"
- Numbers: "IBM Plex Mono" for all numeric data
- Title: 20px bold, body: 13px, small labels: 12px, chart axis: 11px

DO NOT use any charting library. Use clean, minimal inline SVG for the two line charts. The design should feel like a professional Bloomberg Terminal or Wind Financial Terminal dashboard — information-first, restrained color palette, no decorative elements, no gradients except as specified.
```

---

## 三、当前实现基准

以下为当前 `PerformanceDashboard.tsx` 已实现的能力，供重构时对照：

- **图表方案**：纯手写 SVG `<path>` + `<circle>`，不依赖 recharts
- **折线图参数**：viewBox 560×170，padding 20px，y 轴自适应 min/max，网格背景用 CSS `linear-gradient`
- **指标颜色**：`toneFromChange()` 函数，正值 → `"up"`（CSS class 变红），负值 → `"down"`（变绿）
- **策略表排序**：`compareStrategyTrend()` 按最新均收降序
- **市场状态卡片**：`market-heatmap` 卡片网格，`.up` / `.down` class 控制背景色
- **空白态**：`<EmptyPerformance>` 统一组件，居中 muted 文字
- **加载态**：`loading` state 控制骨架屏（`skeleton-line` class），与 TradingWorkspace 其他页面一致
- **时间范围**：`<select>` 硬编码 7/30/90/180 四个选项，切换时重新 fetch
- **数据刷新**：手动按钮触发 `loadDashboard()`，无自动轮询

重构时注意不要破坏 `TradingWorkspace.tsx` 中的 lazy import 和 Topbar 中的 `page === "performance"` 路由判断。

---

## 四、Tab 导航说明

当前 Topbar 中的 tab 定义（`"performance"` 排在第六位）：

```
实时监控 → 量化分析 → 选股宝典 → 研究复盘 → 模拟盘 → 绩效
```

"绩效" tab 的显示条件：当前登录用户 `can_paper_trade === true`（与"模拟盘"tab 共享白名单控制）。未登录或无白名单的用户看不到此 tab。

---

*本提示词基于 2026-05-02 项目全面审查和当前代码基线生成。*
