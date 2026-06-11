# Front-row Weighted Artifact 迁移前置报告（2026-06-11）

## 结论

本批次完成前置改造，不删除、不移动 `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`。后续新生成的 front-row weighted 机器 JSON 默认写入 `backend/data/reports/`，人读 Markdown 继续写入 `docs/reports/`。

旧 docs JSON 当前仍作为历史可追溯产物保留。派生脚本的输入默认采用“优先 `backend/data/reports/`，缺失时回退保留的 `docs/reports/` 历史 JSON”策略，避免前置迁移后默认运行失败。物理出库或删除需要单独提交和授权。

## 已迁移默认路径

| 文件 | 原默认机器 JSON | 新默认机器 JSON | Markdown 摘要 |
|---|---|---|---|
| `backend/scripts/front_row_weighted_production_scoring_backtest.py` | `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | `backend/data/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.md` |
| `backend/scripts/front_row_weighted_oos_manifest.py` | `docs/reports/front-row-weighted-validation-freeze-2026-05-30.json` | 输出到 `backend/data/reports/front-row-weighted-validation-freeze-2026-05-30.json`；输入优先 artifact、缺失回退 docs | 无 |
| `backend/scripts/front_row_weighted_walk_forward_validation.py` | `docs/reports/front-row-weighted-walk-forward-validation-2026-05-30.json` | 输出到 `backend/data/reports/front-row-weighted-walk-forward-validation-2026-05-30.json`；输入优先 artifact、缺失回退 docs | `docs/reports/front-row-weighted-walk-forward-validation-2026-05-30.md` |
| `backend/scripts/front_row_weighted_minute_tick_tradability.py` | `docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json` | 输出到 `backend/data/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json`；输入优先 artifact、缺失回退 docs | `docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.md` |
| `backend/scripts/front_row_weighted_weak_market_compression.py` | `docs/reports/front-row-weighted-weak-market-compression-2026-05-30.json` | 输出到 `backend/data/reports/front-row-weighted-weak-market-compression-2026-05-30.json`；输入优先 artifact、缺失回退 docs | `docs/reports/front-row-weighted-weak-market-compression-2026-05-30.md` |
| `backend/scripts/front_row_weighted_readiness_report.py` | `docs/reports/front-row-weighted-production-readiness-2026-05-30.json` | 输出到 `backend/data/reports/front-row-weighted-production-readiness-2026-05-30.json`；输入优先 artifact、缺失回退 docs | `docs/reports/front-row-weighted-production-readiness-2026-05-30.md` |

## 兼容性

所有脚本仍保留显式参数：

- `--source-report`
- `--base-report`
- `--json-output`
- `--markdown-output`

因此历史命令仍可通过显式传入旧路径运行；默认行为不再向 `docs/reports/` 写大型机器 JSON。
当前仓库尚未跟踪 `backend/data/reports/front-row-weighted-*.json` 基线输入，因此默认输入 fallback 仍会读取保留的 `docs/reports/front-row-weighted-*.json`。

## 残留引用

`rg -n "front-row-weighted-production-scoring-backtest-2026-05-29.json" backend scripts docs` 仍会命中：

- 历史文档、审查报告、开发计划中的引用。
- 既有派生 JSON 的 `source_report` 字段。
- `docs/reports/README.md` 和 `platform-slimming-artifact-manifest-2026-06-09.md` 的保留说明。

这些残留引用是历史追溯，不代表代码默认路径继续依赖旧 docs JSON。

## 删除/出库前置条件

1. 单独获得删除或出库授权。
2. 保留或更新 Markdown 摘要，明确旧 JSON 的 artifact 新位置。
3. 如需重写派生 JSON 指针，必须说明历史报告口径是否保持不变。
4. 跑引用检查，确认非文档默认读取不再依赖旧路径。
5. 单独提交出库/删除动作，不混入功能或策略改动。
