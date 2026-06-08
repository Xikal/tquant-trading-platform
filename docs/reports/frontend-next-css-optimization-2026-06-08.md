# Frontend Next CSS Optimization - 2026-06-08

状态：CSS 预算与 unused report 已生成；无 PurgeCSS、无批量破坏性删除。
生成来源：`docs/reports/frontend-next-css-budget-2026-06-07.json`、`docs/reports/frontend-next-css-unused-report-2026-06-07.json`、`docs/reports/frontend-next-visual-consistency-2026-06-07/visual-consistency-report.json`。

## Budget Summary

| 项 | 值 | 状态 |
|---|---:|---|
| source CSS files | 29 | - |
| source CSS bytes | 299197 | needs-explanation |
| source CSS gzip bytes | 59727 | - |
| source CSS lines | 15682 | - |
| dist CSS files | 11 | built |
| dist CSS bytes | 240556 | - |
| dist CSS gzip bytes | 48132 | ok |
| !important count | 23 | ok |
| unique class selectors | 1332 | report |
| referenced selectors | 792 | report |
| candidate unused selectors | 110 | manual review only |
| dynamic/legacy selectors | 597 | preserve |
| visual consistency captures | 36 | failed 0 |

## 当前结论

- `!important` 已从 51 收敛到 23，满足 <=25 目标。
- dist CSS gzip 为 48132 bytes，预算内。
- source CSS raw 为 299197 bytes，高于 180KB；当前接受 `needs-explanation`，原因是新前端仍保留 feature CSS 与 legacy workspace 皮肤双源，直接删除 110 个候选 selector 存在视觉回退风险。
- 597 个 selector 已归类为动态或 legacy selector，不作为自动删除对象。
- 后续若继续压 raw，必须逐页拆双源、每批跑 `screenshot:parity` 和 `visual:consistency`，不得使用 PurgeCSS 一次性删除。

## 安全边界

- 本报告只做统计和验收汇总，不删除 CSS。
- CSS 优化不得改变当前 `frontend-next` 视觉。
- K 线仍保持 Lightweight Charts；ECharts 只作为低频 lazy chunk。
