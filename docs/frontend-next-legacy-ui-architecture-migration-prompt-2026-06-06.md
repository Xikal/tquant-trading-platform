# Frontend Next Legacy UI Architecture Migration Prompt - 2026-06-06

把下面提示词复制给 Claude/Codex 多 Agent 使用。

```text
你在 /Users/j/Documents/gupiao 工作。目标：修正 frontend-next/ 视觉不贴近旧前端的问题。不要继续只堆 CSS；本轮要在保留 SolidJS/TanStack/Worker/Charts 新技术底座的前提下，把新前端 UI/DOM 架构迁移为旧 frontend/ 工作台架构。旧 frontend/ 只读参考，不得修改；不部署、不切流。

开始前执行：
cd /Users/j/Documents/gupiao && git status --short

必须阅读：
AGENTS.md
docs/engineering-conventions.md
docs/frontend-next-solid-parallel-development-plan-2026-06-05.md
docs/reports/frontend-next-gap-audit-2026-06-06.md
docs/frontend-next-legacy-ui-architecture-migration-development-doc-2026-06-06.md
docs/frontend-next/style-specs/*.md

只读参考旧前端：
frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx
frontend/src/features/trading-workspace/AppSidebar.tsx
frontend/src/features/trading-workspace/Topbar.tsx
frontend/src/features/trading-workspace/WorkspacePageContent.tsx
frontend/src/features/trading-workspace/workspaceShellStyles.ts
frontend/src/features/workspace-shared/WorkspaceComponents.tsx
frontend/src/features/workspace-shared/StockCard.tsx
frontend/src/ui/surfaces/Panel.tsx
frontend/src/ui/table/DataTable.tsx
frontend/src/ui/list/VirtualCardList.tsx
frontend/src/styles/foundation/tokens.css
frontend/src/styles/workspace/workspace.css
frontend/src/styles/workspace/*.css

硬边界：
1. 不改旧 frontend/ 生产代码，不回退旧前端既有脏文件。
2. 不改后端，不改 strategy_policy.py。
3. 不改变生产策略语义、生产排序、production_score、priority_board。
4. 不引入 Ant runtime；可用本地 Ant-compatible class alias，但必须由 frontend-next/src/shared/ui wrapper 输出。
5. 不直接用第三方默认样式。
6. Worker/WASM 只做显示层计算，不做策略判断。
7. 机甲头像/特效只用于 /next/paper display/review。
8. 页面结构、密度、文案层级按旧前端，不做视觉重设计。

实施重点：
A Shell：新增 frontend-next/src/legacy-shell/LegacyAppShell.tsx、LegacySidebar.tsx、LegacyTopbar.tsx、legacyNavConfig.ts、legacyShellStyles.ts。复刻旧 220px fixed sidebar、56px topbar、内容 max-width 1440、主内容 padding var(--sp-5)、旧导航顺序和选中态。AppShell 切到 LegacyAppShell。
B UI Contract：改 shared/ui wrapper，使 Panel/Button/Tabs/Segmented/DataTable/MetricGrid/StockCard/EmptyState/Modal/Drawer/Toast 输出旧 DOM/class contract。Panel 根用 panel tq-panel，标题用 tq-panel__header，body 用 tq-panel__body--md；StockCard 输出旧 tq-stock-card 结构；Table 恢复 12px、sticky header、7px 9px cell padding。
C Style：完整复制旧 frontend/src/styles/workspace/*.css 到 frontend-next/src/shared/styles/legacy-workspace/；新增 legacy-solid-adapter.css 只写 Solid DOM 适配。index.tsx 导入顺序：tokens.css -> legacy-workspace.css -> legacy-solid-adapter.css。不要直接改旧 CSS 副本。
D 页面：按旧截图/旧 TSX 重建 /next/monitor、/next/paper 作为样板页，验收通过后再迁移 /next/strategy-tracking、/next/monitor/market、/next/analysis、/next/playbook、/next/backtest、/next/data、/next/settings。保持现有 Query/model/API/worker 业务逻辑，不改口径。
E QA：每页开发前确认 style spec 和旧截图；每页完成后跑截图 parity，并把最新图复制到 docs/reports/frontend-next-density-review-2026-06-06/next-*.png。

验收命令：
cd /Users/j/Documents/gupiao/frontend-next
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run screenshot:parity
cd /Users/j/Documents/gupiao
git diff --check
git status --short

最终报告必须写：新增/修改文件，完成阶段，新旧视觉 parity 结果，每页截图路径，旧 frontend/ 是否未改，后端是否未改，测试结果，是否影响平台功能，剩余未完成项，是否需要用户授权 cutover。结论默认不 cutover。
```
