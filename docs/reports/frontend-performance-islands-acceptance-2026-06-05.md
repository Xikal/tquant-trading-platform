# Frontend Performance Islands Acceptance - 2026-06-05

## 1. Pre-change Git Status

实施前：

```text
?? docs/frontend-performance-islands-worker-wasm-development-plan-2026-06-05.md
```

该文件为开始前已有未跟踪相关文档，本轮未删除、未回退、未清理。

## 2. Baseline

基线 bundle：

| Metric | Before |
| --- | ---: |
| first_screen_js_gzip_kb | 319.76 |
| total_gzip_kb | 807.12 |

基线 render profile：

| Path | Max Scroll Frame ms | Avg Scroll Frame ms | Long Tasks |
| --- | ---: | ---: | ---: |
| `/monitor` | 33.10 | 31.66 | 0 |
| `/strategy-tracking` | 34.10 | 31.74 | 0 |
| `/paper` | 32.50 | 30.84 | 0 |

## 3. Bottleneck Classification

最终 5 页 profile 全部 `ok=true`，未发现 main-thread long task。当前瓶颈分类：

| Path | Classification |
| --- | --- |
| `/monitor` | within_budget |
| `/strategy-tracking` | within_budget |
| `/paper` | within_budget |
| `/backtest` | within_budget |
| `/analysis` | within_budget |

生产 preview 下 React Profiler callback 没有 emit commit 样本，`react_commit_p95_ms=0` 表示无可用样本，不代表伪造的 0ms commit。已保留 `PerformanceProfilerProbe`，后续如启用 React profiling build，可直接采样 commit p95。

## 4. Implementation Changes

- React Shell：保留 React 路由、页面布局、AntD 低频交互和 TanStack Query/server state；未引入框架重写。
- Realtime signals island：把实时价格 SSE/signals 路径和顶部北京时间脉冲纳入 `frontend_realtime_signals_island_enabled`，旧 `VITE_LIVE_QUOTE_SIGNALS=false` 仍可回退。
- Worker compute layer：新增 `frontend/src/workers/` 协议、同步 fallback、Worker client、Worker entry 和一致性/回退测试；Worker 不做网络请求，输入/输出使用 OpenAPI generated types 派生类型。
- OpenAPI typed analysis：`/api/analyze` 与 `/api/analyze/batch` 补齐 response model，`/analyze/batch` 前端类型从 `unknown` 收敛到 generated API types。
- Chart island：普通图表继续 ECharts；回测密集净值曲线新增同步首帧 downsample + Worker 异步复算入口，普通数据量保持原数组。
- Feature flags：前后端声明 `frontend_worker_compute_enabled`、`frontend_realtime_signals_island_enabled`、`frontend_canvas_chart_island_enabled`、`frontend_wasm_compute_enabled`、`frontend_solid_island_enabled`。
- Performance profile：扩展本地 profile 覆盖 5 页、首次进入、二次进入、SPA 内部路由切换、DOM 峰值、滚动帧、long task、图表刷新和瓶颈分类。

## 5. Enabled Paths

| Capability | Status | Notes |
| --- | --- | --- |
| React Shell | enabled | 继续现有路由/布局/Query/AntD 模式 |
| DataTable / VirtualCardList | verified | lint guard 和现有页面使用保持通过；未做无关迁移 |
| Realtime signals island | enabled by default | 可用 `VITE_FRONTEND_REALTIME_SIGNALS_ISLAND_ENABLED=false` 或后端 flag 回退 |
| TypeScript Worker | enabled for safe compute paths | 排序/过滤/normalize/downsample 支持 Worker + sync fallback；回测密集净值图已接入 Worker 异步复算；分析页批量排序已迁入 Worker client；生产榜单不在前端重排，避免改变排序语义 |
| ChartIsland downsample | enabled by default | 密集回测净值曲线同步首帧 + Worker 异步复算；小数据量直接返回原数组 |
| Rust/WASM | not enabled | A3 后 Worker telemetry 未达到 CPU 热点门槛，按计划不执行；flag 默认 false |
| Solid island | not enabled | 默认 false，未引入 Solid 或整站迁移 |

Rust/WASM 启用门槛：

- 同一纯数值任务在 TS Worker 中 `elapsed_p95_ms >= 30ms` 或 `elapsed_max_ms >= 50ms`，并且重复样本可复现。
- 或页面出现可归因到纯计算的 main-thread long task / worker total p95 抖动，影响滚动、图表刷新或交互响应。
- 候选范围必须是 deterministic pure compute：rolling、indicator batch、OHLCV downsample、score matrix；不得把业务准入、生产排序、网络请求或 OpenAPI 解析迁入 WASM。
- 启用步骤必须是新增 `rust/tquant-wasm/` 与 `frontend/src/wasm/`，lazy load，TS fallback 保留，fixture 做 TS/Rust 一致性测试，`frontend_wasm_compute_enabled` 先默认 false；只有 A/B profile 证明收益稳定且无首屏包体回归后才灰度打开。

本轮实测未达门槛：`chartDownsample` 输入 1800 点，Worker `elapsed_p95_ms=0.70ms`，`elapsed_max_ms=0.70ms`，`total_p95_ms=4.10ms`，没有 long task。因此不启用 WASM 是当前投入产出比最优解。

## 6. Feature Flags And Rollback

前端 env 回退：

```text
VITE_FRONTEND_WORKER_COMPUTE_ENABLED=false
VITE_FRONTEND_REALTIME_SIGNALS_ISLAND_ENABLED=false
VITE_FRONTEND_CANVAS_CHART_ISLAND_ENABLED=false
VITE_FRONTEND_WASM_COMPUTE_ENABLED=false
VITE_FRONTEND_SOLID_ISLAND_ENABLED=false
VITE_LIVE_QUOTE_SIGNALS=false
```

后端 feature flag 同步声明，便于设置页治理：

```text
frontend_worker_compute_enabled=true
frontend_realtime_signals_island_enabled=true
frontend_canvas_chart_island_enabled=true
frontend_wasm_compute_enabled=false
frontend_solid_island_enabled=false
```

## 7. Test Results

| Command | Result |
| --- | --- |
| `cd frontend && npm test -- --run src/workers/__tests__/computeSync.test.ts src/workers/__tests__/workerClient.test.ts src/features/trading-workspace/AnalysisPage.test.tsx src/ui/charts/ChartIsland.test.ts` | 4 files / 14 tests passed |
| `cd frontend && npm run typecheck` | passed |
| `cd frontend && npm run lint` | passed |
| `cd frontend && npm test -- --run` | 72 files / 229 tests passed |
| `cd frontend && npm run api:check` | passed, OpenAPI sha256 `44affb23cbdb0b11c960e3c9c703c7edde23659aca4f164e75dbae0892977ed8` |
| `cd frontend && npm run build` | passed |
| `cd frontend && npm run analyze` | passed |
| `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_web_heavy_task_migration.py backend/tests/test_feature_flags_service.py -q` | 17 passed, 1 urllib3 LibreSSL warning |

## 8. Bundle / Analyze

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| first_screen_js_gzip_kb | 319.76 | 320.02 | +0.26 |
| total_gzip_kb | 807.12 | 810.63 | +3.51 |
| budget | passed | passed | no regression |

新增独立 `monitorCompute.worker` chunk 约 2.58KB，Worker client lazy chunk gzip 约 1.75KB。首屏预算仍通过。

## 9. Performance Before / After

最终 `frontend/dist/render-performance-profile.json`：

| Path | First Entry ms | Second Entry ms | Route Switch ms | Max Scroll Frame ms | Avg Scroll Frame ms | DOM Peak | Chart Refresh ms | Long Tasks | Bottleneck |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `/monitor` | 722 | 652 | 899 | 34.00 | 31.63 | 1294 | 0.00 | 0 | within_budget |
| `/strategy-tracking` | 623 | 608 | 863 | 32.40 | 29.91 | 224 | 0.00 | 0 | within_budget |
| `/paper` | 632 | 607 | 875 | 32.20 | 30.24 | 517 | 0.00 | 0 | within_budget |
| `/backtest` | 726 | 680 | 928 | 32.40 | 30.00 | 511 | 28.30 | 0 | within_budget |
| `/analysis` | 776 | 778 | 1035 | 32.80 | 30.50 | 399 | 0.00 | 0 | within_budget |

Worker telemetry：

| Path | Task | Source | Count | Input Max | Worker p95 ms | Worker max ms | Total p95 ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `/backtest` | `chartDownsample` | worker | 1 | 1800 | 0.70 | 0.70 | 4.10 |

可直接对比的 3 页：

| Path | Max Scroll Before | Max Scroll After | Avg Scroll Before | Avg Scroll After |
| --- | ---: | ---: | ---: | ---: |
| `/monitor` | 33.10 | 34.00 | 31.66 | 31.63 |
| `/strategy-tracking` | 34.10 | 32.40 | 31.74 | 29.91 |
| `/paper` | 32.50 | 32.20 | 30.84 | 30.24 |

## 10. Platform Impact

不影响平台功能。

本轮未修改 `backend/app/services/low_buy/strategy_policy.py`，未修改生产策略语义，未改变 low-buy / priority_board / front-row weighted / strategy tracking 生产排序，未绕过 OpenAPI/generated types，未部署、未提交、未 push。

Worker 的排序/过滤/normalize 能力作为前端计算孤岛基础设施和测试覆盖存在；回测密集净值图已接入 Worker 异步复算，分析页批量排序已接入 Worker client。生产榜单显示不在前端重排，继续以服务端/OpenAPI 数据为事实源。

## 11. Unfinished Items / Next Steps

- Rust/WASM 未执行：A3 后没有明确 CPU 热点，按计划保持默认关闭。启用前必须先满足上面的 Worker telemetry 门槛，再用 TS/Rust fixture 和 A/B profile 证明收益。
- React commit p95 在生产 preview 下没有可用样本；如需要真实 commit p95，应增加 profiling build 测量模式，而不是在生产包中伪造。
- Worker 已完成协议、fallback、一致性测试、回测密集图表真实接入和分析页批量排序接入；priority board / strategy tracking 生产排序不做前端 Worker 重排。
- 若线上真实数据量远大于本地 mock，建议用只读线上 profile 复测，但本轮明确不部署。
