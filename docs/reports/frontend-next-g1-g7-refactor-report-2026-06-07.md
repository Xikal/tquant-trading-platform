# frontend-next G1-G7 Refactor Report

日期：2026-06-07

## 范围

本轮只修改 `frontend-next/` 和本报告。旧 `frontend/` 只做验证；后端、`strategy_policy.py` 未修改。不部署、不切流。

## 初始与最终 git 状态

- 初始 `git status --short`：当前 `frontend-next/` 与相关文档目录均为 untracked，未发现 tracked 旧前端/后端改动。
- 最终 `git status --short`：仍为 `frontend-next/` 与 docs/report untracked；`git diff -- frontend strategy_policy.py backend` 为 0 行。
- `git diff --check`：通过。

## G1-G7 完成情况

| 阶段 | 状态 | 结果 |
| --- | --- | --- |
| G1 timer/copy/save 文案与 guard | 完成 | 修复 `MonitorMarketPage` refresh timer cleanup、`PaperPage` copy fallback、设置/实时行动“保存”误导文案；新增边界 guard。 |
| G2 CSS 入口整理 | 完成 | 删除/防回归未引用 CSS：`legacy-next-overrides.css`、`workspace-compat.css`、`web-layout.css`；`check:css` 纳入 lint。 |
| G3 Shell variant 化 | 完成 | `LegacyAppShell` 使用 route variant；移除页面级 `.legacy-workspace-shell:has(...)` 外壳覆盖。 |
| G4 抽 shared UI | 完成 | 新增/接入 `Icon`、`PagePanel`、`DenseTable`、`StatusBadge`；`Panel` 复用 `PagePanel`；回测表格/徽标、策略徽标接入 shared UI。 |
| G5 拆 Settings/Backtest | 完成 | 新增 `SettingsPrimitives.tsx`、`BacktestPrimitives.tsx`、`backtestFormatters.ts`；`SettingsPage` 880 行，`BacktestPage` 666 行。 |
| G6 页面迁移 shared UI | 完成 | `MonitorAction`、`MonitorMarket`、`StrategyTracking`、`DataConsole` 的本地 SVG/Icon 逻辑迁移到 shared `Icon` 薄包装。 |
| G7 parity/bundle/report | 完成 | 截图 parity、bundle/perf、E2E、旧前端验证完成；本报告已生成。 |

## 新增/修改重点文件

- `frontend-next/src/shared/ui/Icon.tsx`
- `frontend-next/src/shared/ui/PagePanel.tsx`
- `frontend-next/src/shared/ui/DenseTable.tsx`
- `frontend-next/src/shared/ui/StatusBadge.tsx`
- `frontend-next/src/shared/ui/Panel.tsx`
- `frontend-next/src/features/settings/SettingsPrimitives.tsx`
- `frontend-next/src/features/backtest/BacktestPrimitives.tsx`
- `frontend-next/src/features/backtest/backtestFormatters.ts`
- `frontend-next/scripts/check-css-guard.mjs`
- `frontend-next/scripts/check-refactor-guard.mjs`
- `frontend-next/scripts/check-boundary-guard.mjs`
- `frontend-next/scripts/check-bundle-budget.mjs`
- `frontend-next/package.json`
- `frontend-next/tests/e2e/interaction-parity.spec.ts`
- `frontend-next/tests/e2e/monitor-workflows.spec.ts`
- `frontend-next/tests/e2e/smoke.spec.ts`

## 视觉与截图 parity

`npm run screenshot:parity` 通过，截图输出在：

- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/monitor-action-web.png`，similarity 0.9431
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/monitor-market-web.png`，similarity 0.9561
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/paper-web.png`，similarity 0.8688
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/strategy-tracking-web.png`，similarity 0.9503
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/analysis-web.png`，similarity 0.7767
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/playbook-web.png`，similarity 0.9157
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/backtest-web.png`，similarity 0.9152
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/data-console-web.png`，similarity 0.9567
- `/Users/j/Documents/gupiao/docs/reports/frontend-next-screenshots-2026-06-05/settings-web.png`，similarity 0.9354

响应式截图同目录包含 `1280x800-*`、`768x1024-*`、`390x844-*`。

## API/数据与请求情况

- `frontend-next npm run api:check`：通过，OpenAPI generated types 正常。
- `npm run perf:compare`：通过；监控页和市场页各 2 个 API 请求，无重复 SSE；策略跟踪 9 个 API 请求。
- 观测到环境接口残留：
  - `/api/strategy-tracking/items?range=60&board_filter=include_all&limit=120&offset=0` 返回 422。
  - `/api/settings`、`/api/settings/factor-weights` 在截图脚本环境返回 503。
- 这些错误未导致页面崩溃，属于后端/本地数据环境待确认项。

## K 线和初始技术方案核查

- `frontend-next/src/shared/charts/KlineChart.tsx` 继续使用 `lightweight-charts`。
- ECharts 仅保留在 `EchartsIsland.tsx` 低频图表 adapter。
- 新增 `check-boundary-guard.mjs`，阻止 feature 页面 K 线直接引入 ECharts，阻止 `strategy_policy.py` 和旧前端 runtime 依赖，阻止 Worker 改写生产排序字段。

## Bundle 与性能对比

- `frontend-next/dist`：约 1.5M。
- build 输出核心大块：
  - `echarts-charts` 284.02 kB / gzip 95.11 kB。
  - `echarts-components` 160.79 kB / gzip 53.79 kB。
  - `vendor` 160.64 kB / gzip 52.01 kB。
  - `tanstack` 159.23 kB / gzip 46.47 kB。
- 新 bundle guard：总 JS 约 1,189,867 bytes，低于 1.25MB 阈值。
- `perf:compare`：
  - `/next/monitor` 1718ms，DOM 230，API 2。
  - `/next/monitor/market` 732ms，DOM 271，API 2。
  - `/next/paper` 1967ms，DOM 403，API 2。
  - `/next/strategy-tracking` 1906ms，DOM 226，API 9，其中 items 接口 422。

## 测试结果

frontend-next：

- `npm run api:check`：通过。
- `npm run typecheck`：通过。
- `npm run lint`：通过，含 refactor/css/boundary/bundle guards。
- `npm test -- --run`：19 files / 81 tests 通过。
- `npm run build`：通过。
- `npm run e2e`：35 tests 通过。
- `npm run screenshot:parity`：通过。
- `npm run perf:compare`：通过。

旧 frontend：

- `npm run api:check`：通过。
- `npm run typecheck`：通过。
- `npm run lint`：通过。
- `npm test -- --run`：85 files / 299 tests 通过；命令退出码 0，输出中有一条既有 state separation guard 文本。
- `npm run build`：通过。

## 平台影响

不影响。

理由：

- 未修改旧 `frontend/` 生产代码。
- 未修改后端、`strategy_policy.py`。
- 未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
- Worker 仍只做显示层计算/降采样/排序 fallback，不做生产策略判断。
- 机甲头像/特效仅保留在 `/next/paper` 展示层。

## 回滚方式

- 默认不切流；旧 `frontend/` 仍可直接使用。
- 若要回滚本轮变更，删除或还原 `frontend-next/` 本轮改动和本报告即可，不涉及后端迁移。
- 若后续 cutover，必须另行授权并先修复策略跟踪 422、设置 503 的 API 环境问题。

## 剩余未完成/需确认项

- 需要后端/API 侧确认 `/api/strategy-tracking/items` 422 的参数契约。
- 需要后端/API 侧确认 `/api/settings`、`/api/settings/factor-weights` 本地 503 是否为环境依赖未启动。
- `analysis-web` 截图 similarity 0.7767，低于其它页面；若按严格视觉验收，可作为下一轮微调项。
- 未 cutover；是否切流仍需要用户明确授权。
