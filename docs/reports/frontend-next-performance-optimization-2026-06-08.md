# Frontend Next Performance Optimization - 2026-06-08

状态：本地性能验收通过；正式 cutover 前仍需在资源 apply 和 manifest 导出后复跑。
生成来源：`docs/reports/frontend-next-perf-compare-2026-06-08.json`、`docs/reports/frontend-next-chunk-profile-2026-06-08.json`、`docs/reports/frontend-next-visual-consistency-2026-06-07/visual-consistency-report.json`。

## 核心指标

| 项 | 当前值 | 目标/结论 |
|---|---:|---|
| /next/strategy-tracking elapsed | 634 ms | 本地通过 |
| /next/strategy-tracking API 请求 | 2 | <=2 |
| /next/strategy-tracking items 422 | 0 | 0 |
| /next/paper elapsed | 691 ms | 较基线下降 |
| /next/paper 整页 DOM | 343 | 机甲组件未改，整页 <150 不可达 |
| /next/paper 非机甲 DOM | 82 | <150 |
| /next/paper 机甲 DOM | 171 | 保持不改 |
| 首屏 JS raw | 282841 bytes | <=350000 |
| 首屏 JS gzip | 85336 bytes | 记录 |
| 首屏 ECharts assets | 0 | 0 |
| ECharts lazy assets | 3 | 仅低频 lazy |
| ECharts lazy raw | 457660 bytes | 不在首屏 |
| visual consistency captures | 36 | 36 / failed 0 |

## 请求边界

- `/next/strategy-tracking` 只请求 `/api/auth/me` 和 `/api/bff/v1/workspace/strategy`。
- 未出现 `/api/strategy-tracking/items`、`/api/strategy-tracking/summary`、`/api/strategy-tracking/performance` 首屏回退请求。
- `items_422_count=0`。
- 本地默认后端返回旧 `schema_version=v15` 时，前端只记录 `strategy-workspace-contract=outdated` telemetry，不触发多接口首屏 fallback。

## 结论

- Phase B 的 strategy 合包、paper 非机甲虚拟化、ECharts 首屏 lazy 和 chunk 预算已通过本地机器验收。
- `/next/paper` 整页 DOM 未达到 <150 的唯一原因是机甲组件自身 DOM 较大，而机甲组件按边界不改；非机甲区域已经低于 150。
- 正式 cutover 前仍需在云端资源上限 apply、worker 降载生效和 9 个 manifest 导出后复跑完整 frontend/backend/resource/performance gate。
