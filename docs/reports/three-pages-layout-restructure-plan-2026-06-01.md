# 实时监控 / 策略跟踪 / 模拟盘 · 布局重构方案

- 状态：设计方案 / 待评审（**仅方案，未改代码**）
- 适用范围：`frontend/src/features/{monitor,strategy-tracking,paper}`，三页页面级布局重构
- 最后核验日期：2026-06-01
- 关联：字段级处理见 `docs/reports/frontend-information-density-optimization-plan-2026-06-01.md`；视觉 token/原语见 `docs/frontend-ui-redesign-development-plan-2026-05-31.md` 与 Phase 4 文档
- 口径：保留买入类/观察类区分、策略线身份、真实/影子/信号收益分区（§6.6/§6.9）
- 后续动作：按 §6 分批实施；本方案聚焦"布局重排 + 区块去留"，字段文案沿用信息密度文档

---

## 0. 先说结论
三页的共同病根是**没有"第一屏结论区"**：把概况、筛选、装饰、明细全平铺，用户进页先看到一堆"前戏"，真正要看的"今天该干嘛 / 账户怎样 / 哪些要处理"被埋。

**统一改造范式（三页都用同一套骨架）：**
```
① 结论区（第一屏，1–3 个核心结论，必看）
② 主区（这页的主角：榜单 / 持仓 / 明细表，最大面积）
③ 次区（低频/辅助：折叠、Tabs 分组、抽屉、弹窗）
```
- **复用已落地资产**：侧栏壳、`Panel/StatTile/PriceText/Chip/Toolbar` 原语、暗色 token；不新造视觉。
- **装饰降级**：仪式感（RitualFortuneStrip/抽奖）、像素小人 cockpit 收纳或弱化，不占首屏黄金位。
- **移动端**：一律单列；表格转"卡片行"；次区默认折叠。
- **低频操作进抽屉/弹窗**：录入持仓、录入委托等不常驻首屏。

---

## 1. 实时监控（监控工作台）

### 1.1 现状结构（`MonitorPage.tsx`，2 栏栅格 + 多堆叠区）
```
[左列] 实时监控摘要(+复盘草稿+「盘面数字」Collapse)
        生产优先榜(解读AI + FamilyStrip + 卡片列表)
        行业 ETF 做T替代(卡片列表)
[右列aside] 持仓录入表单(常驻) + 已录入底仓(卡片列表)
[另外堆叠] 盘中 Pulse · 全市场午盘/收盘复盘 · 小时全市场快照 · 右侧速览(持仓动作/榜单前三)
```
### 1.2 问题
- "今日核心结论"（有无买点 / 持仓风险 / 大盘状态）被埋进摘要文字，第一屏抓不住重点。
- 盘中 Pulse / 复盘 / 小时快照 / 右侧速览 多块纵向堆叠 → 页面很长。
- **持仓录入表单常驻右栏**：低频操作占了首屏黄金位。
- 仪式感/Pulse 花哨装饰分散注意力。

### 1.3 新布局
```
┌ ① 结论区：今日速览（一行 3 张 StatTile，必看）────────────────────┐
│  今日机会  可买N/观察M →优先榜   持仓风险 高风险K只 →底仓   大盘状态 一句话(+Pulse) │
├ ② 主区（2 栏）──────────────────────────┬────────────────────────┤
│  生产优先榜（主角，最大，解读AI + 卡片）  │  我的持仓信号（已录入底仓）   │
├ ③ 次区（Tabs/折叠，默认收起）──────────┴────────────────────────┤
│  [ETF 做T替代] [全市场复盘] [小时快照]  ← 一组 Tab，默认停在第一个或收起   │
└──────────────────────────────────────────────────────────────────┘
顶部操作：右上「+ 录入持仓」按钮 → 抽屉（原录入表单移入，不常驻）
```
### 1.4 区块去留
| 区块 | 处理 | 说明 |
|---|---|---|
| 实时监控摘要文字 | **改结论区 3 卡** | 提炼成机会/风险/市场状态三结论 |
| 盘面数字 Collapse(MetricGrid) | **保留折叠** | 已是 Collapse，保持收起 |
| 生产优先榜 | **保留为主区主角** | 解读AI、FamilyStrip 保留 |
| 已录入底仓 | **保留为主区右栏** | 持仓监控核心 |
| 持仓录入表单 | **移抽屉**（按钮触发） | 低频，不常驻 |
| 行业 ETF 做T | **移次区 Tab** | 辅助策略 |
| 午盘/收盘复盘 | **移次区 Tab + 默认折叠** | 长文，低频细看 |
| 小时全市场快照 | **移次区 Tab** | 低频 |
| 右侧速览(持仓动作/榜单前三) | **并入结论区/主区** | 持仓动作并入"持仓风险"卡；榜单前三即优先榜头部 |
| 盘中 Pulse 花哨条 | **并入"大盘状态"卡** | 去花哨，留一个时间/状态 |
### 1.5 桌面/移动
- 桌面 ≥xl：结论区 3 卡一行；主区 优先榜:持仓 ≈ 6:4；次区 Tabs 全宽。
- 移动 <lg：结论区 3 卡纵向；主区单列（优先榜在上、持仓在下）；次区折叠；录入走抽屉。
### 1.6 涉及文件
`MonitorPage.tsx`（1094 行，**超阈值，借机拆**）→ 拆出 `MonitorConclusionBar.tsx`、`MonitorMoreTabs.tsx`（ETF/复盘/快照）、`HoldingEntryDrawer.tsx`；页面只做编排。

---

## 2. 策略跟踪

### 2.1 现状结构（`StrategyTrackingPage.tsx`）
```
hero(标题+meta+仪式感) → 筛选面板(ModeToggle + 5~9 个 Select) → FriendlySummary(一句话)
→ 多条 Alert → top-grid(SummaryBar + ReviewPanel + PromotionReviewPanel)
→ StatusCards(状态筛选卡) → 主面板 7 Tab(跟踪复盘/涨幅榜/风险榜/策略表现/持有分析/战绩漂移/复盘诊断)
→ 详情抽屉
```
### 2.2 问题
- **表格前"前戏"过长**：hero + 筛选 + FriendlySummary + 三面板 + StatusCards + 多 Alert，核心表被推到很下面。
- **概况重复三处**：FriendlySummary、SummaryBar、StatusCards 都在讲"今天多少条/多少到买点/多少风险"。
- **7 Tab 里前 3 个（跟踪复盘/涨幅榜/风险榜）是同一张表**，只是排序/过滤不同。
- PromotionReviewPanel（晋升复盘）是 research/admin 性质，却占顶部。

### 2.3 新布局
```
┌ ① 结论区：一句话 + 4 张可点状态卡（合并原三处概况）──────────────┐
│  今日N条信号·K到买点·J破止损·W需复核   [重点看][等买点][已走弱][需复核] ←点=筛选 │
├ 工具条：区间 ▾  策略线 ▾  [更多筛选 ▾]                      模式：新手/专业 ▸│
├ ② 主区：明细表（6 列，已优化）+ 排序切换(默认/按涨幅/按风险) ───────┤
│  股票·结论与原因·信号性质·计划与触发·信号后表现·策略线                  │
├ ③ 次区：二级「分析」Tab（默认收起）────────────────────────────┤
│  [策略表现] [持有分析] [战绩漂移] [复盘诊断] [晋升复盘(admin)]            │
└────────────────────────────────────────────────  点行 → 详情抽屉  ┘
```
### 2.4 区块去留
| 区块 | 处理 | 说明 |
|---|---|---|
| FriendlySummary + SummaryBar + StatusCards | **三合一为结论区** | 一句话 + 4 张可点状态卡，删重复 |
| 跟踪复盘/涨幅榜/风险榜 三 Tab | **合并为 1 表 + 排序切换** | 同表不同序，用排序按钮代替 3 个 Tab |
| 策略表现/持有分析/战绩漂移/复盘诊断 | **收进二级「分析」Tab** | 一级只剩"明细表 / 分析" |
| PromotionReviewPanel | **移「分析」Tab，admin 门控** | research 性质，不占顶部 |
| 筛选 5~9 个 Select | **Toolbar：露 2~3 个 + 「更多筛选」下拉** | 窄屏不再并排撑破 |
| hero 仪式感(FortuneStrip/抽奖) | **弱化/移出** | 不占标题区 |
| 多条 Alert(stale/missing/filter) | **收成一行轻提示** | 合并展示 |
| 6 列表格本身 | **保留**（已优化为 6 列/1040px/tooltip） | 不动 |
### 2.5 桌面/移动
- 桌面：结论区一行；工具条一行；表 6 列不横滚；分析 Tab 全宽。
- 移动：状态卡 2×2；工具条收起为"筛选"按钮→抽屉；**表转卡片行**（股票+结论 Tag+信号 Tag+涨跌）；分析 Tab 单列。
### 2.6 涉及文件
新增 `StrategyTrackingConclusionBar.tsx`（合并三概况）；`StrategyTrackingPage.tsx` 把 7 Tab 收成 2 组；`StrategyTrackingFilters.tsx` 改 Toolbar + 更多筛选下拉。

---

## 3. 模拟盘 / Paper

### 3.1 现状结构（`PaperTradingPage.tsx`）
```
PaperTradingSummaryBar → RitualFortuneStrip(装饰) → PaperReviewOverview(指向监控页,冗余)
→ PortfolioExecutionPanel → [持仓 xl15 | PixelTraderWorker 像素小人 xl9]
→ PaperDetailTabs(委托/成交/个股盈亏/总绩效/ETF-T0/策略/市场/标签/风险/自动日志/对账 ~11 类)
```
### 3.2 问题
- **PaperReviewOverview 是冗余指针**：内容就是"全市场复盘主入口在实时监控页"，白占一块。
- **像素小人 cockpit 占右栏 9/24 黄金位**：娱乐性 > 信息量，挤掉了"今日动作/自动交易状态"。
- **PaperDetailTabs 把 11 类全塞一个 Tabs**：找东西费劲。
- 真实模拟收益 / 影子 / 信号等权收益口径未显式分区（§6.6）。
- FortuneStrip 装饰占位。

### 3.3 新布局
```
┌ ① 账户结论条（精简 SummaryBar）─────────────────────────────────┐
│ 总资产  今日盈亏  持仓市值  可用资金   ｜ 自动交易:开/停(暂停)  [+录入委托] │
├ ② 主区（2 栏）──────────────────────────┬────────────────────────┤
│  我的持仓（PaperPositionsPanel，主角）    │  今日动作 / 自动交易状态     │
│                                          │  (PaperTodayActionPanel；像素小人降级为小图标/可关) │
├ ③ 明细区：3 组 Tab（按用户心智重组 11 类）──────────────────────┤
│  [交易记录] 委托·成交·个股盈亏                                       │
│  [绩效]     总绩效 / 策略 / 市场 / 标签   ← 真实｜影子｜信号 三分区显式   │
│  [自动与风控] 自动日志·风险事件·ETF-T0·账本对账(admin)               │
└──────────────────────────────────────────────────────────────────┘
```
### 3.4 区块去留
| 区块 | 处理 | 说明 |
|---|---|---|
| PaperTradingSummaryBar | **精简为账户结论条** | 总资产/今日盈亏/持仓/可用 + 自动状态 + 录入委托 |
| PaperReviewOverview | **删除**（或并入结论条一句话） | 冗余指针，价值低 |
| RitualFortuneStrip | **弱化/移出** | 装饰 |
| PixelTraderWorker(像素小人) | **降级**：小图标/折叠/可关，默认精简 | 让位给"今日动作/自动状态" |
| PortfolioExecutionPanel | **并入"今日动作"或绩效 Tab** | 不单独占一行 |
| 持仓 PaperPositionsPanel | **保留为主区主角** | — |
| PaperDetailTabs（现 **7 个 Tab**：today/orders/trades/pnl/strategy/risk/diagnostic） | **重组为 3 组 Tab** | 交易记录/绩效/自动与风控（tab key 不变，见 §10.1） |
| 真实/影子/信号收益 | **绩效 Tab 内显式三分区 + 口径标注** | §6.6 防混读 |
| ETF-T0 英文术语/长句塞 pill | **中文化 + 长句移 Popover** | 见信息密度文档 §5 |
### 3.5 桌面/移动
- 桌面：结论条一行 4~5 指标；主区 持仓:动作 ≈ 6:4；明细 3 组 Tab 全宽。
- 移动：结论条指标 2 列；主区单列（持仓在上）；明细横滚表转纵向键值对；像素小人默认隐藏。
### 3.6 涉及文件
`PaperTradingPage.tsx` 去 ReviewOverview/精简;`PaperTradingSummaryBar.tsx` 精简;`PaperDetailTabs.tsx`（449 行，**超阈值**）拆为 3 组子 Tab 组件;`PixelTraderWorker` 加"精简/展开"开关。

---

## 4. 三页通用规则（落地细节）
- **结论区组件统一**：用同一个 `ConclusionBar`（StatTile + 可点卡）原语，三页复用，视觉一致。
- **数字**：价格/盈亏/涨跌一律 `PriceText`（红涨绿跌 + tabular-nums + 对齐）。
- **标签**：风险/状态用 `Chip`，每处 ≤2 个关键标签，其余进详情。
- **长文本**：`ellipsis + title` 或进抽屉，禁止撑破行高。
- **空/加载/错误**：统一 `StateViews`，每区块独立态，互不阻塞。
- **次区默认折叠**：首屏只露结论区 + 主区。

---

## 5. 组件 / 文件改动清单
| 页面 | 新增 | 改动 | 拆分（超行数） |
|---|---|---|---|
| 实时监控 | `MonitorConclusionBar`、`MonitorMoreTabs`、`HoldingEntryDrawer` | `MonitorPage` 只编排 | `MonitorPage.tsx`(1094) |
| 策略跟踪 | `StrategyTrackingConclusionBar` | `StrategyTrackingPage`(7→2 Tab)、`StrategyTrackingFilters`(Toolbar) | — |
| 模拟盘 | `PaperConclusionBar`（或精简 SummaryBar） | 去 `PaperReviewOverview`、`PixelTraderWorker` 加开关 | `PaperDetailTabs.tsx`(449) |
| 通用 | `ui/.../ConclusionBar`（复用 StatTile） | 三页接入 | — |

---

## 6. 分批实施（每批可独立合并、独立验收）
- **P0（最大体感）**：三页各加"结论区" + 把明细/次区折叠收纳（监控次区 Tab、策略 7→2 Tab、Paper 11→3 Tab）。
- **P1**：低频操作进抽屉（监控录入、Paper 录入委托）；装饰降级（仪式感/像素小人）；删冗余（PaperReviewOverview、策略三处概况合一）。
- **P2**：移动端表转卡片行；超阈值文件拆分（MonitorPage / PaperDetailTabs）；筛选 Toolbar「更多筛选」。

建议先做**策略跟踪 P0**（改动集中、收益明显）作为样板，确认范式后复制到监控与模拟盘。

---

## 7. 验收标准
- 进每页 3 秒内能看清第一屏 1–3 个核心结论（监控:机会/风险/市场；策略:信号概况；模拟盘:账户与自动状态）。
- 首屏不再被筛选/概况/装饰占满；明细需展开/Tab/抽屉可达，**信息不丢**。
- 买入类/观察类清晰区分；真实/影子/信号收益分区；无观察信号写成买入。
- `npm run lint` / `build:web` / 相关测试通过；`npm run smoke:responsive` 三页 0 横向溢出（含 375px）。
- 各区块加载/空/错误态版面稳定，一处失败不拖垮整页。
- 拆分文件行为等价（配快照/测试）。

## 8. 风险与回退
| 风险 | 处置 |
|---|---|
| 大改引入布局回归 | 分批 + 每批 `smoke:responsive` + 关键页截图比对 |
| 折叠后用户找不到原内容 | 次区 Tab/抽屉入口文案明确（"更多：ETF做T·复盘·快照"） |
| 像素小人/仪式感是卖点被误删 | 只降级/加开关、不删除，默认精简可恢复 |
| MonitorPage/PaperDetailTabs 超阈值 | 借重构顺势拆分，保持行为等价（§6.8 只拆不改逻辑） |

## 9. 明确不做
- 不改后端接口与数据口径、不改策略逻辑。
- 不删除买入/观察信号、策略线身份、风险/收益口径字段（只重排/折叠/进详情）。
- 不引入新组件库；只用已落地 token/原语。
- 不把娱乐元素直接删除（降级收纳即可）。

---

## 10. 开发实施细则（必读，防返工）

### 10.1 关键耦合与迁移（最容易踩的坑）
**策略跟踪「Tab 合并」≠ 改数据模型。** `store.tab` 同时驱动两件事：① `buildParams` 里的 `tabParams(tab)`（实测：`active→{status:'active'}`、`risk→{stopped:true}`、`gain→走 store.sort`）；② 查询启用（`holding/drift/diagnostics` 各自 `enabled: store.tab===x`）。
→ **做法（零数据风险）**：保留全部 `store.tab` 取值，仅 UI 重组：
- 主表区放一个 Segmented「全部 / 涨幅 / 风险」→ 直接 `setTab('active'|'gain'|'risk')`，三者复用同一张表（现有 `tableContent`），参数差异由 `tabParams` 自动产生。
- `gain` 需补 `tabParams('gain') → { sort:'max_gain_pct_desc' }`（或切到涨幅时 `setSort(...)`），否则"涨幅榜"语义丢失。
- 二级「分析」用内层 Tab `setTab('performance'|'holding'|'drift'|'diagnostics')`，查询启用逻辑原样保留。
- **不改** `StrategyTrackingTab` 类型与 store 字段（除给 `tabParams` 补 gain 分支）→ 持久化/深链不受影响。

**模拟盘 Tab 现状是 7 个**（`today/orders/trades/pnl/strategy/risk/diagnostic`，11 类数据已合进这 7 个）。重组为 3 组只是**外层分组包装**，`PaperDetailTabKey` 取值不变：
| 新分组 | 包含现有 tab |
|---|---|
| 交易记录 | orders · trades · pnl |
| 绩效 | strategy（内部再分 真实 / 影子 / 信号 三区） |
| 自动与风控 | today · risk · diagnostic |
→ 外层加一层分组 Tab，内层渲染原 tab 内容，**行为等价**。

### 10.2 数据来源映射（结论区每个数字都要有出处，避免做到一半没数据）
**实时监控结论区**（来自 `monitor` / `monitorPageProps`，字段名以 `workspaceTypes` 为准）：
| 结论卡 | 指标 | 来源 |
|---|---|---|
| 今日机会 | 可买/观察数 | `priorityBoard.immediate_count` / `focus_count` / `total_candidates` |
| 持仓风险 | 高风险持仓数 | `watchCards.filter(c => c.riskText.includes('高')).length`（与 Topbar 同口径） |
| 大盘状态 | 一句话 | `priorityBoard.market_state_text` / `marketPulse` / `marketBreadth` |

**策略跟踪结论区**（来自 `result.summary` + `result.items`）：
| 元素 | 来源 |
|---|---|
| 一句话概况 | `summary.tracking_count / in_entry_zone_count / stopped_count` + `needs_review_count + abnormal_return_count`（= FriendlySummary 现口径） |
| 可点状态卡 | `items` 按 `user_friendly_status` 计数（focus/wait_entry/weakening/take_profit_watch/review_needed），点击 `setUserStatus`（= StatusCards 现逻辑） |
| 数据质量 | `summary.data_quality / data_quality_text` |

**模拟盘结论条**（来自 `account` / `performance` / `autoTradingStatus`，全部沿用 SummaryBar 现字段）：
| 指标 | 来源 |
|---|---|
| 总资产/今日盈亏/持仓市值/可用 | `account.*` |
| 自动交易 开/停 | `autoTradingStatus.running / engine_running / trading_time` |
| 录入委托可用 | `!paused && !autoTradingRunning` |

> 结论区**不新增后端字段**，全部复用现有 props。

### 10.3 新组件 props 契约
```ts
// ui/surfaces/ConclusionBar.tsx（三页复用）
interface ConclusionItem { key: string; label: ReactNode; value: ReactNode; tone?: "up"|"down"|"warn"|"neutral"; onClick?: () => void; active?: boolean; }
interface ConclusionBarProps { items: ConclusionItem[]; columns?: 3 | 4 | 5; }

// MonitorConclusionBar：消费 monitor，产出 3 个 ConclusionItem，点击触发 onNavigate / 滚动到对应区
// StrategyTrackingConclusionBar：{ summary, items, activeStatus, onSelectStatus }（合并 FriendlySummary + SummaryBar + StatusCards）
// PaperConclusionBar：沿用 PaperTradingSummaryBar 入参 { account, performance, autoTradingStatus, canOpenOrder, onOpenOrderEntry, onTogglePause }
// HoldingEntryDrawer：原录入表单 props（watchDraft 等）+ { open, onClose }；表单整体迁移，不重写
// MonitorMoreTabs：{ etf, reviewReports, hourlySnapshots }；内层即现有 ETF / 复盘 / 快照组件
```

### 10.4 状态（store）改动清单（UI 态一律 Zustand，禁 `useState/useReducer`）
- `strategyTrackingStore`：几乎不动（tab/sort/userStatus 全在），仅可能给 `tabParams` 补 gain 的 sort 默认。
- 监控：新增 `monitorUiStore`（或并入 workspace UI store）：`moreTab: 'etf'|'review'|'snapshot'`、`holdingDrawerOpen: boolean`。
- 模拟盘：`paperUiStore` 加 `detailGroup: 'trades'|'perf'|'auto'`、`pixelTraderCollapsed: boolean`。

### 10.5 响应式实现细则
- 用 antd `Grid.useBreakpoint()`：`xl(≥1200)` 双栏；`lg` 主区双栏、结论 3 卡；`<lg` 全单列。
- 结论区：`xl` 一行 N 卡；`<md` 每行 2 卡（`Row gutter` + `Col xs=12 md=8/6`）。
- **表格转卡片行（移动端）**：`<lg` 时 `StrategyTrackingTable` 改渲染 `VirtualCardList`（行内：股票名+代码 / 结论 Tag / 信号 Tag / 现价涨跌 `PriceText`），点行开抽屉；桌面仍用 6 列 `VirtualGrid`。**用断点切两套渲染，不要 CSS 硬压**。
- 次区 Tabs / 折叠在 `<lg` 默认收起。

### 10.6 各区块加载/空/错误态（统一 `StateViews`，互不阻塞）
- 每区块独立 `loading/error`；一处失败不顶替整页。
- 加载=骨架（结论卡占位条、表 `VirtualGrid loading`）；空=对应文案（"今日无信号/无持仓/未开自动交易"）；错误=区块内红字 + 重试。

### 10.7 实现约束（护栏，提交必过）
- 颜色/间距/圆角只用 `var(--token)`；行情数字一律 `PriceText`；**禁止裸 hex / 裸 px / `fontSize<12`**（`check:css` 棘轮拦截）。
- 新组件不写内联 `style={{}}` 字面量（用 CSS Module 或集中常量），不顶高 `inlineStyleObjects` 基线。
- 文件行数：页面 ≤300、组件 ≤220；借重构拆 `MonitorPage.tsx`(1094) / `PaperDetailTabs.tsx`(449)，**拆分保持行为等价**（§6.8）。

### 10.8 验收测试用例（仿现有 `*.test.tsx` 的 SSR 断言）
- 策略跟踪：结论条渲染"一句话 + 4 状态卡"；主表切"风险"→ `buildParams(...).stopped===true`；切"涨幅"→ sort 生效；分析 Tab 切 holding/drift 时对应 query `enabled`。
- 模拟盘：结论条出总资产/自动状态；3 组 Tab 各含原 tab（断言 orders/trades/pnl 在"交易记录"组内可达）；删 `PaperReviewOverview` 后页面不报错。
- 监控：结论区 3 卡可见且数字源自 monitor；录入表单移入抽屉（默认不在首屏主 DOM）；次区 Tab 默认收起。
- 三页：`smoke:responsive` 375/768/1440 视口 **0 横向溢出、0 报错**。

### 10.9 依赖顺序的任务拆解（顺序不能乱）
1. **先做原语 `ConclusionBar`**（三页都依赖）。
2. **策略跟踪 P0（样板）**：ConclusionBar 合并三概况 + 主表 Segmented + 分析 Tab 分组（store 基本不动）→ 跑测试/smoke 验证范式。
3. 复制到**监控**：结论条 + 次区 Tab + 录入抽屉 + 拆 `MonitorPage`。
4. 复制到**模拟盘**：结论条 + 3 组 Tab + 删 ReviewOverview + 像素小人开关 + 拆 `PaperDetailTabs`。
5. **移动端卡片行 + 装饰降级**（P1/P2）。

### 10.10 逐页"不要动什么"（防误删/误改）
- 策略跟踪：6 列表格本体、`tabParams`/`buildParams` 数据契约、详情抽屉、专业/新手 `viewMode` 门控——**不动**。
- 监控：生产优先榜卡片与 `FamilyStrip`、AI 解读、底仓信号取数——**不动**逻辑，只挪位置。
- 模拟盘：`PaperPositionsPanel`、绩效真实/影子/信号口径、自动交易风控门——**不动**；`PixelTraderWorker` 只加开关不删。

