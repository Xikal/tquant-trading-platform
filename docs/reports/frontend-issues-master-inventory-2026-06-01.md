# 前端问题总账（全量发现清单 + 修改意见）

- 状态：审查结论 / 总账（**仅文档，未改代码**）
- 适用范围：Web 前端 `frontend/src` 全量；汇总本次排查全过程发现的所有前端问题
- 最后核验日期：2026-06-01
- 数据范围：`codex/phase4-phase5-architecture` 分支当前代码静态核对（`git status` 干净）
- 口径定义：状态分 ✅已修复 / 🟡进行中 / ⬜待办 / 👁观察（设计如此或低优先）
- 是否可作生产依据：可作为前端治理排期总索引；不改变任何后端口径
- 后续动作：见 §8；详细方案见 §0 关联文档

---

## 0. 概览

### 0.1 关联详细文档（深入方案在这些文件，本总账只做索引 + 补全）
| 主题 | 文档 |
|---|---|
| 视觉重构（设计系统/侧栏/暗色，Phase 1–5） | `docs/frontend-ui-redesign-development-plan-2026-05-31.md` |
| Phase 4（组件原语 + ECharts + 内联迁移） | `docs/frontend-ui-redesign-phase4-development-plan-2026-05-31.md` |
| 信息密度优化（7 个重点页面字段级，含文案对照表） | `docs/reports/frontend-information-density-optimization-plan-2026-06-01.md` |

### 0.2 现状护栏快照（实测）
| 指标 | 棘轮基线（文件记录） | 当前实测 | 说明 |
|---|---:|---:|---|
| 内联 `style={{}}` | 181 | **149** | 迁移进行中 |
| `CSSProperties` 文件 | 43 | **38** | 迁移进行中 |
| `<12px` 字号 | 0 | **0** | 已清零并锁定 |
| 硬编码 hex（ts/tsx） | 422 | **276** | 迁移进行中 |
| CSS 硬编码 hex | — | **0** | 已收敛到 token |
| `workspace.css` 行数 | — | **2356** | 超「必须拆分 700」阈值 3 倍 ⚠️ |
| `MonitorPage.tsx` 行数 | — | **1094** | 超 React 页面「必须拆分 600」 ⚠️ |

> 注：棘轮基线文件（181/422）已落后于实测（149/276），迁移后未重新 `--update-baseline` 锁定（见 B6）。

### 0.3 统计
- ✅ 已修复 15 项（主要是 Phase 1–5 视觉 + 401 鉴权 Bug）
- 🟡 进行中 4 项（内联样式/hex/原语迁移、ECharts 接入）
- ⬜ 待办 21 项（信息密度 13 + 代码健康 5 + 响应式 3）
- 👁 观察/设计如此 3 项

---

## A. 设计系统 / 视觉一致性（多数已修，留档）

| ID | 问题 | 位置 | 严重度 | 状态 | 修改意见 |
|---|---|---|---|---|---|
| A1 | 设计 Token 多源冲突（`workspace.css :root` + `antdTheme.ts` + 未引用的死 `tokens.css`） | styles/ + ui/theme | 高 | ✅ Phase 1 | 已用 `ui/theme/tokens.ts` 单一源 + antd `cssVar` 收编；保持 CSS 只写 `var(--token)`，护栏禁止再出现第二套 `:root` 颜色定义。 |
| A2 | 主色冲突：金 `#d6a55c` vs 藏青 `#0B1F3A`，无单一主色 | tokens / antdTheme | 高 | ✅ Phase 1 | 主色定为交互蓝 `#2563EB`，藏青作 `--brand-ink`（侧栏），金色仅 AI/点睛；改色相只动 `tokens.ts` 一处。 |
| A3 | antd 组件色与手写 CSS 对不上（脏感） | 全站 | 高 | ✅ Phase 1 | 开启 antd `cssVar`，手写 CSS 复用 `--ant-*`；新组件禁止硬编码色值。 |
| A4 | 满屏 10–11px 小字（145 处 `<12px`） | 41 文件内联 | 高 | ✅ Phase 2 | 基准 14px、下限 12px（`--fs-*` 阶梯）；护栏 `smallFonts` 锁 0，CI 阻止再现 `fontSize<12`。 |
| A5 | 字重 800/900 滥用 | 多文件 | 中 | ✅ Phase 2 | 字重统一 ≤700，表头 600；后续组件沿用。 |
| A6 | 圆角 8/9/10/12/14 五种混用 | 全站 | 中 | ✅ Phase 2 | 收敛为 `--radius-sm/md/lg`(6/10/14)，禁止杂值。 |
| A7 | 顶栏深蓝渐变 + `0 12px 28px` 重投影 + 金色选中 | workspaceShellStyles | 中 | ✅ Phase 3 | 顶栏改 `--bg-elevated` + 1px 描边 + `--shadow-1`，删渐变与重投影。 |
| A8 | 一级导航横排拥挤、不耐扩展 | Topbar | 中 | ✅ Phase 3 | 改 `AppSidebar` 左侧可折叠侧栏，移动端抽屉；娱乐元素收进用户菜单。 |
| A9 | 无暗色模式（但 `theme-color` 是深色，割裂） | 全站 | 中 | ✅ Phase 5 | `themeStore` + antd `darkAlgorithm` + `[data-theme=dark]`；保持浅/深两套 token 值同步，图表跟随重建。 |
| A10 | `tokens.css` 残留已卸载的 antd-mobile `--adm-*` 死变量 | tokens.css | 低 | ✅ Phase 1 | 已删；后续卸载任意库时同步清其遗留 CSS 变量。 |
| A11 | `foundation/tokens.css` 未被任何文件 import（死文件） | tokens.css | 中 | ✅ Phase 1 | 已被 `main.tsx` 引入为唯一源；保持导入顺序 `reset → tokens → workspace`。 |

---

## B. 代码健康 / 技术债

| ID | 问题 | 位置 | 严重度 | 状态 | 修改意见 |
|---|---|---|---|---|---|
| B1 | 内联 `style={{}}` 仍 149 处 | 多文件 | 中 | 🟡 | 按 Phase 4 分批用原语（`Panel/PriceText/Chip/StatTile`）/`var(--token)` 替换；每批跑护栏并降基线。 |
| B2 | `CSSProperties` 常量文件仍 38 个 | settings/workspace-shared 等 | 中 | 🟡 | 能用原语的删常量文件，余下迁 CSS Module（`*.module.css`）；避免新增内联样式集中文件。 |
| B3 | 硬编码 hex 仍 276 处 | 多文件 | 中 | 🟡 | DOM 用 `var(--token)`；图表 canvas 用 `tokens.ts` JS 值；行情色只经 `PriceText`（护栏已限制）。 |
| **B4** | **`workspace.css` 2356 行**，超「必须拆分 700」3 倍 | styles/workspace | **高** | ⬜ | 拆为 `styles/base.css` + 各 feature 的 `*.module.css`；新样式禁止再堆此文件；拆分保持行为等价并配快照回归。 |
| B5 | `MonitorPage.tsx` 1094 行，超「必须拆分 600」 | features/monitor | 高 | ⬜ | 按"page/hook/panel/table"拆（复盘区、ETF 区、右侧速览各成组件）；遵循"只小修不扩写"，拆时不改行为。 |
| B6 | 棘轮基线文件过时（记 181/422，实测 149/276） | scripts/css-guard-baseline.json | 低 | ⬜ | 迁移完一批就跑 `node scripts/check-css-guard.mjs --update-baseline` 锁住已得收益，防回升。 |
| B7 | `FactorMiningTab` 及整个 `factor-mining/` 目录死代码（无外部 import/渲染） | features/factor-mining | 中 | ⬜ | 先 `rg FactorMiningTab` 确认无引用→整目录删除（降包体+hex），或明确要保留则接回设置页并补 `onAuthRequired`。 |
| B8 | React Query `monitorWorkspaceOptions/useMonitorWorkspaceQuery` 死路径（配 `refetchInterval:30s` 但无人 mount） | state/serverQueries/monitor.ts | 低 | 👁 | 删除死导出，避免日后误用时与命令式 `fetchMonitorData` 重复轮询打接口。 |
| B9 | `package.json` capacitor 依赖残留 9 处 | package.json | 低 | 👁 设计如此 | `responsiveSingleCodebase.test.tsx` 强制保留为响应式外壳——**不删**；如确要移除需同步改该测试与 `cap:*` 脚本。 |
| B10 | ECharts 图表硬编码色 / 与界面两张皮 / canvas 不能用 CSS 变量 | features/backtest 图表、ui/charts | 中 | 🟡 | `echartsTheme.ts` 已建；逐图删 option 里的 `#hex` 改走主题/`tokens.ts`；`ChartIsland` 监听 `themeStore.mode` 做 dispose+重建。 |

---

## C. 功能 / 鉴权 Bug

| ID | 问题 | 位置 | 严重度 | 状态 | 修改意见 |
|---|---|---|---|---|---|
| C1 | 监控轮询 `Promise.allSettled` 吞 401，不识别不登出 → 会话过期后每 30s 持续刷 401、不回登录页 | useMonitorData.ts | 高 | ✅ 已修 | 已在 `fetchMonitorData` 识别 401 → 调 `onAuthRequired()` 登出；保持所有轮询 hook 都接入 `onAuthRequired`。 |
| C2 | `useSettingsData` 同款吞 401（按需触发，不刷屏但不登出） | useSettingsData.ts | 中 | ✅ 已修 | 已把 401 `throw` 给外层 `withLoading` 统一登出；非鉴权错误仍只 `setError`。 |
| C3 | `useAnalysisData` / `usePaperTrading` 鉴权处理 | 同上 | — | 👁 本来正确 | 维持现状作为模板；新数据 hook 一律复用「401→rethrow/`onAuthRequired`」模式，禁止用 `allSettled` 静默吞错。 |

---

## D. 信息密度 / 展示（详见信息密度优化文档 §3 字段级表）

| ID | 问题 | 位置 | 严重度 | 状态 | 修改意见 |
|---|---|---|---|---|---|
| D1 | 同值字段重复：质量 ★+数字；「预期」=「建议仓位」(`suggested_position_text`)；板块/止损单卡显 2–3 次 | StockCard / workspaceViewModels | 高 | ⬜ | 质量分只留数字（hover 显星级）；「预期/建议仓位」合并为一项；板块、止损每卡只出现一次。 |
| D2 | 优先榜卡 `details` 用 `/` 拼 **11 段** + ≤6 badges + 子标签 + 执行提示 | workspaceViewModels L28–40 | 高 | ⬜ | 卡面只保留固定槽位（动作 / 价格涨跌 / 买入区 / 止损 / 风险 / 1 个关键标签）+ 1 句主因；其余进详情抽屉。 |
| D3 | 策略跟踪表 9–10 列 × 每格 3 行堆叠，`scroll.x=1360` 强制横滚；「当前结论/信号性质/为什么」三列重叠 | StrategyTrackingTable | 高 | ⬜ | 默认压到 6 列、`scroll.x≤1040`；「当前结论+为什么」合并为「结论与原因」；`signalStateHelpText` 移 tooltip。 |
| D4 | Paper ETF-T0：英文状态码 + 整段长句塞进 `InfoPill` value（版式破裂）+ 收益口径混读 | PaperTradingPerformance | 高 | ⬜ | 状态码中文化；执行门禁长句改 Popover/Collapse，不放 pill；真实模拟 / 影子 / 样本外收益分三卡。 |
| D5 | 分析页 8 panel，`decisionTitle/executionText/invalidText/statusText/风险` 多处重复渲染 | AnalysisPage | 中 | ⬜ | 删 hero `Callout` 与 Collapse 内和 decision 区重复的 execution/invalid；identity 区 metric 由 7 压到 5。 |
| D6 | Playbook 英雄 pill 与 9 项 MetricGrid 重复、5 个动作计数与 Tab 角标重复 | PlaybookPage | 中 | ⬜ | 删 MetricGrid 的「全量深筛/数据状态」（英雄区已有）；动作计数并入 CandidateTabs 角标，MetricGrid 只留「可执行/真实成交样本/5日达标率」。 |
| D7 | 监控工作台 ~8 区块纵向堆叠、"盘中 Pulse"标题重复、首屏看不到核心结论 | MonitorPage | 中 | ⬜ | 首屏只留「今日有无买点 + 持仓动作 + 优先榜前 3」，复盘/小时快照折叠；去掉重复标题（结合 B5 拆分一起做）。 |
| D8 | 回测 20+ 面板一屏铺开、半中半英术语 | features/backtest | 中 | ⬜ | 首屏只留「结论(四档)+净值+收益/回撤/Sharpe/胜率」；样本外/归因/优化/ML 容量进 Tabs/Collapse。 |
| D9 | 设置页普通用户与管理调参（因子权重/ML 容量/数据覆盖率）混排进首屏 | features/settings | 中 | ⬜ | 普通/管理分层：调参与内部字段移「高级信息」默认隐藏；策略展示项与账号/数据源/风控分组隔离。 |
| D10 | `badges`+`subBadges` 无上限堆叠，撑破行高 | StockCard | 中 | ⬜ | 卡面限 2 个关键标签（如「龙头#x」「N 策略命中」），其余进详情；标签容器固定高度。 |
| D11 | 专业审计字段（`future_leak_check/data_cutoff_at/posterior_start_date`）作为列出现 | StrategyTrackingTable | 低 | 👁 已门控 | 保持 `viewMode=professional` 才显示，默认隐藏；不要进入新手视图首屏。 |
| D12 | 卡片质量分前缀 `Shadow xx`/`观察 xx`、`Paper验证` 等英文/内部词进卡面 | workspaceViewModels | 中 | ⬜ | `Shadow xx`→「影子分 xx（仅验证）」；`Paper验证`→「模拟验证中」；策略线名保留 + 加普通话副标。 |
| D13 | 长文本无统一省略，破坏布局 | 多处 | 中 | ⬜ | 统一 `text-overflow: ellipsis` + `title`，或整段进详情；禁止长串撑破行高/换行遮挡。 |

---

## E. 文案 / 口径（文案对照见信息密度文档 §5）

| ID | 问题 | 严重度 | 状态 | 修改意见 |
|---|---|---|---|---|
| E1 | "推荐/重点推荐/接近买点/观察池" 易被误解为买入建议 | 高 | ⬜ | 仅 `buy_now/soft_buy_now` 用"可买/试买"；`near_entry/observe_confirmed/watch/front_row_only` 一律带"观察/提醒/不是买入"。落到 `signalStateCopy.ts`、`uxClarity.ts`、卡片与优先榜文案。 |
| E2 | 英文状态码直出：`OOS / needs_validation / candidate_production / positive_t_buy / paper_small / Shadow / Paper / 影子` | 高 | ⬜ | 全部中文化：`样本外 / 仍需验证 / 可进入生产候选 / 分钟级正向买点 / 小仓模拟 / 影子分 / 模拟盘 / 跟踪`。 |
| E3 | 收益口径混读：真实模拟组合收益 vs 每日信号等权收益 vs 影子跟踪收益 未显式分区（违反 §6.6） | 高 | ⬜ | 三类收益分区展示并各自标注口径；信号等权处加「（非真实组合收益）」，影子处加「（非真实成交）」。 |
| E4 | `walk-forward`、`tick data insufficient` 未通俗化 | 中 | ⬜ | `walk-forward`→「滚动验证（按时间逐段向前验证）」；`tick data insufficient`→「逐笔成交数据不足（结果仅供参考）」。 |

---

## F. 响应式 / 移动端

| ID | 问题 | 位置 | 严重度 | 状态 | 修改意见 |
|---|---|---|---|---|---|
| F1 | 多张 `scroll.x` 表移动端横向溢出（策略跟踪 1360、Paper 980/680、ETF 复盘） | 多表 | 中 | ⬜ | 减少默认列降低 `scroll.x`；移动端断点下表格转「卡片行」，避免横滚条。 |
| F2 | 卡片 `details` 长串窄屏炸行；`VirtualCardList estimateSize=54` 与真实高度不符 → 滚动跳动 | PlaybookPage / StockCard | 中 | ⬜ | 卡片改固定高度槽位，`estimateSize` 对齐真实高度；`details` 不进卡面（配合 D2）。 |
| F3 | 策略跟踪筛选区 5 个 Select 并排（≈700px）窄屏拥挤换行 | StrategyTrackingFilters | 低 | ⬜ | 窄屏把筛选收进「筛选」抽屉/下拉；或按组换行并给稳定间距。 |
| F4 | 主要表格在移动端未转「卡片行」，难读 | 策略跟踪/Paper/回测 | 中 | ⬜ | 给策略跟踪/Paper/回测做移动端专属布局（卡片行 / 纵向键值对 / 单列折叠）。 |

> 注：整体响应式骨架（侧栏抽屉 + 内容列）已在 Phase 3 落地，`smoke:responsive` 9 路由 ×3 视口 0 溢出；F 类问题集中在**表格/卡片内部**的内容溢出，非外壳。

---

## 8. 后续动作（按状态汇总）

### 待办优先级（建议顺序）
- **P0 直接影响理解/误导**：E1、E2、E3、D4、D1、D2。
- **P1 明显降噪**：D3、D5、D6、D8、E4、D12。
- **P2 体验/治理**：D7、D9、D10、D13、F1–F4、B4（拆 `workspace.css`）、B5、B7、B8、B6。

### 进行中（持续推进 + 每批锁基线）
- B1/B2/B3 内联样式与 hex 迁移；B10 ECharts 接主题。每批完成跑 `--update-baseline`（解决 B6）。

### 已修复（留档，勿回退）
- A1–A11 视觉/设计系统；A9 暗色；C1/C2 鉴权 401。

### 观察/设计如此
- B9 capacitor 外壳（测试强制保留）、B8 死查询路径（可删）、D11 审计列（门控隐藏）、C3 已正确的鉴权 hook。

---

## 9. 不改代码声明

- 本次**只汇总问题、补充修改意见、输出文档**，未修改任何前端/后端代码。
- 未修改配置、未生成实现补丁、未运行构建、未部署。
- 仅更新 `docs/reports/` 本总账报告；未删除/格式化/移动任何源文件。
- 文中标「✅ 已修复」的项指本次排查全过程中先前已完成的改动，非本次新增。
