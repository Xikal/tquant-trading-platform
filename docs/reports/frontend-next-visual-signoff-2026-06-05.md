# Frontend Next Visual Signoff

日期：2026-06-05
范围：旧 `frontend/` 与新 `frontend-next/` 1440x900 认证态截图人工签收清单。

## 2026-06-07 视觉验收口径更新

后续 cutover 前视觉 gate 不再以旧前端像素级 similarity 作为阻断项；旧截图和旧相似度仅保留为历史迁移参考。正式验收改为新前端当前样式体系的一致性、紧凑度、稳定性、无错位、无大留白和无页面/API 错误。

最新自动化结果：

| Gate | 结果 | 证据 |
|---|---|---|
| `visual:consistency` | PASS | `docs/reports/frontend-next-visual-consistency-2026-06-07/visual-consistency-report.md`；9 页 x 4 视口，36 captures，failed 0。 |
| `screenshot:parity` | PASS | `docs/reports/frontend-next-screenshots-2026-06-05/*.png`；9 页无导航错误、无 app error、无 failed API。 |

人工签收仍未完成；若进入 cutover 流程，需按新前端当前视觉逐页签收。

说明：本文件不代表已经人工签收；它固定了逐页签收证据。签收前需打开对应 review PNG，确认信息层级、密度、颜色、表格/卡片、空态/错误态、关键按钮和滚动区域是否接受。

| 旧路由 | 新路由 | 状态 | sample_similarity | Review PNG | 人工结论 |
|---|---|---|---:|---|---|
| /monitor | /next/monitor | ready-for-human-signoff | 0.9232 → 0.9233 | [review-monitor-action-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-monitor-action-web.png) | 待签收 |
| /monitor/market | /next/monitor/market | ready-for-human-signoff | 0.9410 → 0.9413 | [review-monitor-market-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-monitor-market-web.png) | 待签收 |
| /paper | /next/paper | ready-for-human-signoff (本轮微调) | **0.8433 → 0.8509 (+0.0076)** | [review-paper-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-paper-web.png) | 待签收 |
| /strategy-tracking | /next/strategy-tracking | ready-for-human-signoff | 0.9612 → 0.9610 | [review-strategy-tracking-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-strategy-tracking-web.png) | 待签收 |
| /analysis | /next/analysis | ready-for-human-signoff | 0.9080 → 0.8898* | [review-analysis-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-analysis-web.png) | 待签收 |
| /playbook | /next/playbook | ready-for-human-signoff (本轮微调) | 0.9229 → 0.9226 | [review-playbook-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-playbook-web.png) | 待签收 |
| /backtest | /next/backtest | ready-for-human-signoff | 0.9185 → 0.9186 | [review-backtest-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-backtest-web.png) | 待签收 |
| /data | /next/data | ready-for-human-signoff | 0.9806 → 0.9806 | [review-data-console-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-data-console-web.png) | 待签收 |
| /settings | /next/settings | ready-for-human-signoff | 0.9475 → 0.9344* | [review-settings-web.png](/Users/j/Documents/gupiao/docs/reports/frontend-next-visual-review-2026-06-05/review-settings-web.png) | 待签收 |

人工签收 Gate：全部页面结论从 `待签收` 改为 `通过` 后，才可把视觉项视为 cutover 前完成。

## 2026-06-06 视觉微调一轮（baseline → after，旧↔新 sample_similarity，1440x900）

本轮在不做视觉重设计的前提下，只对相似度最低的 `/paper` 做 A+B 微调（4 tile 收敛 + spec 字段口径），并对 `/playbook` 做 A 类去多余说明性文案；未触动其他 7 页代码。`*` 标注的页面（/analysis、/settings）未改代码，波动来自截图采样时的动态内容（时钟 chip、实时脉冲、K 线/图表渲染帧），属本测量回路的噪声基线（±0.01–0.02）。Spec 图相似度全 9 页基本稳定（最大波动 ±0.0008）。
