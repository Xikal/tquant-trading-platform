# frontend-next 运行时与体积修复报告（2026-06-08）

## 范围与边界

- 范围：`frontend-next/` O1-O5、策略展示 F1/F2/F3/F5、分离部署本地 readiness 相关最小后端静态托管开关。
- 未部署、未切流。
- 未改旧 `frontend/` 生产源码。
- 未改 `strategy_policy.py`。
- 未改变生产策略语义、`production_score`、`priority_board` 排序和口径。
- 后端仅新增 `SERVE_FRONTEND_STATIC` API-only 静态托管开关，默认 `true` 兼容旧部署。

## P0 基线

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
npm run chunk:profile
npm run css:budget
npm run css:unused-report
```

before：

| 指标 | before |
| --- | ---: |
| initial JS raw | 285,190 bytes |
| initial CSS raw | 88,546 bytes |
| dist CSS raw | 240,929 bytes |
| ECharts assets | 3 |
| ECharts raw | 457,660 bytes |
| `!important` | 23 |

## After 指标

after：

| 指标 | after | 目标 | 结论 |
| --- | ---: | ---: | --- |
| initial JS raw | 284,862 bytes | <=350,000 | 通过 |
| initial CSS raw | 16,758 bytes | 无硬阈值 | 显著下降 |
| dist CSS raw | 169,870 bytes | <=180,000 | 通过 |
| dist CSS gzip | 35,668 bytes | <=60,000 warning | 通过 |
| ECharts assets | 0 | 0 | 通过 |
| ECharts raw | 0 bytes | 0 | 通过 |
| `!important` | 23 | <=25 | 通过 |
| `tanstack-virtual` 初始加载 | false | 不进初始 HTML | 通过 |

机器报告：

- `docs/reports/frontend-next-chunk-profile-2026-06-08.json`
- `docs/reports/frontend-next-css-budget-2026-06-07.json`
- `docs/reports/frontend-next-css-unused-report-2026-06-07.json`
- `docs/reports/frontend-next-perf-compare-2026-06-08.json`

## O1/O2 运行时证据

本地后端启动：

```bash
AUTH_SECRET_KEY=local-dev-only-frontend-next-acceptance-secret-2026-06-08-with-more-than-sixty-four-characters ./scripts/run_platform_component.sh web
curl -fsS http://127.0.0.1:8000/readyz
```

readyz 返回 `status=ok`，`database=true`，`frontend_dist=true`，`frontend_next_dist=true`。

`npm run perf:compare` 结果：

| 页面 | API 请求数 | 关键结果 |
| --- | ---: | --- |
| `/next/strategy-tracking` | 2 | 只请求 `/api/auth/me` 和 `/api/bff/v1/workspace/strategy` |
| `/next/strategy-tracking` legacy items 422 | 0 | 无无故 fallback 到 `/api/strategy-tracking/items` |
| `/next/paper` | 2 | 只请求 `/api/auth/me` 和 `/api/bff/v1/workspace/paper` |
| `/next/paper` 非机甲 descendants | 82 | 虚拟列表/懒挂载生效 |

## O3 CSS 修复

修复：

1. 从 `frontend-next/src/index.tsx` 移除全局 `legacy-workspace.css`。
2. 保留 `tokens.css` 和 `legacy-solid-adapter.css` 作为全局基础。
3. 将 `StockCard` 当前实际使用的共享选择器最小迁入 `legacy-solid-adapter.css`。
4. 不执行盲目 PurgeCSS。

验证：

- `npm run css:budget`：dist CSS raw 169,870 bytes，`!important=23`。
- `npm run css:unused-report`：只作为候选报告，无批量删除。
- `npm run screenshot:parity`：9 个 `/next/*` 页面 desktop/mobile 均 captured/compared，无 navigation error、app error、failed API。

## O4 ECharts 修复

修复：

1. 新增 `frontend-next/src/shared/charts/EquitySparklineChart.tsx`，用 SVG 渲染 backtest 权益曲线。
2. `BacktestPage.tsx` 从 `EchartsIsland` 切换到 `EquitySparklineChart`。
3. 删除 `frontend-next/src/shared/charts/EchartsIsland.tsx`。
4. 从 `package.json` 和 lockfile 移除 `echarts`。

验证：

- `rg -n "EchartsIsland|echarts" frontend-next/src frontend-next/package.json frontend-next/vite.config.ts`：无源码/依赖残留。
- `npm run chunk:profile`：`echarts_assets=0`，`echarts_raw_bytes=0`。
- `src/shared/charts/__tests__/charts.test.tsx` 覆盖轻量 SVG 非空渲染和空态。

## O5 TanStack 修复

修复：

`frontend-next/vite.config.ts` 将 `@tanstack/*` 拆为：

- `tanstack-router`
- `tanstack-query`
- `tanstack-table`
- `tanstack-virtual`
- `tanstack-misc`

验证：

- `dist/index.html` modulepreload 不包含 `tanstack-virtual`。
- initial JS raw 284,862 bytes。

## P2 VirtualList 防御性修复

虽然 P1 中 `/next/paper` 非机甲 DOM 已达标，本轮仍修复源码风险：

- `scrollReady=false` 时不再渲染全部 `items`。
- 初始 fallback 只渲染首屏估算数量，默认不超过 20，支持 `initialItemLimit`。
- 新增长列表回归测试，防止初始全量渲染回流。

## P6 策略展示正确性

| 项 | 修复 |
| --- | --- |
| F1 | 回归守卫旧 `"99.2% (影子校验)"` 不回流 |
| F2 | 回归守卫旧 `"冲高未止盈 · 原低吸策略 · 影子校验一致"` 不回流 |
| F3 | `executionAssumptionRows` 优先读取后端 `execution_assumptions`；无字段时 label 为 `费率模型`，不把模型版本标为手续费率 |
| F4 | paper 机甲 HUD 仍按装饰项处理，不参与策略/绩效/排序/交易判断 |
| F5 | `buildDriftRows` 只用真实漂移字段；缺数据时显示 `"--"` / `暂无数据`，不展示假滑点、假延时、硬编码健康状态 |

验证：

```bash
npm test -- --run src/shared/ui src/shared/charts src/features/backtest src/features/strategy-tracking
npm run typecheck
```

结果：27 tests passed，typecheck 通过。

## E2E blocker 收敛

| blocker | 处理 |
| --- | --- |
| `monitor-market` 闸门模式按钮旧断言/状态反馈 | 对齐当前“空态预览/实时数据”模式；`空态预览` 选中后也带 active 状态，避免用户无法判断当前模式 |
| `playbook` 旧“今日注目核心标的”断言 | 对齐发布日口径，E2E 改为匹配“注目核心标的” |
| `backtest` 旧 ECharts canvas 断言 | 对齐轻量 SVG 权益曲线，断言 `role=img` 和 SVG 非空 |
| 移动导航遮罩关闭偶发失败 | 遮罩改为可访问 `button`，点击区域限制在侧栏外，E2E 使用“关闭导航”按钮验证 |

验证：

```bash
npx playwright test tests/e2e/app-shell-auth.spec.ts tests/e2e/page-function-matrix.spec.ts --project=chromium
npm run e2e
```

结果：关键子集 24/24 通过，完整 E2E 60/60 通过。

## 视觉证据

`npm run screenshot:parity` 通过，覆盖：

- `/next/monitor`
- `/next/monitor/market`
- `/next/paper`
- `/next/strategy-tracking`
- `/next/analysis`
- `/next/playbook`
- `/next/backtest`
- `/next/data`
- `/next/settings`

截图输出目录：`docs/reports/frontend-next-screenshots-2026-06-05/`。

## 剩余风险

1. 分离部署仅完成本地 readiness 工件，不代表已云端部署。
2. `source_css_bytes` 仍高于 180KB，但本轮目标为 `dist CSS raw <=180KB`，且 dist 已达标；source CSS 保留页面级样式和 legacy 未引用文件，避免盲删。
3. 旧 `frontend/` 工作区存在非本轮脏改动，本轮未回退、未覆盖；最终边界结论需按文件归属拆分阅读。

## 最终门禁结果

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run chunk:profile
npm run css:budget
npm run css:unused-report
npm run perf:compare
npm run screenshot:parity
npm test -- --run src/features/strategy-tracking src/features/backtest src/features/paper
npx playwright test tests/e2e/app-shell-auth.spec.ts tests/e2e/page-function-matrix.spec.ts --project=chromium
node scripts/check-boundary-guard.mjs
```

结果：

- `api:check` 通过，生成类型无 diff。
- `typecheck` 通过。
- `lint` 通过，包含 refactor/css/boundary/bundle-budget guard。
- Vitest 全量 25 files / 110 tests passed。
- 专项 Vitest 4 files / 13 tests passed。
- `build` 通过。
- Playwright 全量 60/60 passed。
- Playwright 关键子集 24/24 passed。
- `chunk:profile`、`css:budget`、`css:unused-report` 均通过。
- `perf:compare` 通过，`/next/strategy-tracking` API 请求数 2，legacy items fallback 0；`/next/paper` 非机甲 descendants 82。
- `screenshot:parity` 通过，9 个页面桌面和移动截图均无 navigation error、app error、failed API。
- `check-boundary-guard.mjs` 通过。
