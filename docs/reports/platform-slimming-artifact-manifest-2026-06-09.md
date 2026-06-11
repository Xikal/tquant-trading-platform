# 平台瘦身 Artifact Manifest（2026-06-09）

## 规则

- 移动前已执行 `rg --fixed-strings "<basename-or-dir>"` 引用检查。
- 只移动确认没有运行时读取、API 默认读取、Dockerfile COPY、测试断言或固定脚本读取依赖的机器产物。
- 归档位置：`backend/data/reports/archived/2026-06-09/`。该路径被 `.gitignore` 的 `data/` 规则覆盖，不进入仓库。
- 恢复路径：从归档位置复制回原路径，或用 `git checkout <commit-before-archive> -- <original-path>` 恢复跟踪文件。
- 本轮不删除生产核心能力，不触碰 `strategy_policy.py`、生产排序、priority board、market、paper、backtest、tasks、BFF。

## 本轮已确认可归档

| 原路径 | 大小 | 类型 | 引用检查摘要 | 归档位置 | 仓库保留摘要/指针 | 恢复方式 |
|---|---:|---|---|---|---|---|
| `docs/reports/strategy-24m-optimization-report-2026-05-28.json` | 1352 KiB | 回测优化机器 JSON | `rg --fixed-strings` 仅发现文档/报告引用；`--glob '!docs/**' --glob '!IMPLEMENTATION_PLAN.md'` 无非文档引用 | `backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-optimization-report-2026-05-28.json` | `docs/reports/strategy-24m-optimization-report-2026-05-28.md` | `cp backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-optimization-report-2026-05-28.json docs/reports/` |
| `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json` | 888 KiB | 回测机器 JSON | `rg --fixed-strings` 仅发现文档/报告引用；无非文档引用 | `backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json` | `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.md` | `cp backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json docs/reports/` |
| `docs/reports/market-state-guard-walk-forward-2026-05-28/summary.json` | included in 8960 KiB dir | walk-forward 汇总 JSON | 目录名无非文档引用 | `backend/data/reports/archived/2026-06-09/docs/reports/market-state-guard-walk-forward-2026-05-28/summary.json` | `docs/reports/market-state-guard-walk-forward-2026-05-28/summary.md` + `README.md` | `cp backend/data/reports/archived/2026-06-09/docs/reports/market-state-guard-walk-forward-2026-05-28/summary.json docs/reports/market-state-guard-walk-forward-2026-05-28/` |
| `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/` | included in 8960 KiB dir | walk-forward 分窗口机器产物 | `rg --fixed-strings "market-state-guard-walk-forward-2026-05-28" --glob '!docs/**' --glob '!IMPLEMENTATION_PLAN.md'` 无非文档引用 | `backend/data/reports/archived/2026-06-09/docs/reports/market-state-guard-walk-forward-2026-05-28/windows/` | `docs/reports/market-state-guard-walk-forward-2026-05-28/summary.md` + `README.md` | `cp -a backend/data/reports/archived/2026-06-09/docs/reports/market-state-guard-walk-forward-2026-05-28/windows docs/reports/market-state-guard-walk-forward-2026-05-28/` |
| `docs/reports/frontend-next-density-review-2026-06-06/` | 4664 KiB | frontend-next 一次性截图 PNG | 目录名无非文档引用；未发现脚本固定输出到该目录 | `backend/data/reports/archived/2026-06-09/docs/reports/frontend-next-density-review-2026-06-06/` | `docs/reports/frontend-next-density-review-2026-06-06.md` | `cp -a backend/data/reports/archived/2026-06-09/docs/reports/frontend-next-density-review-2026-06-06 docs/reports/` |

## 本轮暂不移动的 Blocker

| 路径 | 大小 | 原因 | 当前状态 |
|---|---:|---|---|
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | 12972 KiB | 2026-06-11 已将 `backend/scripts/front_row_weighted_*` 新机器 JSON 默认路径迁到 `backend/data/reports/`；历史文档和派生 JSON 仍保留追溯引用 | 保留，等待单独出库/删除授权；删除前需保留 Markdown 摘要、迁移报告和必要 artifact 指针 |
| `docs/reports/strategy-24m-backtest-2026-05-30.json` | 1444 KiB | 被 `Dockerfile` COPY 和 `backend/app/services/analytics/report_queries.py` 默认读取 | 保留，属于运行/镜像引用，不能本轮移动 |
| `docs/reports/strategy-24m-backtest-2026-05-28.json` | 820 KiB | 被 `backend/app/api/routes/backtests.py`、`backend/scripts/strategy_24m_backtest_report.py`、`backend/scripts/strategy_improvement_closed_loop.py`、测试和服务报告引用 | 保留，属于 API/脚本默认读取 |
| `docs/reports/daily-history-backfill-runs/` | 3912 KiB | 被 `backend/scripts/daily_history_backfill_runner.py` 默认输出路径引用 | 本轮保留，先登记为后续脚本默认输出目录迁移候选 |
| `docs/reports/frontend-next-visual-review-2026-06-05/` | 2924 KiB | 被 `frontend-next/scripts/visual-review.mjs` 固定输出目录引用 | 本轮保留，后续应先修改脚本输出到 ignored artifacts |
| `docs/reports/frontend-next-visual-consistency-2026-06-07/` | 4584 KiB | 被 `frontend-next/scripts/visual-consistency.mjs` 固定输出目录引用 | 本轮保留，后续应先修改脚本输出到 ignored artifacts |
| `docs/reports/frontend-next-screenshots-2026-06-05/` | 4736 KiB | 被 `frontend-next/scripts/screenshot-parity.mjs`、`frontend-next/scripts/visual-review.mjs` 固定输出/引用 | 本轮保留，后续应先修改脚本输出目录和报告指针 |

## 引用检查命令摘要

```text
rg --fixed-strings "<basename-or-dir>" .
rg --fixed-strings "<basename-or-dir>" . --glob '!docs/**' --glob '!IMPLEMENTATION_PLAN.md' --glob '!backend/data/**'
```

关键发现：

- `front-row-weighted-production-scoring-backtest-2026-05-29.json` 的后端脚本默认参数已在 2026-06-11 迁到 `backend/data/reports/`，旧 docs JSON 当前只作为历史可追溯产物保留，最终出库/删除需要单独授权。
- `strategy-24m-backtest-2026-05-30.json` 存在 Dockerfile 和 analytics service 默认读取，不能直接移动。
- `strategy-24m-backtest-2026-05-28.json` 存在 backtests API 默认读取，不能直接移动。
- `strategy-24m-optimization-report-2026-05-28.json`、`strategy-24m-front-row-filter-backtest-2026-05-29.json` 没有非文档引用，可归档。
- `market-state-guard-walk-forward-2026-05-28` 没有非文档引用，可保留 `summary.md` 并归档机器产物。
- `frontend-next-density-review-2026-06-06` 没有非文档引用，可归档截图并保留 Markdown 指针。
