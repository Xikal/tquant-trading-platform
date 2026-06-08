# Frontend Next Architecture Design - 2026-06-05

状态：设计文档，未实施
目标：定义 `frontend-next/` 并行新前端架构，不影响旧前端和生产策略
最后核验日期：2026-06-05

## 执行入口

`frontend-next/` 未来作为独立 Vite/SolidJS 应用存在，先运行在 `/next/*` shadow 路由。旧 `frontend/` 保持默认生产入口，直到所有 parity gate 通过且用户明确授权 cutover。

## 硬边界

1. 不修改 `strategy_policy.py`。
2. 不改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
3. 不把策略判断迁移到前端。
4. 不让 Worker/WASM 成为唯一计算路径，必须保留同步 fallback。
5. 不保存后端 secret 到客户端。
6. 不直接使用第三方默认视觉样式。
7. 不部署，不切流，cutover 默认禁止。
8. 旧 `frontend/` 必须随时可恢复为默认入口。

## 目标数据流

```text
FastAPI / BFF / OpenAPI
  -> frontend-next/src/generated/api-types.ts
  -> typed API client
  -> TanStack Query snapshot cache
  -> Solid signals realtime store
  -> Web Worker derived view models with sync fallback
  -> Solid feature pages
  -> virtual table/list and chart islands
```

关键规则：

1. 首屏监控数据以 BFF snapshot 为源。
2. SSE/delta 只更新实时字段，不重写生产排序。
3. 生产优先榜顺序以后端返回顺序为准。
4. 本地 Worker 只做显示层排序、过滤、派生、downsample。
5. `monitor_snapshot.priority_board` 是优先榜读取路径，除非后端契约未来有兼容 alias。

## 技术选型

| 层面 | 决策 | 约束 |
|---|---|---|
| UI framework | SolidJS + TypeScript | 用细粒度更新承接实时行情和交易工作台 |
| 构建 | Vite | 与旧前端独立构建、独立校验 |
| 路由 | TanStack Router | `/next/*` typed routes，先 shadow |
| 服务端状态 | TanStack Query for Solid | API snapshot、错误态、加载态、缓存 |
| 高频状态 | Solid signals | 行情、时钟、局部 PnL 等字段级更新 |
| 长列表 | TanStack Virtual/Table | DOM 数量稳定，避免滚动退化 |
| 图表 | Lightweight Charts + ECharts adapter | K 线走 canvas 增量更新，低频图保留 ECharts |
| 派生计算 | Web Worker | sort/filter/derive/downsample，保留 sync fallback |
| 数值热点 | 可选 Rust/WASM | 只有 telemetry 证明必要后才启用 |
| 契约 | OpenAPI generated types | 不手写重复 DTO，不依赖样例 JSON 字段 |

## 推荐目录结构

```text
frontend-next/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  public/
  scripts/
    export-openapi.mjs
    compare-with-legacy.mjs
    perf-profile.mjs
    screenshot-parity.mjs
  src/
    app/
      App.tsx
      AppProviders.tsx
      AppShell.tsx
      ErrorBoundary.tsx
      env.ts
      routeTree.ts
    generated/
      api-types.ts
    shared/
      api/
      config/
      realtime/
      workers/
      styles/
      ui/
      charts/
      testing/
    features/
      auth/
      monitor-action/
      monitor-market/
      analysis/
      playbook/
      strategy-tracking/
      paper/
      backtest/
      data-console/
      settings/
```

## 模块边界

| 模块 | 职责 | 禁止事项 |
|---|---|---|
| `shared/api` | typed client、auth、query keys、错误归一 | 不定义重复 DTO，不改接口口径 |
| `shared/realtime` | SSE client、行情 signals、交易时段状态 | 不创建重复 SSE 连接 |
| `shared/workers` | Worker protocol、fallback、性能 telemetry | 不做生产策略判断 |
| `shared/ui` | 当前风格 wrapper、表格、列表、状态组件 | 不泄露第三方默认主题 |
| `shared/charts` | K 线、低频图 adapter、downsample | 不把图表计算接入生产排序 |
| `features/*` | 页面功能和交互 | 不绕过后端 feature flag |

## 样式原则

`frontend-next/` 必须复刻旧前端视觉风格，不做新主题：

1. token、密度、边框、阴影、间距和文案语气来自旧前端。
2. 页面开发前必须有 Web style spec 和 style image。
3. 每页用截图 parity 验收，不用主观“看起来像”。
4. 卡片不得套卡片，长表格走 `DataTable` 等价 wrapper，长列表走 `VirtualList`。
5. paper 机甲头像和执行日志只作为模拟盘 display/review 元素。

## 与平台架构基线的关系

本设计服从 `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`：

1. 前端只处理页面请求、轻量查询、状态展示和任务提交。
2. 重任务仍由 Runtime/Analytics/Backtest Worker 执行。
3. DuckDB/Parquet 只作为分析层，不作为生产交易事实源。
4. 策略、回测、模拟盘、分析、任务运行时继续按领域模块解耦。
5. 新前端不能引入新的无边界并行策略实现。

## 验收命令

后续实现 `frontend-next/` 后必须支持：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run perf:compare
npm run screenshot:parity
```

旧前端必须保持绿色：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

## 回退方式

架构默认可回退：`frontend/` 保持默认入口，`frontend-next/` 仅作为 `/next/*` shadow 应用。若后续启用开关或路由切换，回退入口必须是 `NEW_FRONTEND_ENABLED=false` 或等价配置，并恢复旧前端路由为默认服务目标。
