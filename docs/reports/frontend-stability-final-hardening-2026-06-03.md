# 前端稳定性最终加固验收报告

状态：已完成本地代码与验证
适用范围：`frontend/` 前端稳定性、bundle 预算、热路径状态、SWR 降级
最后核验日期：2026-06-03
结论：本次只处理前端稳定性收尾，不修改后端业务逻辑、生产排序、交易/选股逻辑或投资建议边界。

## 数据范围

- 基线命令：`cd frontend && npm run analyze`
- 最终命令：`cd frontend && npm run analyze`
- 基线以任务开始时当前脏工作树为准；仓库内已有部署脚本、文档迁移和上一轮策略跟踪前端改动未被回滚。

## M0 基线

`npm run analyze` 生成 `frontend/dist/bundle-report.json`。

| 指标 | 数值 |
|---|---:|
| `first_screen_js_gzip_kb`（旧脚本口径） | 9.34 KB |
| `total_gzip_kb` | 798.36 KB |
| 最大 JS chunk | `antd-BR64pej6.js`，159.29 KB gzip |

基线 Top chunks：

| Chunk | gzip KB |
|---|---:|
| `antd-BR64pej6.js` | 159.29 |
| `echarts-charts-CK4dBMWO.js` | 99.75 |
| `antd-display-BVwdjJ9i.js` | 86.84 |
| `echarts-components-DpCUDnhF.js` | 89.55 |
| `react-vendor-AyzRAY9E.js` | 30.46 |
| `antd-feedback-BhjeLxQH.js` | 24.21 |

说明：基线脚本旧口径没有把 AntD vendor 计入 `first_screen_js_gzip_kb`。本次同步更新 `bundle-report.mjs`，最终口径把首屏 AntD vendor 计入预算门。

## 最终 Bundle 指标

| 指标 | 数值 |
|---|---:|
| `first_screen_js_gzip_kb`（新预算口径） | 319.95 KB |
| `total_gzip_kb` | 797.06 KB |
| 最大 JS chunk | `antd-controls-BaqoebOb.js`，126.46 KB gzip |
| 单 chunk 150KB gzip 预算 | 通过 |
| 首屏 350KB gzip 预算 | 通过 |

最终 Top chunks：

| Chunk | kind | gzip KB |
|---|---|---:|
| `antd-controls-BaqoebOb.js` | first-screen-js | 126.46 |
| `echarts-charts-DQW6wPOZ.js` | heavy-vendor | 99.75 |
| `antd-core-DT6dQcj8.js` | first-screen-js | 93.14 |
| `echarts-components-CwijDdWm.js` | heavy-vendor | 89.55 |
| `antd-display-Bkjv67XA.js` | first-screen-js | 49.79 |
| `react-vendor-BdaprpLK.js` | vendor | 30.74 |
| `antd-detail-CTD69MpG.js` | heavy-vendor | 26.10 |

## 完成项

- H1：`vite.config.ts` 将 AntD detail 组件拆为 `antd-detail`，并把 shell/core/display/feedback/navigation/control 分类稳定化；原单个 `antd` 159.29KB gzip 大 chunk 已消失。
- H1：新增 `frontend/src/ui/icons/index.ts`，全站 AntD 图标从按需路径集中 re-export；`@ant-design/icons` 桶导入为 0。
- H1/H4：新增 `frontend/scripts/check-bundle-budget.mjs` 与测试，接入 `npm run lint` 和 GitHub Actions frontend build 后检查。
- H2：`Topbar` 心跳迁移到 `frontend/src/state/realtime/topbarClockSignal.ts`，删除 `workspaceStore` 的 `topbarPulse/setTopbarPulse`，1 秒刷新不再写 Zustand。
- H2：`MonitorPage` 合并 Zustand selector，使用稳定 callback/list render props，降低刷新时叶子组件无意义 props 抖动。
- H3：`queryClient` 默认启用 `placeholderData: previous`、`refetchOnReconnect: true`、`refetchOnMount: false`；monitor/paper/playbook/strategy-tracking 热查询补齐 SWR 行为。
- H3：`api/base.ts` 增加 BFF `partial_errors` 统一识别和文案 helper；策略跟踪页使用统一“部分降级源”展示。
- H4：`check-refactor-guard.mjs` 增加 AntD 图标桶导入、signals 定义目录、`<=1000ms` 定时器写 store 守卫。
- H4：`docs/engineering-conventions.md` 新增前端性能预算与热路径规则。

## 未完成项 / 风险

- React DevTools Profiler 的人工提交数录制未在本地自动化环境中执行；用 `Topbar.signal.test.ts` 验证了 signal 更新不触发 workspace store 订阅广播。
- 后端 G1/G2/G3 的云端 p95 与 `bff_partial_timeout=0` 联动验收不属于本计划实施范围，本次未改后端业务逻辑。
- `npm run lint` 在 build 前会跳过 bundle budget；CI build 后显式执行 `node ./scripts/bundle-report.mjs && npm run check:bundle-budget`，本地最终验收也已在 analyze 后执行预算门。

## 验证命令结果

| 命令 | 结果 |
|---|---|
| `cd frontend && npm run api:check` | 通过；OpenAPI 导出 sha256 `6b778f722715bba6b1aba8378beb35aced215e4ba135b4f1d264027c394ad6e5`，有 urllib3 LibreSSL 第三方 warning |
| `cd frontend && npm run lint` | 通过；含 refactor/state-separation/css/bundle-budget |
| `cd frontend && npm test -- --run` | 通过；60 files / 175 tests |
| `cd frontend && npm run build` | 通过 |
| `cd frontend && npm run analyze` | 通过；`first_screen_js_gzip_kb=319.95`，`total_gzip_kb=797.06` |
| `cd frontend && npm run check:bundle-budget` | 通过；首屏 350KB 与单 chunk 150KB 预算均通过 |
| `git diff --check` | 通过 |
| `git status --short` | 已执行；仍有多处既有脏文件，详见最终交付说明 |

测试输出说明：`check-state-separation` 的违规 fixture 会在 Vitest 中打印一次 “State separation guard failed...” 文本，这是测试 guard 失败样例，不是验收失败；Vitest 最终结果为全绿。

## 生产边界

- 未修改 `strategy_policy`。
- 未产生或接入 `production_score`。
- 未替换 low-buy、priority board、front-row weighted 或任何生产排序。
- 未新增 Web 后台 loop。
- 未新增 npm 依赖。
