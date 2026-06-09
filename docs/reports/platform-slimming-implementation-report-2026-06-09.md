# 平台瘦身落地实施报告（2026-06-09）

## 结论

本轮完成 Phase 0-3 的本地瘦身落地与报告化，不部署、不切流、不删除生产核心能力。

- 未修改 `strategy_policy.py`
- 未修改旧前端生产代码
- 未修改后端生产代码
- 未改变生产策略语义、`production_score`、priority board 排序和口径
- 未启用 research/shadow/ML/factor/agent 能力
- 未停 low_buy、market、paper、backtest、tasks、BFF、`monitor_snapshot_service`、RuntimeTaskQueue

## 完成项

| 阶段 | 交付物 | 状态 |
|---|---|---|
| Phase 0 | `docs/reports/platform-slimming-baseline-2026-06-09.md` | 完成 |
| Phase 1 | `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md` | 完成 |
| Phase 1 | 安全机器产物归档到 `backend/data/reports/archived/2026-06-09/` | 完成 |
| Phase 2 | `docs/reports/platform-slimming-feature-flag-review-2026-06-09.md` | 完成 |
| Phase 3 | `docs/reports/platform-slimming-remove-candidate-inventory-2026-06-09.md` | 完成 |

## 移动/归档清单

归档目录：`backend/data/reports/archived/2026-06-09/`

该目录被 `.gitignore` 的 `data/` 规则覆盖，不进入仓库。仓库保留 manifest、Markdown 摘要和恢复命令。

| 原路径 | 归档后状态 | 恢复方式 |
|---|---|---|
| `docs/reports/strategy-24m-optimization-report-2026-05-28.json` | 已移动 | `cp backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-optimization-report-2026-05-28.json docs/reports/` |
| `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json` | 已移动 | `cp backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json docs/reports/` |
| `docs/reports/market-state-guard-walk-forward-2026-05-28/summary.json` | 已移动 | `cp backend/data/reports/archived/2026-06-09/docs/reports/market-state-guard-walk-forward-2026-05-28/summary.json docs/reports/market-state-guard-walk-forward-2026-05-28/` |
| `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/` | 已移动 | `cp -a backend/data/reports/archived/2026-06-09/docs/reports/market-state-guard-walk-forward-2026-05-28/windows docs/reports/market-state-guard-walk-forward-2026-05-28/` |
| `docs/reports/frontend-next-density-review-2026-06-06/` | 已移动 | `cp -a backend/data/reports/archived/2026-06-09/docs/reports/frontend-next-density-review-2026-06-06 docs/reports/` |

保留摘要/指针：

- `docs/reports/strategy-24m-optimization-report-2026-05-28.md`
- `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.md`
- `docs/reports/market-state-guard-walk-forward-2026-05-28/summary.md`
- `docs/reports/market-state-guard-walk-forward-2026-05-28/README.md`
- `docs/reports/frontend-next-density-review-2026-06-06.md`
- `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md`

体积变化：

```text
before: docs/reports 53M
after:  docs/reports 37M
artifact archive: backend/data/reports/archived/2026-06-09 15M
```

## 未处理项

以下文件存在运行引用、脚本默认路径、Dockerfile COPY、API 默认读取或测试断言，本轮只登记，不移动：

| 路径 | 保留原因 |
|---|---|
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | 后端 front-row 脚本默认参数、派生报告、测试断言引用 |
| `docs/reports/strategy-24m-backtest-2026-05-30.json` | `Dockerfile` COPY 和 analytics report query 默认读取 |
| `docs/reports/strategy-24m-backtest-2026-05-28.json` | `backtests.py` API、strategy 24m 脚本和 closed-loop 脚本默认读取 |
| `docs/reports/daily-history-backfill-runs/` | `daily_history_backfill_runner.py` 默认输出路径引用 |
| `docs/reports/frontend-next-visual-review-2026-06-05/` | `frontend-next/scripts/visual-review.mjs` 固定输出路径引用 |
| `docs/reports/frontend-next-visual-consistency-2026-06-07/` | `frontend-next/scripts/visual-consistency.mjs` 固定输出路径引用 |
| `docs/reports/frontend-next-screenshots-2026-06-05/` | `screenshot-parity.mjs` 和 `visual-review.mjs` 固定输出/引用 |

后续若要继续瘦身，应先改脚本默认输出到 ignored artifact 目录并补测试，再迁移这些文件。

## P0 保护模块

本轮未触碰以下模块：

- `backend/app/services/low_buy/strategy_policy.py`
- low-buy production scoring、priority board、priority read model、materialization
- market 读路径和行情刷新
- paper 模拟盘
- backtest 回测
- tasks/RuntimeTaskQueue/runtime worker
- BFF、monitor snapshot
- OpenAPI 契约事实源
- 旧前端生产代码
- frontend-next 运行代码

## Flag 状态

详见 `docs/reports/platform-slimming-feature-flag-review-2026-06-09.md`。

核心结论：

- research/ML/factor job 当前 `default_off`
- AKeyLevel 默认 `default_off`
- trading_experience suite 和子能力默认 `default_off`
- strategy engine 仍为 `research_only/shadow`，不替代生产排序
- agent provider 当前为 `none`，写工具默认关；通知为可选集成，不影响生产排序

## Remove Candidate 状态

详见 `docs/reports/platform-slimming-remove-candidate-inventory-2026-06-09.md`。

本轮仅标状态：

- `protected`
- `active`
- `default_off`
- `research_only`
- `optional_integration`
- `blocked_archive_candidate`
- `archived_this_round`

没有实际删除代码。

## 验证结果

本轮只触碰文档和 `docs/reports` 机器产物，不触碰 frontend-next 运行代码或后端生产代码，因此无需执行 frontend-next 或后端 pytest 门禁。

已执行/需最终确认：

```text
git diff -- frontend backend strategy_policy.py
0 行输出

git check-ignore -v backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-optimization-report-2026-05-28.json
.gitignore:21:data/ backend/data/reports/archived/2026-06-09/docs/reports/strategy-24m-optimization-report-2026-05-28.json
```

最终门禁以本报告生成后的 `git diff --check && git status --short` 为准。

## 功能影响

对平台功能无影响：

- 线上未部署，未切流
- 本地未修改运行代码
- 被归档的产物均为无非文档运行引用的机器产物/截图
- 有运行引用的机器产物已保留

cutover、真实删除、脚本默认路径迁移、旧前端/frontend-next 收敛仍需用户单独授权。

