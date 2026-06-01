# 前端信息展示优化方案（信息密度审查）

- 状态：审查结论 / 待评审（**仅方案，未改代码**）
- 适用范围：Web 前端 `frontend/src`，重点 7 个核心页面
- 最后核验日期：2026-06-01
- 数据范围：基于 `codex/phase4-phase5-architecture` 分支当前代码静态审查（`git status` 干净）
- 口径定义：本文区分「买入类信号 / 观察类信号」「真实模拟组合收益 / 每日信号等权收益 / 影子跟踪收益」，与 `docs/engineering-conventions.md` §6.6、§6.9 一致
- 是否可作生产依据：可作为前端改造排期依据；不改变任何后端口径或策略边界
- 后续动作：按 §7 优先级分批实施；实施前每页补充加载/空/错误态快照回归

---

## 1. 总体结论

### 1.1 当前最大问题：缺的是「信息分层」，不是「信息太少」
页面把**结论、原因、信号性质、执行计划、风控、审计**几乎等权地平铺在同一屏 / 同一张卡片 / 同一行表格里，并且**同一个含义换名字重复出现**。用户因此无法在一眼内回答"现在该看什么"。三类典型病灶：

1. **重复字段**（同值多名）：
   - 卡片里「质量 ★★★★☆」与「质量分 82」同时显示（[StockCard.tsx](frontend/src/features/workspace-shared/StockCard.tsx) L78/L83）。
   - 「预期」与「建议仓位/数量」都来自同一个 `suggested_position_text`（[workspaceViewModels.ts](frontend/src/features/workspace-shared/workspaceViewModels.ts) L25/L26）。
   - 板块、止损在同一张卡片里出现 2–3 次（`identityTags` + `details` + 操作区）。
   - 分析页 `decisionTitle / executionText / invalidText / statusText / 风险` 每个都渲染了两遍（[AnalysisPage.tsx](frontend/src/features/analysis/AnalysisPage.tsx)）。

2. **长串拼接**：优先榜卡片的 `details` 用 `" / "` 拼了**最多 11 段**文字（[workspaceViewModels.ts](frontend/src/features/workspace-shared/workspaceViewModels.ts) L28–L40），加上最多 6 个 `badges` + `subBadges` + `executionHint`，单卡信息量爆炸。

3. **审计/内部字段进首屏**：策略跟踪表默认强制横向滚动（`scroll.x=1360`），9–10 列、每格 3 行堆叠；Paper ETF-T0 面板把 `needs_validation / candidate_production / positive_t_buy / OOS` 等英文状态码直接展示给用户。

### 1.2 最拥挤的 3 个页面（按严重度）
1. **策略跟踪表格**（[StrategyTrackingTable.tsx](frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx)）：9–10 列 × 每格 3 行堆叠 + `scroll.x=1360` 强制横滚；「当前结论 / 信号性质 / 为什么」三列在重复表达同一件事。
2. **低吸 / 全策略优先榜卡片**（[StockCard.tsx](frontend/src/features/workspace-shared/StockCard.tsx) + [workspaceViewModels.ts](frontend/src/features/workspace-shared/workspaceViewModels.ts)）：单卡 = 身份 + 2 标签 + 动作 + 双重质量分 + 价/涨跌/风险/预期 + 买入区/止损/仓位 + 6 badges + 子 badges + 执行提示 + 11 段 details。
3. **Paper / 模拟盘绩效**（[PaperTradingPerformance.tsx](frontend/src/features/paper/PaperTradingPerformance.tsx)）：6 个 pill + 2 张横滚表 + 把整段话塞进 `InfoPill` 的 value（执行门禁）+ 大量未翻译英文术语。

### 1.3 最该删减的信息
- 重复同值字段（质量分双显、预期=仓位、板块/止损多显）。
- `details` 的 11 段长拼接（拆进卡片正文的固定槽位或详情）。
- 审计字段（`future_leak_check / data_cutoff_at / posterior_start_date`）默认列。
- 英文状态码原文（`needs_validation / candidate_production / positive_t_buy / paper_small / OOS`）。

### 1.4 必须保留（不得删除）
- 「买入类（确定可买 / 小仓试买）」与「观察类（接近买点 / 观察确认）」的区分。
- 策略线身份：**原低吸策略 / 前排加权 / 前排极精选**。
- Shadow / Paper / 仅观察（watch-only）状态。
- 风险状态、市场状态、硬风险剔除原因。
- 真实模拟组合收益 与 每日信号等权收益 的区别。
- baseline 默认排序展示。
- 用户判断"能否交易"所必需的：买入区、止损、风险等级、失效条件。

> 重要肯定：项目已有较好的"通俗语义层"——[signalStateCopy.ts](frontend/src/features/strategy-tracking/signalStateCopy.ts)、[uxClarity.ts](frontend/src/utils/uxClarity.ts)、[StrategyLaneStatusCard.tsx](frontend/src/features/low-buy/StrategyLaneStatusCard.tsx)、[StrategyTrackingFriendlySummary.tsx](frontend/src/features/strategy-tracking/StrategyTrackingFriendlySummary.tsx) 已经把买/观分得很清楚。**本方案不是推翻它，而是把这套语义在密集的表格/卡片里"减重 + 分层 + 去重"。**

---

## 2. 页面级审查清单

### 2.1 低吸优先榜 / 全策略优先榜（选股宝典 [PlaybookPage.tsx](frontend/src/features/playbook/PlaybookPage.tsx) + 卡片模型 [workspaceViewModels.ts](frontend/src/features/workspace-shared/workspaceViewModels.ts)）
- **当前信息问题**：英雄区 4 pill 与下方 9 项 `MetricGrid` 重复（「全量深筛」「数据状态」各出现两次）；5 个动作计数 metric 与候选 Tab 的角标数量重复；单卡 `details` 拼 11 段。
- **可删除**：MetricGrid 里的「全量深筛」「数据状态」（已在英雄区）；卡片「质量 stars」与「质量分」二选一。
- **可合并**：5 个动作计数（可买/小仓/等确认/观察/放弃）→ 与 CandidateTabs 角标合一，MetricGrid 只留「可执行总数 / 真实成交样本 / 5日达标率」。
- **可移到详情**：`details` 的主力评分、龙头排名、多周期共振、连续推荐天数、退出计划 → 卡片"展开/详情"。
- **必须保留**：买/观分档（Tab 已分好）、买入区、止损、风险、策略线身份。
- **文案需改写**：「现在可买/小仓试买」标题 OK；卡片分数前缀 `Shadow xx`、`观察 xx` 需中文化（见 §5）。
- **拥挤风险**：单卡 11 段 details 在窄屏换行成多行，破坏列表行高（`VirtualCardList estimateSize=54` 与实际高度不符 → 滚动跳动）。
- **桌面端**：卡片改"固定字段槽位"（动作 / 价格涨跌 / 买入区 / 止损 / 风险 / 1 个关键 badge），其余进详情。
- **移动端**：英雄区 pill 改 2 列；动作计数横条可横向滑动但不换行堆叠。

### 2.2 策略跟踪页面（[StrategyTrackingPage.tsx](frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx) / [StrategyTrackingTable.tsx](frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx) / [StrategyTrackingFilters.tsx](frontend/src/features/strategy-tracking/StrategyTrackingFilters.tsx)）
- **当前信息问题**：表格 9–10 列、每格 3 行堆叠、`scroll.x=1360` 强制横滚；「当前结论」「信号性质」「为什么」三列语义重叠；「信号性质」格里 `signalStateText` + `signalStateKindText` + `signalStateHelpText` 三行长文；筛选区 5 个 Select 并排（≈700px）窄屏拥挤。
- **可删除**：「信号性质」格的 `signalStateHelpText`（移 tooltip）；默认隐藏「专业审计」列（已受 `viewMode=professional` 门控，保持）。
- **可合并**：「当前结论 + 为什么」合成 1 列（结论 Tag + 一句原因）；「信号后表现 + 适合持有」合成 1 列或移详情；「跟踪计划 + 触发」可上下分区为同一列。
- **可移到详情**：信号后最高/最低/现价三件套、最优持有天数、`matched_strategy_variants` 同时命中明细 → 详情抽屉（[StrategyTrackingDetailDrawer.tsx](frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx) 已存在）。
- **必须保留**：信号性质 Tag（买/观分档）、策略线身份、止损/目标、已到买点/已破止损/已达目标三态。
- **文案需改写**：「信号性质」用短 Tag（确定可买 / 小仓试买 / 接近买点·观察 / 观察确认·观察），详细解释进 tooltip。
- **拥挤风险**：每格 3 行 `cell-stack` × 9 列 → 行高被撑高、横滚找不到主信息；`Tag` 在窄列里换行撑破行高。
- **桌面端**：默认列压到 **6 列**（股票/板块 · 结论与原因 · 信号性质 · 计划与触发 · 信号后表现 · 策略线），`scroll.x` 降到 ≤1040。
- **移动端**：表格转「卡片式行」，每行只显示 股票 + 结论 Tag + 信号性质 Tag + 现价涨跌，点开看详情。

### 2.3 监控工作台（[MonitorPage.tsx](frontend/src/features/monitor/MonitorPage.tsx)，1094 行，按规范"只小修不扩写"）
- **当前信息问题**：单页堆叠"实时监控 + 指标 Collapse + 已录入底仓 + 行业 ETF 做 T + 右侧速览(持仓动作/榜单前三) + 盘中 Pulse + 午盘/收盘复盘 + 小时快照"近 8 个区块；"盘中 Pulse"标题出现两处。
- **可删除**：重复的"盘中 Pulse"标题二选一；复盘区把全文默认展开的部分收进 Collapse。
- **可合并**："榜单前三"与优先榜入口合并为一个"今日重点"卡。
- **可移到详情/展开**：小时全市场快照、午盘/收盘复盘全文 → Collapse（部分已是）。
- **必须保留**：今日是否有买入类信号、持仓风险动作、市场状态、底仓信号。
- **文案**：区块标题统一为"用户视角"短语（如"持仓要做什么""今天大盘什么状态"）。
- **拥挤风险**：纵向区块过多导致首屏看不到"今天最重要的结论"。
- **桌面端**：首屏只留「今日结论条（有无买点/风险）」+「持仓动作」+「优先榜前 3」，其余折叠。
- **移动端**：右侧速览改为首屏顶部摘要条，复盘/快照默认折叠。

### 2.4 回测页面（[BacktestDashboard.panels.tsx](frontend/src/features/backtest/BacktestDashboard.panels.tsx) / [ValidationPanel.tsx](frontend/src/features/backtest/ValidationPanel.tsx) 等 20+ 文件）
- **当前信息问题**：面板数量多（任务、净值、交易明细、验证、归因、优化、ML 容量、ETF OOS、改进门、改进摘要…）一屏铺开；术语半中半英。
- **可删除/折叠**：把"防过拟合 / 样本外 / 归因 / 优化 / ML 容量"等二级分析默认折叠，首屏只留"结论 + 净值 + 核心指标"。
- **可合并**：净值曲线 + 核心指标（收益/回撤/Sharpe/胜率）为"结论卡"。
- **必须保留**：是否 OOS、是否滚动验证、回撤、PF、`backtestVerdict`（[uxClarity.ts](frontend/src/utils/uxClarity.ts) 已有"值得继续验证/谨慎使用/不建议使用"四档）。
- **文案需改写**：`OOS→样本外`（ValidationPanel 已做，统一到全站）；`walk-forward→滚动验证`；`tick data insufficient→逐笔成交数据不足`。
- **拥挤风险**：多个 scroll 表 + 多面板，移动端尤其难读。
- **桌面端**：左结论右明细两栏；二级分析进 Tabs / Collapse。
- **移动端**：单列，二级分析默认收起。

### 2.5 模拟盘 / Paper（[PaperTradingPerformance.tsx](frontend/src/features/paper/PaperTradingPerformance.tsx) / [PaperTradingSummaryBar.tsx](frontend/src/features/paper/PaperTradingSummaryBar.tsx) / [PaperTodayActionPanel.tsx](frontend/src/features/paper/PaperTodayActionPanel.tsx)）
- **当前信息问题**：ETF-T0 面板 6 pill + 2 张横滚表 + 把整段"执行门禁"长句塞进 `InfoPill` 的 value（破坏 pill 版式）+ 英文术语（`needs_validation / candidate_production / positive_t_buy / paper_small / OOS / 影子`）。
- **可删除**：默认隐藏"逐笔复盘归因"表（移 Collapse）。
- **可合并**：`OOS阶段 + OOS结论` 合一为"样本外状态"。
- **可移到详情**：执行门禁说明 → Popover/Collapse，不放 pill value。
- **必须保留**：**真实模拟组合收益（胜率/平均单笔/最大回撤）必须与"影子跟踪收益""信号等权收益"显式分区**（§6.6）；自动执行风控门禁结论。
- **文案需改写**：见 §5（OOS/影子/状态码全部中文化）。
- **拥挤风险**：长句进 pill → 文字溢出/换行遮挡；多张横滚表移动端横向溢出。
- **桌面端**：绩效"真实/影子/样本外"三段清晰分卡。
- **移动端**：横滚表转纵向键值对；门禁说明折叠。

### 2.6 分析页面（[AnalysisPage.tsx](frontend/src/features/analysis/AnalysisPage.tsx)）
- **当前信息问题**：8 个 panel；`decisionTitle / executionText / invalidText / statusText / 风险 / 预期价差` 多处重复渲染（hero summary = callout title；decision 区与"执行计划"Collapse 重复 execution/invalid）。
- **可删除**：hero 的 `Callout` 与 `WorkspacePageIntro.summary` 二选一（同为 decisionTitle）；"执行计划"Collapse 里与 decision 区重复的 execution/invalid 文本。
- **可合并**：identity 区 7 项 metric 压到 5 项（合并"交易条件/机会强度"为一项"机会强度"，"风险"只显示一次）。
- **可移到详情**：AI 补充、合规假设、买卖盘细节（已在 Collapse，保持）。
- **必须保留**：能否操作结论、买入区/止损/止盈、失效条件、风险等级。
- **文案需改写**：「交易条件」(tradability_score) → "可交易性"；「机会强度」(signal_score) 保留但加 tooltip。
- **拥挤风险**：重复文本拉长页面，重点"能不能买"被淹没。
- **桌面端**：首屏只留"能否操作 + 怎么做 + 错了怎么办 + 买入区/止损"。
- **移动端**：K 线与指标默认折叠次级指标。

### 2.7 设置页（与策略展示相关：[SettingsPagePanels.tsx](frontend/src/features/settings/SettingsPagePanels.tsx) / [FactorWeightSettingsCard.tsx](frontend/src/features/settings/FactorWeightSettingsCard.tsx) / [QuantParameterMlCard.tsx](frontend/src/features/settings/QuantParameterMlCard.tsx) / [DataQualityPanel.tsx](frontend/src/features/settings/DataQualityPanel.tsx)）
- **当前信息问题**：管理/调参字段密集，普通用户与管理员混在一屏；数据覆盖率、ML 容量、因子权重等内部字段对普通用户无意义。
- **可删除/隐藏**：普通用户视角默认隐藏因子权重、ML 容量、数据质量明细（管理员/高级开关后再显示）。
- **可合并**：策略相关配置归到"策略展示"一组，与账号/数据源/风控分组隔离。
- **可移到详情**：数据覆盖率、任务状态、调试字段进"高级信息"。
- **必须保留**：风控阈值、策略最小收益阈值、数据源选择等影响交易的项。
- **文案**：用"会影响什么"一句话说明每个阈值的后果。
- **拥挤风险**：长表单一屏堆叠，分组边界不清。
- **桌面端**：左导航分组 + 右表单，管理项折叠。
- **移动端**：每组单列，管理项默认收起。

---

## 3. 字段级处理表

> 处理方式：保留 / 删除 / 合并 / 移到详情 / 改文案。"影响交易判断"列：是=直接影响能否买/卖/风控，否=辅助或内部。

| 字段 | 当前位置 | 当前问题 | 处理方式 | 理由 | 影响交易判断 |
|---|---|---|---|---|---|
| `scoreStars`（质量★） + `scoreText`（质量分数字） | StockCard L78 / L83 | 同一质量分显示两遍 | **合并**：只留数字，hover 显示星级 | 去重 | 否（辅助） |
| `expectedText`（预期）= `operationAmountText`（建议仓位） | StockCard L85/L91，来源同 `suggested_position_text` | 同值两名 | **合并**为「建议仓位」 | 去重 | 是 |
| `details`（11 段 `/` 拼接） | priorityToCard L28–40 | 超长串、窄屏炸行 | **拆分+移详情**：卡面留 1 句主因，其余进详情 | 降密度 | 部分 |
| `badges`（≤6）+ `subBadges` | StockCard L94–103 | 标签无限堆叠撑破行高 | **限 2 个关键**（如"龙头#x""N策略命中"），余下进详情 | 防撑破 | 否 |
| `priorityScoreText` = `Shadow 82` / `观察 75` | workspaceViewModels L66–75 | 英文 + 含义不清 | **改文案**：「影子分 82」「观察分 75」并加 tooltip | 通俗 | 否 |
| `laneIdentityText` = `前排加权 · Paper验证` | workspaceViewModels L56–64 | "Paper验证"英文 | **改文案**：「前排加权 · 模拟验证中」 | 通俗 | 否（身份保留） |
| `signalStateHelpText`（信号性质第 3 行长句） | StrategyTrackingTable L92 | 每格 3 行长文 | **移 tooltip** | 降密度，保留可查 | 是（可查） |
| 「当前结论」+「为什么」两列 | StrategyTrackingTable L74–95 / L153–163 | 语义重叠 | **合并**为「结论与原因」1 列 | 去重 | 是 |
| 「信号后表现」+「适合持有」两列 | StrategyTrackingTable L120–141 | 次级信息占 2 列 | **合并/移详情** | 降列数 | 否 |
| 专业审计列（`future_leak_check`/`data_cutoff_at`/`posterior_start_date`） | StrategyTrackingTable L168–180 | 内部审计字段 | **保留但默认隐藏**（已 `viewMode` 门控） | 内部 | 否 |
| MetricGrid「全量深筛」「数据状态」 | PlaybookPage L96/L98 | 与英雄区 pill 重复 | **删除**（英雄区已有） | 去重 | 否 |
| 5 个动作计数 metric | PlaybookPage L91–95 | 与候选 Tab 角标重复 | **合并**到 Tab 角标 | 去重 | 否 |
| ETF-T0 `OOS阶段` + `OOS结论` | PaperTradingPerformance L132/L135 | 英文状态码 + 拆两格 | **合并 + 中文化**：「样本外：可进入生产候选 / 仍需验证」 | 通俗 | 否 |
| ETF-T0 执行门禁长句（放进 InfoPill value） | PaperTradingPerformance L157–161 | 整段话塞进 pill，版式破裂 | **移 Popover/Collapse** | 防溢出 | 否 |
| `影子胜率`/`shadow_*` | PaperTradingPerformance L143–148 | 半英文、易和真实收益混 | **改文案**「跟踪胜率」+ 分区标注"非真实组合" | 防误读 | 是（口径） |
| 分析页 `decisionTitle` | AnalysisPage L57 & L69 | 渲染两遍 | **删一处** | 去重 | 是 |
| 分析页 `executionText`/`invalidText` | AnalysisPage L145/146 & L191/192 | decision 区与 Collapse 重复 | **删 Collapse 内重复** | 去重 | 是 |
| 分析页 metric「交易条件」「机会强度」 | AnalysisPage L80/81 | 术语数字 | **改文案 + tooltip** | 通俗 | 否 |
| 设置：因子权重 / ML 容量 / 数据覆盖率 | SettingsPagePanels 等 | 内部调参对普通用户无意义 | **移"高级信息"默认隐藏** | 降噪 | 否 |

---

## 4. 页面信息分层方案

> 统一三层：第一层=立即结论；第二层=辅助判断；第三层=详情/审计。

| 页面 | 首屏只显示 | 表格默认列 | 详情/抽屉 | tooltip | 移动端优先 |
|---|---|---|---|---|---|
| 优先榜 | 今日可买数 / 观察数 / 风险提示 + 主看 1 只 | —（卡片制） | 主力评分、龙头排名、共振、退出计划、连续推荐 | 质量星级、策略线含义 | 主看卡 + 可买 Tab |
| 策略跟踪 | 友好摘要（已有）+ 风险条 | 股票/板块·结论与原因·信号性质·计划与触发·信号后表现·策略线（6 列） | 信号后最高/最低、最优持有、同时命中、专业审计 | 信号性质解释、失效条件 | 卡片行：股票+结论 Tag+信号 Tag+涨跌 |
| 监控工作台 | 今日有无买点 / 持仓动作 / 优先榜前 3 | 底仓信号默认列精简 | 复盘全文、小时快照 | 指标口径 | 顶部摘要条 + 持仓动作 |
| 回测 | 结论（四档）+ 净值 + 收益/回撤/Sharpe/胜率 | 交易明细默认折叠 | 样本外、归因、优化、ML 容量 | 过拟合/样本外含义 | 单列，二级折叠 |
| Paper | 真实模拟：总盈亏/胜率/回撤 | 绩效分组表精简 | 逐笔复盘、执行门禁、ETF 影子明细 | OOS/影子口径 | 纵向键值对 |
| 分析 | 能否操作 + 怎么做 + 错了怎么办 + 买入区/止损 | 批量前 3 | AI 补充、合规假设、买卖盘细节 | 可交易性/机会强度 | 折叠次级指标 |
| 设置 | 影响交易的项（风控阈值/数据源/最小收益） | — | 因子权重、ML 容量、数据覆盖率 | 每项"会影响什么" | 分组单列，管理项收起 |

---

## 5. 文案优化方案（新旧对照）

| 旧文案 / 原文 | 新文案 | 说明 |
|---|---|---|
| 推荐 / 重点推荐 / 重点跟踪推荐 | **重点观察** / **今日主看（观察）** | 去除"推荐买入"暗示；除非 `buy_now/soft_buy_now` 不用"买" |
| 接近买点 | **接近买点（观察类·未到买入）** | 必须显式标观察，不能让人当买入结论 |
| 观察池 / 观察确认 | **观察提醒（不是买入建议）** | 明确非买入 |
| 前排极精选 | **前排极精选（只观察，不参与买入排序）** | 保留身份名 + 补普通话副标 |
| 前排加权 | **前排加权（模拟验证中，未接真实排序）** | 同上 |
| Shadow（如 `Shadow 82`） | **影子分 82（仅验证，不计入真实排序）** | 去英文 |
| Paper / Paper验证 | **模拟盘 / 模拟验证中** | 去英文 |
| OOS / OOS阶段 / OOS结论 | **样本外 / 样本外阶段 / 样本外结论** | 全站统一（ValidationPanel 已用"样本外"） |
| needs_validation | **仍需验证** | 中文化状态码 |
| candidate_production | **可进入生产候选** | 中文化 |
| paper_small | **小仓模拟** | 中文化 |
| positive_t_buy | **分钟级正向买点** | 中文化 |
| walk-forward | **滚动验证（按时间逐段向前验证）** | 通俗 |
| tick data insufficient | **逐笔成交数据不足（结果仅供参考）** | 通俗 + 风险提示 |
| 交易条件（tradability_score） | **可交易性** | 通俗 |
| 每日信号等权收益（如"5日达标率/平均收益"） | **信号等权（非真实组合收益）** | §6.6 防止当成组合收益 |
| 影子胜率 | **跟踪胜率（非真实成交）** | 防与真实模拟收益混 |

> 强制规则：仅 `buy_now`、`soft_buy_now` 可出现"可买/试买"字样；`near_entry`、`observe_confirmed`、watch、front_row_only 一律带"观察/提醒/不是买入"。

---

## 6. 布局优化方案

- **应合并的卡片**：分析页 hero 的 `Callout` 并入 `WorkspacePageIntro`；优先榜英雄 pill 与 MetricGrid 合一；Paper 的 `OOS阶段+OOS结论` 合一；监控"榜单前三"并入"今日重点"。
- **应折叠的区域**：回测二级分析（样本外/归因/优化/ML 容量）、Paper 逐笔复盘与执行门禁、监控复盘全文与小时快照、分析 AI/合规。
- **应默认隐藏的表格列**：策略跟踪"专业审计"列、"信号后表现/适合持有"次级三件套、Paper 逐笔复盘表。
- **应合并的标签**：卡片 `badges`+`subBadges` 统一限 2 个关键标签，其余进详情；策略跟踪每格多 Tag 改为 1 主 Tag。
- **应降低首屏高度的页面**：监控工作台、回测、Paper（首屏只留结论 + 1 张核心图/表）。
- **需要移动端单独布局的页面**：策略跟踪（表→卡片行）、Paper（横滚表→纵向键值对）、回测（多面板→单列折叠）。
- **通用整齐度**：
  - 卡片/表格/标签/按钮统一间距（用已落地的 `--sp-*` token）。
  - 长文本统一 `text-overflow: ellipsis` + `title`，或进详情，不得撑破行高（`details` 长串是当前主因）。
  - 数字 / 收益率 / 价格右对齐 + `tabular-nums`（项目已在表格 `td` 全局启用，卡片内数值也应套用）。
  - 卡片高度固定槽位，避免 `VirtualCardList estimateSize` 与真实高度不符导致滚动跳动。
  - 空 / 加载 / 错误态用统一 `StateViews`（已存在），保持版面稳定。

---

## 7. 实施优先级

### P0（必须先改：直接影响理解或误导用户）
1. 文案中所有"推荐/接近买点/观察池"按 §5 改为明确的"买入类 / 观察类"措辞；强制规则落到 [signalStateCopy.ts](frontend/src/features/strategy-tracking/signalStateCopy.ts)、[uxClarity.ts](frontend/src/utils/uxClarity.ts)、卡片与优先榜文案。
2. Paper 绩效**显式三分区**：真实模拟组合 / 影子跟踪 / 信号等权，杜绝混读（§6.6）。
3. Paper 英文状态码（OOS/needs_validation/positive_t_buy/影子）全部中文化；执行门禁长句移出 InfoPill value（防溢出遮挡）。
4. 优先榜卡片去重（双质量分、预期=仓位、板块/止损多显），`details` 11 段拆短。

### P1（应该改：明显降噪）
5. 策略跟踪表默认 6 列、`scroll.x≤1040`，「当前结论+为什么」合并，`signalStateHelpText` 移 tooltip。
6. 优先榜英雄 pill 与 MetricGrid 去重；动作计数并入 Tab 角标。
7. 分析页去除 decisionTitle / executionText / invalidText 的重复渲染。
8. 回测二级分析默认折叠，`OOS→样本外`、`walk-forward→滚动验证`、`tick→逐笔成交` 全站统一。

### P2（可后续改：体验优化）
9. 监控工作台首屏精简 + 复盘/快照折叠（注意该文件已超行数阈值，按"只小修"处理）。
10. 设置页普通/管理分层，内部调参移"高级信息"。
11. 策略跟踪 / Paper / 回测移动端专属布局（表→卡片行 / 纵向键值对 / 单列折叠）。

---

## 8. 验收标准

- **更简洁**：每个重点页面首屏可在 3 秒内说出"今天该看什么"；一屏核心结论 ≤ 1–3 个。
- **信息完整可查**：被隐藏字段都能在 详情抽屉 / 展开 / tooltip / Popover 找到；买入类/观察类信号、风险原因、策略线身份、失效条件均未删除。
- **无遮挡/挤压/折叠/重叠**：无长文本撑破行高；无长句塞进 pill；无标签无限堆叠；无父容器裁切后看不全。
- **买/观清晰**：任意页面都能一眼区分"可买"与"只观察"；无任何观察类信号被写成"推荐买入"。
- **收益口径正确**：真实模拟组合收益 与 信号等权 / 影子跟踪 收益分区展示，不混表（§6.6）。
- **桌面端可扫描**：主表格默认列不超载，核心列不被横滚淹没；数字右对齐等宽。
- **移动端无横向溢出**：策略跟踪 / Paper / 回测在 375px 宽下无横向滚动条；可用 `npm run smoke:responsive` 回归 0 溢出。
- **状态稳定**：空 / 加载 / 错误态版面不跳动。

---

## 9. 不改代码声明

- 本次**只输出方案**，未修改任何前端/后端代码。
- 未修改任何配置（含 `settings.json`、构建配置、feature flag）。
- 未生成任何实现补丁、未运行构建或部署。
- 未删除、格式化或移动任何源文件；仅新增本审查报告于 `docs/reports/`。
