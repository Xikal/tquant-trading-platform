# Frontend Performance Baseline - 2026-06-05

## Scope

本基线用于本轮“React Shell + 性能孤岛 + TypeScript Worker + 可选 Rust/WASM”前端性能架构升级。覆盖目标页面：

- `/monitor`
- `/strategy-tracking`
- `/paper`
- `/backtest`
- `/analysis`

## Pre-change Git Status

开始实施前执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

输出：

```text
?? docs/frontend-performance-islands-worker-wasm-development-plan-2026-06-05.md
```

该未跟踪文档为开始前已有相关计划文件，本轮未清理、未删除、未回退。

## Baseline Commands

```bash
cd /Users/j/Documents/gupiao/frontend
npm run analyze
node scripts/perf-profile.mjs
```

## Bundle Baseline

`npm run analyze` 通过，基线 bundle 指标：

| Metric | Value |
| --- | ---: |
| first_screen_js_gzip_kb | 319.76 |
| total_gzip_kb | 807.12 |
| bundle budget | passed |

主要 gzip chunk：

| Chunk | Gzip KB |
| --- | ---: |
| antd-core | 104.18 |
| antd-check-controls | 105.42 |
| echarts-charts | 99.75 |
| echarts-components | 89.55 |
| antd-display | 54.18 |

## Render Baseline

初始 `scripts/perf-profile.mjs` 只覆盖 3 个页面，结果如下：

| Scenario | Path | Max Scroll Frame ms | Avg Scroll Frame ms | Rendered Nodes Before/After | Long Tasks |
| --- | --- | ---: | ---: | --- | ---: |
| monitor_refresh_virtual_cards | `/monitor` | 33.10 | 31.66 | 54 / 54 | 0 |
| strategy_tracking_table_scroll | `/strategy-tracking` | 34.10 | 31.74 | 0 / 0 | 0 |
| paper_trades_table_scroll | `/paper` | 32.50 | 30.84 | 0 / 0 | 0 |

## Bottleneck Classification

基线阶段未发现 main-thread long task。可确认瓶颈分类：

- 渲染：`/monitor` 已保持稳定节点数；策略追踪、模拟盘列表未出现 DOM 膨胀。
- 计算：基线脚本未覆盖排序/过滤/downsample 计算耗时，需要补 Worker 一致性测试和更完整 profile。
- 序列化：未发现本地 mock profile 异常。
- 网络：本地 mock profile 不代表线上网络。
- 图表：基线未覆盖 `/backtest`，需要补密集图表 profile。
- 状态更新：基线没有 React commit 样本，需要增加可选 profiler probe；生产 preview 下若 React 不 emit Profiler callback，应在验收中如实记录。

## Baseline Gap

初始 profile 缺少 `/backtest`、`/analysis`、二次进入、DOM 峰值、图表刷新耗时、bundle 前后对比和瓶颈分类字段。本轮实现中已增强脚本，用于最终验收报告。
