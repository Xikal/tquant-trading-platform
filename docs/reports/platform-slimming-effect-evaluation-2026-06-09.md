# 平台瘦身效果评测（2026-06-09）

## 结论

本轮瘦身属于“仓库工作区与未来 checkout 变轻”，不是 Git 历史清理。

- `docs/reports` 当前工作区体积：`53M -> 37M`，减少约 `16M`，约 `30%`。
- 被移出跟踪区的历史机器产物：`56` 个文件。
- 删除的 tracked blob 原始体积：约 `15715.2 KiB`，约 `15.35 MiB`。
- 新增 Markdown 报告/指针体积：约 `84 KiB`；净减少仍约 `15.27 MiB`。
- 归档恢复区：`backend/data/reports/archived/2026-06-09`，约 `15M`，被 `.gitignore` 覆盖，不进入仓库。
- 对平台运行功能无影响：未改 `frontend/`、未改后端生产代码、未改 `strategy_policy.py`。

## 当前体积指标

```text
du -sh docs/reports backend/data/reports/archived/2026-06-09
37M     docs/reports
15M     backend/data/reports/archived/2026-06-09
```

```text
tracked docs/reports KiB now: 37200
tracked docs/reports file count now: 773
deleted tracked file count: 56
git object size of deleted tracked blobs KiB: 15715.2
git object size of added untracked markdown KiB: 84
```

说明：

- `git ls-files docs/reports` 在提交前仍会列出已删除但尚未提交的 tracked 文件，所以当前 file count 仍是历史 index 视角。
- 提交后，`docs/reports` tracked 文件数预计减少：删除 56 个机器产物，新增若干 Markdown 报告/指针，净减少约 40+ 个 tracked 文件。

## 归档完整性

归档文件数：

```text
find backend/data/reports/archived/2026-06-09 -type f | wc -l
56
```

归档内容覆盖：

- `docs/reports/strategy-24m-optimization-report-2026-05-28.json`
- `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json`
- `docs/reports/market-state-guard-walk-forward-2026-05-28/summary.json`
- `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/`
- `docs/reports/frontend-next-density-review-2026-06-06/`

恢复方式已记录在：

- `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md`
- `docs/reports/platform-slimming-implementation-report-2026-06-09.md`

## 未瘦身的主要大头

`docs/reports` 仍然保留较大的文件，因为存在运行或脚本引用，不能直接移动：

| 文件/目录 | 当前原因 |
|---|---|
| `front-row-weighted-production-scoring-backtest-2026-05-29.json` | 后端脚本默认路径、派生报告、测试引用 |
| `strategy-24m-backtest-2026-05-30.json` | `Dockerfile` COPY 和 analytics report query 默认读取 |
| `strategy-24m-backtest-2026-05-28.json` | `backtests.py` API 和策略脚本默认读取 |
| `daily-history-backfill-runs/` | 后端脚本默认输出路径引用 |
| `frontend-next-visual-review-2026-06-05/` | frontend-next visual-review 脚本固定输出路径 |
| `frontend-next-visual-consistency-2026-06-07/` | frontend-next visual-consistency 脚本固定输出路径 |
| `frontend-next-screenshots-2026-06-05/` | screenshot-parity / visual-review 固定输出或引用 |

下一轮若要继续瘦身，优先改这些脚本默认路径到 ignored artifact 目录，再迁移大产物。

## Git 历史影响

本轮没有重写 Git 历史，因此：

- 当前工作区和未来新 checkout 会变轻。
- 当前 `.git/objects` 不会因普通删除立刻变小。
- 远端仓库历史体积也不会变小。

如果将来要真正压缩 Git 历史，需要单独授权执行历史重写方案，例如 `git filter-repo`，这会影响所有协作者和远端，需要单独评估，不属于本轮。

## 功能与边界验证

```text
git diff -- frontend backend strategy_policy.py | wc -l
0
```

```text
git diff --check
pass
```

```text
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_boundary.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_low_buy_read_paths.py -q
31 passed, 1 warning
```

结论：瘦身没有影响生产策略、BFF monitor、low-buy read paths 或 strategy_engine shadow 边界。

## 评分

| 维度 | 评分 | 说明 |
|---|---:|---|
| 安全性 | 9/10 | 只移动无运行引用产物；有引用大文件全部保留 |
| 当前工作区瘦身 | 7/10 | `docs/reports` 减少约 30%，但还有有引用的大文件 |
| 仓库长期收益 | 6/10 | 提交后 checkout 变轻；历史不变 |
| 可恢复性 | 9/10 | artifact 目录、manifest、README、恢复命令齐全 |
| 继续瘦身空间 | 8/10 | 下一步可迁移脚本默认输出路径和 Docker/API 读取路径 |

