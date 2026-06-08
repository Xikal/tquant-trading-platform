# Frontend Next Legacy UI Architecture Migration Development Doc - 2026-06-06

状态：可直接落地的开发文档
范围：仅 `frontend-next/` 新前端 UI/DOM 架构迁移；旧 `frontend/` 只作为对照源
结论：继续保留 SolidJS/TanStack/Worker/Charts 新技术底座，但把 `frontend-next` 的工作台壳、shared UI wrapper、页面 DOM/class 架构改成旧前端同款结构。此前只复制 CSS 不够，原因是旧视觉依赖旧 DOM、Ant 结构 class、inline layout constants、页面区域顺序和旧业务组件结构。

## 1. 本轮目标

把 `frontend-next/` 从“新视觉 + 旧 CSS 覆盖”调整为“旧前端 UI/DOM 架构 + 新前端技术底座”：

1. `/next/*` 页面视觉、密度、区域顺序、组件尺寸、文案层级向旧 `frontend/` 当前页面对齐。
2. `SolidJS + TypeScript + Vite + TanStack Router/Query/Table/Virtual + Worker + Charts` 不变。
3. `frontend/` 继续保持可回滚，不修改旧前端生产代码。
4. 后端、策略语义、生产排序、`production_score`、`priority_board` 不变。
5. 本阶段只解决 UI/DOM 架构和视觉 parity，功能 parity 继续按 `docs/reports/frontend-next-gap-audit-2026-06-06.md` 和既有 parity 文档推进。

## 2. 硬边界

1. 不部署、不切流。
2. 不修改 `strategy_policy.py`。
3. 不改变生产策略语义、生产排序、`production_score`、`priority_board`。
4. 不修改旧 `frontend/` 生产代码；旧文件只读参考，必要时复制 CSS/结构思想到 `frontend-next/`。
5. 后端默认不动；发现 UI 需要但契约缺失时写入 open items，不临时改后端。
6. 不引入 Ant Design 作为 `frontend-next` 运行时依赖；允许在本地 CSS 中保留 Ant-compatible class alias，但必须由 `frontend-next/src/shared/ui` wrapper 输出和维护。
7. 不直接使用第三方默认样式；所有通用控件必须经过 `frontend-next/src/shared/ui` wrapper。
8. Worker/WASM 只做显示层 sort/filter/derive/downsample，不做生产策略判断。
9. 机甲头像和特效只用于 `/next/paper` display/review，不参与生产排序或信号计算。

## 3. 问题根因

此前“导入旧 CSS”仍然看起来是新前端，主要有五个原因：

1. 旧前端不是纯 CSS 主题，而是 `TradingWorkspaceChrome`、`AppSidebar`、`Topbar`、`WorkspacePageContent`、Ant DOM、inline style constants、`workspace-shared` 组件共同形成的 UI 架构。
2. 新前端页面大量使用 `tq-page`、`tq-panel__head`、`tq-button`、`tq-table` 等新 DOM/class；旧 CSS 主要命中 `.panel`、`.tq-panel__header`、`.ant-*`、旧页面局部 class。
3. 旧页面区域顺序和新页面区域顺序不同，例如旧 `/analysis` 首屏是分析总览、建议、输入控制、批量分析、K 线；新 `/next/analysis` 是新的双列输入/摘要结构。
4. 旧前端很多间距来自 `workspaceShellStyles.ts` 的 inline constants，而不是 CSS 文件。
5. 懒加载页面 CSS 会后插入，容易覆盖全局旧样式。

因此正确方案不是继续堆 CSS，而是建立 **Legacy UI Contract**：新 Solid 组件输出旧前端能命中的 DOM/class/区域结构。

## 4. 目标架构

```text
frontend/ old UI sources (read only)
  styles/workspace/*
  features/trading-workspace/*
  features/workspace-shared/*
  ui/*
        |
        v
frontend-next legacy UI contract
  legacy-shell/
  shared/ui/
  shared/styles/legacy-workspace/
  shared/styles/legacy-solid-adapter.css
        |
        v
frontend-next feature pages
  Solid pages keep TanStack Query, signals, workers, charts
  DOM/class/section order follows old frontend
```

核心原则：

1. **技术底座新**：Solid、TanStack、Worker、chart islands 保持。
2. **UI 架构旧**：shell、导航、顶部栏、panel、tabs、table、stock card、empty/loading/error、modal/drawer 的 DOM/class 按旧前端重建。
3. **页面结构旧**：每页区域顺序、首屏密度、侧栏/主栏比例、表格/卡片高度按旧截图和 style spec 实现。
4. **适配层独立**：旧 CSS 原样副本放 `legacy-workspace/`，Solid DOM 适配放 `legacy-solid-adapter.css`，不在旧 CSS 副本里直接改。

## 5. 文件设计

### 5.1 新增目录

```text
frontend-next/src/legacy-shell/
  LegacyAppShell.tsx
  LegacySidebar.tsx
  LegacyTopbar.tsx
  LegacyPageContent.tsx
  legacyNavConfig.ts
  legacyShellStyles.ts
  legacyShell.test.tsx

frontend-next/src/shared/styles/
  legacy-workspace/
    workspace.css
    workspace-primitives.css
    workspace-primitives-base.css
    workspace-primitives-intro.css
    workspace-primitives-stock.css
    workspace-login.css
    workspace-login-shell.css
    workspace-login-scene.css
    workspace-login-card.css
    workspace-login-motion.css
    workspace-ritual.css
    workspace-strategy-tracking.css
    workspace-paper.css
    workspace-paper-mecha.css
    workspace-backtest.css
    workspace-key-levels.css
  legacy-solid-adapter.css
```

### 5.2 修改文件

```text
frontend-next/src/app/AppShell.tsx
frontend-next/src/app/routeTree.tsx
frontend-next/src/index.tsx
frontend-next/src/shared/ui/Button.tsx
frontend-next/src/shared/ui/Panel.tsx
frontend-next/src/shared/ui/Tabs.tsx
frontend-next/src/shared/ui/Segmented.tsx
frontend-next/src/shared/ui/DataTable.tsx
frontend-next/src/shared/ui/MetricGrid.tsx
frontend-next/src/shared/ui/StockCard.tsx
frontend-next/src/shared/ui/EmptyState.tsx
frontend-next/src/shared/ui/Modal.tsx
frontend-next/src/shared/ui/Drawer.tsx
frontend-next/src/shared/ui/Toast.tsx
frontend-next/src/shared/ui/StatusPill.tsx
frontend-next/src/features/shared/PageScaffold.tsx
frontend-next/src/features/*/*.tsx
frontend-next/src/features/*/*.css
```

### 5.3 只读参考文件

```text
frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx
frontend/src/features/trading-workspace/AppSidebar.tsx
frontend/src/features/trading-workspace/Topbar.tsx
frontend/src/features/trading-workspace/WorkspacePageContent.tsx
frontend/src/features/trading-workspace/workspaceShellStyles.ts
frontend/src/features/trading-workspace/navConfig.tsx
frontend/src/features/workspace-shared/WorkspaceComponents.tsx
frontend/src/features/workspace-shared/StockCard.tsx
frontend/src/features/workspace-shared/WorkspacePageIntro.tsx
frontend/src/ui/surfaces/Panel.tsx
frontend/src/ui/surfaces/Toolbar.tsx
frontend/src/ui/table/DataTable.tsx
frontend/src/ui/list/VirtualCardList.tsx
frontend/src/ui/feedback/StateViews.tsx
frontend/src/styles/foundation/tokens.css
frontend/src/styles/workspace/workspace.css
frontend/src/styles/workspace/*.css
```

## 6. Legacy UI Contract

### 6.1 Shell Contract

`LegacyAppShell` 必须复刻旧工作台：

1. 220px fixed sidebar。
2. 56px sticky topbar。
3. 内容列 `margin-left: 220px`。
4. 主内容 padding 使用 `var(--sp-5)`。
5. 内容内层 `max-width: 1440px; margin: 0 auto`。
6. 背景 `var(--bg-base)`。
7. 移动端保留抽屉/遮罩，但本阶段视觉验收以 Web 截图为主。

源文件：

```text
frontend/src/features/trading-workspace/workspaceShellStyles.ts
frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx
```

目标文件：

```text
frontend-next/src/legacy-shell/LegacyAppShell.tsx
frontend-next/src/legacy-shell/legacyShellStyles.ts
frontend-next/src/app/AppShell.tsx
```

### 6.2 Sidebar Contract

`LegacySidebar` 复刻旧导航：

1. 品牌区高度 56px。
2. 导航顺序与旧前端一致：实时行动、市场环境、量化分析、选股宝典、策略跟踪、回测页、模拟盘、数据中心、系统配置。
3. 选中项蓝色背景，文字白色。
4. 未选中项白色半透明，hover 轻亮。
5. 图标使用 lucide 或本地 icon wrapper，不用方块伪字符。

目标文件：

```text
frontend-next/src/legacy-shell/LegacySidebar.tsx
frontend-next/src/legacy-shell/legacyNavConfig.ts
```

### 6.3 Topbar Contract

`LegacyTopbar` 复刻旧顶部栏：

1. 左侧显示当前页面标题。
2. monitor/market 显示分段切换。
3. paper 页面保留刷新按钮位置。
4. 右侧显示机会、风险、脉冲、用户按钮。
5. 不出现 `Next Shadow` 这类新前端描述文案，除非是测试环境必要标记并放在用户按钮处。

目标文件：

```text
frontend-next/src/legacy-shell/LegacyTopbar.tsx
frontend-next/src/features/trading-workspace/UserMenu.tsx
```

### 6.4 Panel Contract

`Panel` wrapper 输出旧结构：

```tsx
<section class="panel tq-panel">
  <header class="tq-panel__header">
    <div>
      <h2 class="tq-panel__title">...</h2>
      <p class="tq-panel__subtitle">...</p>
    </div>
    <div class="tq-section-header__actions">...</div>
  </header>
  <div class="tq-panel__body tq-panel__body--md">...</div>
</section>
```

规则：

1. 兼容旧 `.panel`、`.tq-panel__header`、`.tq-panel__body--md`。
2. 现有 `class` 透传到根节点。
3. 标题区不存在时不输出空 header。
4. 页面不得手写重复 panel DOM。

### 6.5 Button/Segmented/Tabs Contract

1. `Button` 输出本地 button class，并可带 Ant-compatible alias：`tq-button ant-btn ant-btn-default`。
2. `variant="primary"` 输出 `tq-button--primary ant-btn-primary`。
3. `Tabs` 输出旧 tab 条结构，保留 `role="tablist"`、`role="tab"`。
4. `Segmented` 输出旧 Ant segmented 的密度，但样式由本地 CSS 控制。

注意：这些 `ant-*` class 只作为 CSS 命中 alias，不引入 Ant runtime。

### 6.6 Table/List Contract

`DataTable` 和 `VirtualList` 必须符合旧密度：

1. 12px 表格字体。
2. header sticky。
3. cell padding 7px 9px。
4. hover 行背景 `#f8fafc`。
5. 空状态用 dashed border。
6. 长列表通过 TanStack Virtual 保持 DOM 数稳定。

### 6.7 StockCard Contract

`StockCard` 必须输出旧 `frontend/src/features/workspace-shared/StockCard.tsx` 的关键 class：

```text
tq-stock-card
tq-stock-card__body
tq-stock-identity
tq-stock-identity__name
tq-stock-identity__meta
tq-stock-card__badge-row
tq-stock-card__score
tq-stock-card__meta
tq-stock-card__operation
tq-stock-card__risk
tq-stock-card__execution-hint
```

即使某些字段为空，也要保持结构稳定，避免布局在不同数据状态下跳动。

### 6.8 Modal/Drawer/Toast Contract

1. Modal/Drawer 使用本地 wrapper。
2. 必须 focus trap、Esc 关闭、点击遮罩关闭可配置。
3. 关闭后焦点回到触发按钮。
4. 危险操作统一走 `ConfirmAction` 二次确认。
5. Toast 统一 `aria-live="polite"`。

## 7. 页面迁移策略

### 7.1 通用流程

每个页面必须按这个顺序：

1. 读取旧页面 TSX/CSS 和 style spec。
2. 对照旧截图确认区域顺序。
3. 在 `frontend-next` 中重建 DOM/class/区域结构。
4. 保持现有 Solid query/model/worker 数据逻辑，不改业务口径。
5. 跑页面单测或 wrapper test。
6. 跑 `npm run screenshot:parity`。
7. 复制截图到验收目录。
8. 记录差异和未完成项。

### 7.2 `/next/monitor`

旧源：

```text
frontend/src/features/monitor/MonitorActionPage.tsx
frontend/src/features/monitor/MonitorPage.tsx
frontend/src/features/monitor/MonitorPage.panels.tsx
frontend/src/styles/workspace/workspace.css
```

目标：

1. 首屏恢复旧“实时监控 / 生产优先榜 / 我的持仓”结构。
2. `生产优先榜` 与 `我的持仓` 两列比例按旧截图。
3. 优先榜保持服务端顺序；前端仅做显示层 lane/filter。
4. 空状态、告警条、解读按钮、去选股宝典按钮按旧位置。

### 7.3 `/next/monitor/market`

旧源：

```text
frontend/src/features/monitor/MonitorMarketPage.tsx
frontend/src/features/monitor/MarketStateGatePanel.tsx
frontend/src/features/monitor/SectorLeaderGatePanel.tsx
```

目标：

1. 恢复市场总闸、宽度、板块、ETF T0、复盘、运行时区块。
2. 卡片密度和旧截图一致。
3. 图表区域高度固定，避免空白和布局跳动。

### 7.4 `/next/paper`

旧源：

```text
frontend/src/features/paper/PaperTradingPage.tsx
frontend/src/features/paper/PaperTradingSections.tsx
frontend/src/features/paper/PaperOrderEntryModal.tsx
frontend/src/features/paper/PaperMechaActionPanel.tsx
frontend/src/styles/workspace/workspace-paper.css
frontend/src/styles/workspace/workspace-paper-mecha.css
```

目标：

1. 恢复旧账户总览、持仓、机甲 HUD、详情 tabs 的首屏布局。
2. 机甲头像和特效可迁移，但仍 display/review only。
3. 订单/成交/风险/绩效/对账区域按旧 tabs 结构。
4. 写入仍按当前 safety guard；缺契约的写入保持 shadow-only。

### 7.5 `/next/strategy-tracking`

旧源：

```text
frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx
frontend/src/features/strategy-tracking/StrategyTrackingFilters.tsx
frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx
frontend/src/features/strategy-tracking/StrategyReviewWorkspacePanel.tsx
frontend/src/styles/workspace/workspace-strategy-tracking.css
```

目标：

1. 恢复旧筛选、列表、详情抽屉、复盘中心 tabs。
2. 新前端已有数据模型可复用，但 DOM 结构按旧 class。
3. 交易日志写入缺安全契约时保持 blocked/shadow 状态。

### 7.6 `/next/analysis`

旧源：

```text
frontend/src/features/analysis/AnalysisPage.tsx
frontend/src/features/trading-workspace/AnalysisPage.test.tsx
```

目标：

1. 恢复旧“量化分析”首屏：总览、当前建议、输入控制、批量分析、K 线与指标。
2. 输入控件尺寸和按钮位置按旧截图。
3. K 线容器深色区域按旧样式；图表逻辑继续使用新 chart adapter。

### 7.7 `/next/playbook`

旧源：

```text
frontend/src/features/playbook/PlaybookPage.tsx
frontend/src/features/low-buy/StrategyLaneTabs.tsx
frontend/src/styles/workspace/workspace.css
```

目标：

1. 恢复旧策略页签、候选分层、绩效、候选列表、详情联动。
2. 新交互可优化易用性，但不能改变 research-only/生产榜口径。

### 7.8 `/next/backtest`

旧源：

```text
frontend/src/features/backtest/BacktestDashboard.tsx
frontend/src/features/backtest/BacktestDashboard.panels.tsx
frontend/src/styles/workspace/workspace-backtest.css
```

目标：

1. 恢复旧回测 tabs、提交、运行列表、结果概览、交易明细、ETF T0、研究闭环结构。
2. 旧 Ant 表格密度通过 `DataTable` wrapper 模拟。

### 7.9 `/next/data`

旧源：

```text
frontend/src/features/data-console/DataConsolePage.tsx
frontend/src/features/data-console/*.tsx
```

目标：

1. 恢复旧数据中心分区：健康、源、覆盖率、任务、worker、修复、检查、ETF universe。
2. admin guard 和 shadow/live-safe 状态必须显式展示。

### 7.10 `/next/settings`

旧源：

```text
frontend/src/features/settings/SettingsPage.tsx
frontend/src/features/settings/SettingsLayout.tsx
frontend/src/features/settings/SettingsPageTabs.tsx
frontend/src/features/settings/SettingsPagePanels.tsx
```

目标：

1. 恢复旧设置页左侧分类、右侧配置面板。
2. MFA、风险、行业排除、LLM、factor、quant、策略治理、feature flags、audit 按旧信息架构。
3. 缺写契约的操作显示 disabled/shadow/blocked_contract_needed。

## 8. 多 Agent 分工

### Agent A - Shell/Navigation

负责：

1. `legacy-shell/*`
2. `AppShell.tsx`
3. `routeTree.tsx`
4. command palette 外壳适配
5. 兼容跳转

验收：

1. 9 个 `/next/*` 页面侧栏/顶栏一致。
2. `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 不丢 query。

### Agent B - Shared UI Contract

负责：

1. `shared/ui/*`
2. `shared/form/*`
3. wrapper 单测
4. a11y/focus 管理

验收：

1. Panel/Button/Tabs/Table/StockCard DOM contract tests 通过。
2. 页面不再手写重复基础控件。

### Agent C - Style System

负责：

1. 完整复制旧 workspace CSS 到 `legacy-workspace/`。
2. 编写 `legacy-solid-adapter.css`。
3. 清理冲突的新版页面 CSS。
4. 维护 style specs 与截图目录。

验收：

1. `screenshot:parity` 无导航/API/page error。
2. 旧 CSS 副本不被直接手改；所有适配在 adapter 中。

### Agent D - Core Pages 1

负责：

1. `/next/monitor`
2. `/next/monitor/market`
3. 生产榜顺序保护
4. monitor page screenshot parity

### Agent E - Core Pages 2

负责：

1. `/next/paper`
2. `/next/strategy-tracking`
3. 机甲 display/review 隔离
4. 写入 guard 显示状态

### Agent F - Secondary Pages

负责：

1. `/next/analysis`
2. `/next/playbook`
3. `/next/backtest`
4. `/next/data`
5. `/next/settings`

### Agent G - QA/Reports

负责：

1. 新旧截图对比。
2. DOM contract test 汇总。
3. request/SSE 重复检查。
4. 更新 acceptance/open items。
5. 最终 `git diff --check` 和 status 报告。

## 9. 执行阶段

### P0 - Baseline

1. 执行 `git status --short`。
2. 确认旧 `frontend/` 只有已知脏文件，不碰不回退。
3. 确认 style specs 和旧截图存在。
4. 跑当前 `frontend-next` `screenshot:parity`，保留现状截图作为 before。

### P1 - Legacy Shell

1. 新建 `legacy-shell/*`。
2. `AppShell` 切换到 `LegacyAppShell`。
3. 用 Solid 实现旧 `workspaceShellStyles` 常量。
4. 补 shell tests。

### P2 - Shared UI DOM Contract

1. 改 `Panel`、`Button`、`Tabs`、`Segmented`、`MetricGrid`、`DataTable`、`StockCard`、`EmptyState`。
2. 补 wrapper DOM snapshot tests。
3. 补 focus/a11y tests。

### P3 - Style Adapter

1. 确保旧 CSS 完整副本在 `legacy-workspace/`。
2. `index.tsx` 导入顺序固定为：

```ts
import "./shared/styles/tokens.css";
import "./shared/styles/legacy-workspace.css";
import "./shared/styles/legacy-solid-adapter.css";
```

3. 删除或降权和旧视觉冲突的新页面 CSS 规则。

### P4 - Pilot Pages

先做两个样板页：

1. `/next/monitor`
2. `/next/paper`

验收通过后才扩展到其他页。

### P5 - Batch Pages

按顺序：

1. `/next/strategy-tracking`
2. `/next/monitor/market`
3. `/next/analysis`
4. `/next/playbook`
5. `/next/backtest`
6. `/next/data`
7. `/next/settings`

### P6 - QA

1. 跑所有新前端命令。
2. 如本轮未改旧前端，只跑旧前端关键命令可作为最终 cutover 前置项；当前 UI-only 阶段必须至少确认旧前端未改。
3. 更新报告。

## 10. 测试要求

每批至少跑：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run screenshot:parity
```

最终跑：

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

如果本轮改了共享 wrapper 或 routing，补充：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run e2e
npm run perf:compare
```

## 11. 截图验收

输出目录：

```text
docs/reports/frontend-next-screenshots-2026-06-05/
docs/reports/frontend-next-density-review-2026-06-06/
```

每页必须提供：

1. 旧页面 reference screenshot。
2. 新页面 actual screenshot。
3. 1440x900 主截图。
4. 1280x800、768x1024、390x844 响应式捕获。
5. 视觉差异说明。

当前用户验收时优先看：

```text
docs/reports/frontend-next-density-review-2026-06-06/next-monitor.png
docs/reports/frontend-next-density-review-2026-06-06/next-monitor-market.png
docs/reports/frontend-next-density-review-2026-06-06/next-paper.png
docs/reports/frontend-next-density-review-2026-06-06/next-strategy-tracking.png
docs/reports/frontend-next-density-review-2026-06-06/next-analysis.png
docs/reports/frontend-next-density-review-2026-06-06/next-playbook.png
docs/reports/frontend-next-density-review-2026-06-06/next-backtest.png
docs/reports/frontend-next-density-review-2026-06-06/next-data.png
docs/reports/frontend-next-density-review-2026-06-06/next-settings.png
```

## 12. 性能与稳定性要求

1. Shell 和 wrapper 迁移不得显著增加首屏 JS。
2. 不引入 Ant runtime，避免 bundle 膨胀。
3. Chart/list/worker 离页必须释放。
4. SSE 连接不重复。
5. 页面切换不重复创建 worker。
6. 长列表继续虚拟化。
7. reduced motion 下禁用非必要动效。
8. 机甲动效只在 paper 可见区域运行，离页停止。

## 13. 易用性、可用性、稳定性优化原则

旧前端不合理处允许优化，但必须满足：

1. 不改变业务口径。
2. 不改变生产排序。
3. 不减少可见信息。
4. 优先减少留白、减少跳动、减少误点。
5. 对危险操作增加二次确认。
6. 对空/加载/错误/权限不足/断网/partial data 给明确状态。
7. 对用户高频动作保留键盘和快速入口。
8. 对长文案用折叠、tooltip 或抽屉，不挤压主表格。

优化必须记录在：

```text
docs/frontend-next/optimization-registry-2026-06-06.md
```

## 14. 回滚方式

1. `frontend/` 未改，所以生产回滚方式仍是继续使用旧前端。
2. 新前端 UI 架构回滚：
   - 恢复 `frontend-next/src/app/AppShell.tsx`
   - 恢复 `frontend-next/src/shared/ui/*`
   - 移除或停止导入 `legacy-solid-adapter.css`
3. 不涉及后端回滚。
4. 不涉及数据库回滚。
5. 不涉及策略回滚。

## 15. 完成定义

本开发包完成必须同时满足：

1. 9 个 `/next/*` 页面使用 Legacy Shell。
2. shared UI wrapper 输出旧 DOM/class contract。
3. 9 个页面截图接近旧页面，不再呈现新版大留白/大卡片/新视觉。
4. `frontend-next` 全量命令通过。
5. `git diff --check` 通过。
6. 明确报告旧 `frontend/` 未改、后端未改、不影响平台功能。
7. 用户完成新视觉人工验收后，才允许进入功能 parity 或 cutover 讨论。
