# Frontend Performance Islands + Worker/WASM Development Plan

日期：2026-06-05
状态：开发计划
范围：Web 前端性能架构升级

## 1. 结论

本轮不建议整站更换框架或语言。最高投入产出比方案是：

```text
React Shell + Performance Islands + TypeScript Worker + optional Rust/WASM
```

React 继续负责路由、页面布局、表单、AntD 低频交互和 TanStack Query 数据获取；高频状态、长列表、大表、密集图表和重计算从 React 主渲染树与浏览器主线程中拆出，形成可测、可回滚、可灰度的性能孤岛。

## 2. 目标

1. 提升 `/monitor`、`/strategy-tracking`、`/paper`、`/backtest`、`/analysis` 等热页面的交互性能。
2. 降低主线程 long task、React commit、密集表格/卡片/图表渲染压力。
3. 引入可维护的新架构：React Shell、signals 实时状态孤岛、虚拟化 UI、TypeScript Worker、可选 Rust/WASM。
4. 保持 OpenAPI/generated types、AntD 页面资产、TanStack Query 数据链路和现有测试体系稳定。
5. 所有新路径必须可 feature flag 回滚，不影响平台核心功能。

## 3. 非目标与硬边界

1. 不部署。
2. 不整站切换到 Solid、Svelte、Qwik、Flutter Web 或其他框架。
3. 不修改生产策略语义。
4. 不修改 `strategy_policy.py`。
5. 不改变生产排序、生产分、priority board 语义。
6. 不为了性能放宽策略规则或改变数据口径。
7. 不绕过 FastAPI OpenAPI 与 generated types。
8. 不引入无法回滚的新运行时路径。
9. 不格式化无关文件。
10. 不让 Worker/WASM 成为唯一实现，必须保留 fallback。

## 4. 当前依据

现有前端栈：

| 能力 | 当前技术 |
|---|---|
| 应用框架 | React 18 |
| 构建 | Vite |
| UI | AntD |
| 数据获取 | TanStack Query |
| 低频状态 | Zustand |
| 高频状态基础 | `@preact/signals-react` |
| 列表虚拟化 | `@tanstack/react-virtual` |
| 图表 | ECharts |
| API 类型 | OpenAPI generated types |

现有工程规范已经要求：

1. 新表格默认使用 `DataTable`。
2. 长列表默认使用 `VirtualCardList`。
3. 高频实时状态应进入 `frontend/src/state/realtime/`。
4. API 契约以后端 OpenAPI 为事实源。
5. Web 主进程只处理页面请求、轻量查询、任务提交和状态查询；重任务应 Worker 化。

## 5. 端态架构

```text
React Shell
  - routes
  - page layout
  - forms
  - low-frequency AntD interactions
  - TanStack Query screen model fetch
        |
        v
Performance Islands
  - signals: quotes, clock, live PnL, priority board live fields
  - virtual UI: DataTable, VirtualCardList
  - chart islands: dense charts, heatmaps, high-frequency chart refresh
        |
        v
TypeScript Web Workers
  - sorting
  - filtering
  - derived view model
  - JSON normalization
  - chart downsampling
        |
        v
Rust/WASM, only after proven CPU hotspot
  - rolling stats
  - indicator batch
  - OHLCV downsample
  - score matrix
```

## 6. 技术裁决

| 方案 | 裁决 | 投入产出比 | 可维护性 | 性能收益 | 原因 |
|---|---|---:|---:|---:|---|
| React Shell 保留 | 采用 | 高 | 高 | 中 | 保留现有资产，减少迁移风险 |
| signals 实时状态孤岛 | 采用 | 高 | 高 | 高 | 仓库已有依赖，适合高频字段 |
| DataTable/VirtualCardList 虚拟化 | 采用 | 高 | 高 | 高 | 已符合工程规范，改动集中 |
| TypeScript Worker | 采用 | 高 | 高 | 高 | 主线程减压明显，仍保持 TS 可维护性 |
| Canvas/WebGL 图表孤岛 | 按需采用 | 中 | 中 | 高 | 只用于密集高频图表 |
| Rust/WASM | 延后采用 | 中 | 中 | 很高 | 只用于已证明 CPU-bound 的纯计算 |
| SolidJS 局部孤岛 | 最后备选 | 中 | 中低 | 高 | 第二框架会增加维护成本 |
| 整站换框架 | 不采用 | 低 | 低 | 不确定 | 重写成本高，不能直接解决数据/图表/主线程瓶颈 |

## 7. 分阶段开发计划

### P0. 前端性能基线

新增报告：

```text
docs/reports/frontend-performance-baseline-2026-06-05.md
```

覆盖页面：

1. `/monitor`
2. `/strategy-tracking`
3. `/paper`
4. `/backtest`
5. `/analysis`

采集指标：

1. 首次进入耗时。
2. 二次进入耗时。
3. 路由切换耗时。
4. main thread long task 数量。
5. 最长 long task。
6. React commit p95。
7. DOM 节点峰值。
8. 表格/列表滚动 FPS。
9. 图表刷新耗时。
10. bundle gzip/chunk 体积。

验收：

1. 报告必须给出瓶颈分类：渲染、计算、序列化、网络、图表或状态更新。
2. 不允许凭感觉直接改架构。
3. 每个后续阶段都必须与 P0 基线对比。

### P1. React Shell 收敛

目标：React 只承担页面壳、布局、表单和低频交互。

重点文件：

```text
frontend/src/ui/table/DataTable.tsx
frontend/src/ui/list/VirtualCardList.tsx
frontend/src/features/**/*
```

任务：

1. 大表统一收敛到 `DataTable`。
2. 长卡片列表统一收敛到 `VirtualCardList`。
3. 移除非业务性的 `.slice(0, N)` 截断。
4. 页面拆成 page、hook、panel、row、card、cell。
5. 行、卡片、单元格使用 memo 叶子隔离。
6. store selector 保持窄字段订阅。

验收：

1. 大表 DOM 节点不随数据量线性增长。
2. 长列表滚动不卡顿。
3. 一次行情刷新不触发整页重渲染。
4. 表格排序、筛选、固定列、空态、错误态不回归。

### P2. 实时状态性能孤岛

重点目录：

```text
frontend/src/state/realtime/
frontend/src/ui/realtime/
```

任务：

1. 高频字段进入 signals。
2. TanStack Query 只管稳定 screen model。
3. Zustand 只管低频 UI 状态。
4. 高频价格、时钟、浮盈浮亏、priority board live fields 不进入 page-level props。
5. 禁止新增 `<=1000ms` 定时器写入全局 store。

验收：

1. 高频刷新只更新对应 leaf cell。
2. React commit 数量随变化项规模增长，而不是随页面规模增长。
3. 关闭 feature flag 后可恢复旧路径。

### P3. TypeScript Worker 计算层

建议新增结构：

```text
frontend/src/workers/
  protocol.ts
  workerClient.ts
  monitorCompute.worker.ts
  strategyTrackingCompute.worker.ts
  chartDownsample.worker.ts
  __tests__/
```

任务：

1. 把大数组排序、过滤、派生、normalize、downsample 移到 Worker。
2. Worker 输入/输出使用 generated API types 派生类型。
3. Worker 不做网络请求。
4. Worker 不修改业务事实源。
5. 小数据量保留同步路径，避免序列化成本。
6. Worker 输出加快照测试，与旧同步逻辑保持一致。

验收：

1. 主线程 long task 明显下降。
2. Worker 往返耗时可测。
3. Worker 输出与同步路径一致。
4. Worker 失败时 fallback 到同步路径。

### P4. 图表孤岛

重点目录：

```text
frontend/src/ui/chart/
frontend/src/workers/chartDownsample.worker.ts
```

任务：

1. 普通业务图表继续使用 ECharts。
2. 高频密集图表使用 `ChartIsland`。
3. 大序列先 Worker downsample，再渲染。
4. 对多图联动、热力图、密集 K 线做独立刷新控制。

验收：

1. 图表刷新不阻塞页面输入。
2. 多图联动时 long task 下降。
3. tooltip、空态、错误态、交互行为不回归。

### P5. Rust/WASM 纯计算层

仅当 P3 后仍存在明确 CPU 热点时执行。

建议新增：

```text
rust/tquant-wasm/
frontend/src/wasm/
```

可迁移函数：

1. rolling stats。
2. indicator batch。
3. OHLCV downsample。
4. score matrix。
5. research preview 纯计算。

硬边界：

1. 不实现 UI。
2. 不读取 API。
3. 不修改生产策略语义。
4. 不替代后端事实源。
5. 必须保留 TS fallback。
6. 必须有 TS/Rust fixture 一致性测试。

验收：

1. WASM lazy load，不进入首屏主 chunk。
2. TS/Rust 输出一致。
3. WASM 加载失败自动 fallback。
4. bundle budget 不退化。

### P6. SolidJS 局部孤岛评估

只有 P1-P5 后 React commit 仍是核心瓶颈，才允许评估。

适用：

1. 高频 watchlist。
2. 实时盘口。
3. 纯展示、少交互、边界清楚的小区域。

不适用：

1. 整站迁移。
2. 表单复杂页。
3. AntD 深度页面。
4. 需要大量现有 React context 的页面。

## 8. Feature Flag

建议新增或复用：

```text
frontend_worker_compute_enabled
frontend_realtime_signals_island_enabled
frontend_canvas_chart_island_enabled
frontend_wasm_compute_enabled
frontend_solid_island_enabled
```

默认策略：

1. P1/P2 可默认开启，但保留回退。
2. P3 按页面灰度。
3. P4/P5/P6 默认关闭，验证后再启用。

## 9. 测试与验收命令

前端必须运行：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run analyze
```

如改到后端 read model、BFF 或 API，必须补充：

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

最后必须运行：

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

## 10. 成功标准

1. 热页面主线程 long task 数量下降。
2. React commit p95 至少下降 40%。
3. 大表/长列表 DOM 节点稳定。
4. 高频字段刷新不触发整页重渲染。
5. 图表密集页交互不被刷新阻塞。
6. bundle budget 不退化。
7. OpenAPI/generated types 无无关 diff。
8. 生产策略、生产排序、任务语义不变。
9. feature flag 关闭后可回退。

## 11. 输出报告

完成实施后生成：

```text
docs/reports/frontend-performance-islands-acceptance-2026-06-05.md
```

报告必须包含：

1. 实施前 `git status --short`。
2. 基线测量结果。
3. 瓶颈分类。
4. 实施改动清单。
5. Worker/signals/virtualized/chart/WASM 是否启用。
6. feature flag 和回滚方式。
7. 测试命令和结果。
8. bundle/analyze 结果。
9. 性能指标前后对比。
10. 是否影响平台功能，必须明确回答“不影响”或说明风险。
11. 未完成项和后续建议。

## 12. 回滚方式

1. 关闭对应 feature flag。
2. Worker 路径 fallback 到同步计算。
3. WASM 路径 fallback 到 TS 实现。
4. 图表孤岛 fallback 到现有 ECharts 组件。
5. DataTable/VirtualCardList 改动如有风险，保留旧分页/截断路径作为临时回退，并在报告中说明。

## 13. 实施提示词

```text
你在 /Users/j/Documents/gupiao 仓库工作。本轮目标是落地“前端性能架构升级”：React Shell + 性能孤岛 + TypeScript Worker + 可选 Rust/WASM。只考虑投入产出比、可维护性、性能，但绝不能影响平台功能、生产策略语义、生产排序和 OpenAPI 契约。

开始前必须阅读：
/Users/j/Documents/gupiao/AGENTS.md
/Users/j/Documents/gupiao/docs/engineering-conventions.md
/Users/j/Documents/gupiao/docs/frontend-rendering-performance-final-plan-2026-05-30.md
/Users/j/Documents/gupiao/docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
/Users/j/Documents/gupiao/docs/architecture/current-boundary-map.md

开始前必须执行：
cd /Users/j/Documents/gupiao
git status --short

若存在脏文件，必须先看相关 git diff，只允许做本轮性能架构相关的最小改动；不得覆盖、回退或格式化用户已有改动。

硬边界：
1. 不部署。
2. 不修改生产策略语义。
3. 不修改 strategy_policy.py。
4. 不改变生产排序、生产分、priority board 语义。
5. 不绕过 OpenAPI/generated types。
6. 不引入整站框架重写。
7. 不为了性能改业务规则。
8. 不格式化无关文件。
9. 不新增无法 feature flag 回滚的新路径。
10. 不把 Worker/WASM 作为唯一实现，必须保留 fallback。

目标端态：
- React 保留为 Shell：路由、页面布局、表单、AntD 低频交互、TanStack Query 数据获取。
- 高频字段进入 signals 性能孤岛。
- 大表统一 DataTable，长列表统一 VirtualCardList。
- 排序、过滤、派生、normalize、图表 downsample 进入 TypeScript Worker。
- Rust/WASM 只在明确 CPU 热点存在时用于纯数值计算，并保留 TS fallback。
- 普通图表继续 ECharts；高频密集图表才做 ChartIsland。

执行步骤：

A0 基线测量：
生成 docs/reports/frontend-performance-baseline-2026-06-05.md。
覆盖 /monitor、/strategy-tracking、/paper、/backtest、/analysis。
记录首次进入、二次进入、路由切换、main thread long task、React commit p95、DOM 节点峰值、滚动 FPS、图表刷新耗时、bundle gzip/chunk 体积。
先分类瓶颈：渲染、计算、序列化、网络、图表、状态更新。不能凭感觉改架构。

A1 React Shell 收敛：
检查 frontend/src/ui/table/DataTable.tsx、frontend/src/ui/list/VirtualCardList.tsx 和热页面使用情况。
大表统一走 DataTable；长卡片列表统一走 VirtualCardList；移除非业务性的 slice 截断。
页面拆成 page/hook/panel/row/card/cell；行、卡片、单元格用 memo 叶子隔离；store selector 保持窄字段订阅。
不得改变展示语义和数据口径。

A2 实时状态性能孤岛：
扩展 frontend/src/state/realtime/ 和 frontend/src/ui/realtime/。
高频价格、时钟、浮盈浮亏、priority board live fields 使用 signals；TanStack Query 只管稳定 screen model；Zustand 只管低频 UI 状态。
禁止新增 <=1000ms 定时器写入全局 store。

A3 TypeScript Worker：
新增或扩展 frontend/src/workers/：
protocol.ts、workerClient.ts、monitorCompute.worker.ts、strategyTrackingCompute.worker.ts、chartDownsample.worker.ts、__tests__/。
把排序、过滤、派生、normalize、downsample 移到 Worker。
Worker 输入/输出使用 generated API types 派生类型；Worker 不做网络请求；小数据量保留同步路径；Worker 失败 fallback 到同步路径。
必须写 Worker 输出一致性测试。

A4 图表孤岛：
普通图表继续 ECharts。
只有高频密集图表新增 ChartIsland 和 Worker downsample。
保证 tooltip、空态、错误态、交互行为不回归。

A5 Rust/WASM 评估：
仅当 A3 后仍有明确 CPU 热点时才执行。
如执行，新增 rust/tquant-wasm/ 和 frontend/src/wasm/。
只迁移 rolling、indicator batch、OHLCV downsample、score matrix 等纯计算。
必须保留 TS fallback 和 TS/Rust fixture 一致性测试。
WASM 必须 lazy load，不进入首屏主 chunk。

Feature flag：
新增或复用：
frontend_worker_compute_enabled
frontend_realtime_signals_island_enabled
frontend_canvas_chart_island_enabled
frontend_wasm_compute_enabled
frontend_solid_island_enabled
默认：P1/P2 可开但可回退；P3 按页面灰度；P4/P5 默认关闭。

验收命令必须运行：
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run analyze

如改到后端 read model、BFF 或 API：
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q

最后必须运行：
cd /Users/j/Documents/gupiao
git diff --check
git status --short

输出报告：
生成 docs/reports/frontend-performance-islands-acceptance-2026-06-05.md，包含：
1. 实施前 git status。
2. 基线测量结果。
3. 瓶颈分类。
4. 实施改动清单。
5. Worker/signals/virtualized/chart/WASM 是否启用。
6. feature flag 和回滚方式。
7. 测试命令和结果。
8. bundle/analyze 结果。
9. 性能指标前后对比。
10. 是否影响平台功能，必须明确回答“不影响”或说明风险。
11. 未完成项和后续建议。

最终回复必须包含：
- 完成了哪些架构升级。
- 改动文件清单。
- 测试结果。
- 性能指标前后对比。
- 是否影响平台功能：明确回答“不影响”或说明风险。
- 未处理项和需要用户确认项。
```

## 14. 参考资料

1. MDN Web Workers: https://developer.mozilla.org/docs/Web/API/Web_Workers_API/Using_web_workers
2. wasm-bindgen Guide: https://wasm-bindgen.github.io/wasm-bindgen/reference/index.html
3. Solid fine-grained reactivity: https://docs.solidjs.com/advanced-concepts/fine-grained-reactivity
4. React Compiler: https://react.dev/learn/react-compiler
