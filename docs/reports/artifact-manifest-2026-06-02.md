# docs/reports 历史机器产物清单 - 2026-06-02

状态：治理清单 / 暂不迁移
生成日期：2026-06-02
适用范围：`docs/reports/` 顶层 JSON、JSONL、zip、parquet 历史产物

## 口径

- 本清单只记录顶层历史机器产物，不包含子目录中的 walk-forward 明细、窗口结果和 manifest。
- 引用计数来自 `rg --fixed-strings <basename> .` 的当前工作区扫描，作为迁移优先级线索，不作为删除许可。
- 任何迁移或删除前仍需重新做引用检查，并确认不影响代码、脚本、测试、部署、审计和报告追溯。
- 本轮不移动、不删除这些历史产物；先建立可追踪治理入口。

## 分类规则

| 状态 | 含义 |
|---|---|
| 保留 | 当前有明确引用或审计价值，暂不移动 |
| 迁移候选 | 当前引用较少或无引用，但仍需确认审计价值后再迁移 |
| 外部归档候选 | zip、大型包或可由外部 artifact 保存的产物 |

## 清单

| 路径 | 类型 | 引用计数 | 建议状态 |
|---|---:|---:|---|
| `docs/reports/daily-history-backfill-probe-2026-05-28.json` | json | 1 | 迁移候选 |
| `docs/reports/daily-limit-price-backfill-2026-05-28.json` | json | 5 | 保留 |
| `docs/reports/etf-execution-metadata-backfill-t0-30m-2026-05-29.json` | json | 1 | 迁移候选 |
| `docs/reports/etf-execution-metadata-backfill-t0-5m-2026-05-29.json` | json | 2 | 迁移候选 |
| `docs/reports/etf-minute-backfill-1m-probe-2026-05-28.json` | json | 2 | 迁移候选 |
| `docs/reports/etf-minute-backfill-akshare-probe-2026-05-28.json` | json | 3 | 保留 |
| `docs/reports/etf-minute-backfill-probe-2026-05-28.json` | json | 2 | 迁移候选 |
| `docs/reports/etf-minute-backfill-t0-30m-best-provider-2026-05-29.json` | json | 2 | 迁移候选 |
| `docs/reports/etf-minute-backfill-t0-5m-2026-05-28.json` | json | 1 | 迁移候选 |
| `docs/reports/etf-minute-backfill-t0-5m-refresh-2026-05-29.json` | json | 4 | 保留 |
| `docs/reports/etf-minute-backfill-tushare-probe-2026-05-28.json` | json | 3 | 保留 |
| `docs/reports/etf-t0-rule-sync-2026-05-28.json` | json | 3 | 保留 |
| `docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json` | json | 6 | 保留 |
| `docs/reports/front-row-weighted-production-readiness-2026-05-30.json` | json | 3 | 保留 |
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | json | 32 | 保留 |
| `docs/reports/front-row-weighted-production-scoring-review-package-2026-05-30.zip` | zip | 4 | 外部归档候选 |
| `docs/reports/front-row-weighted-validation-freeze-2026-05-30.json` | json | 5 | 保留 |
| `docs/reports/front-row-weighted-walk-forward-validation-2026-05-30.json` | json | 7 | 保留 |
| `docs/reports/front-row-weighted-weak-market-compression-2026-05-30.json` | json | 7 | 保留 |
| `docs/reports/go-rust-performance-acceptance-2026-05-25.json` | json | 4 | 保留 |
| `docs/reports/go-rust-performance-acceptance-2026-05-27.json` | json | 7 | 保留 |
| `docs/reports/gupiao-cloud-performance-2026-05-27-120241.json` | json | 3 | 保留 |
| `docs/reports/gupiao-cloud-performance-2026-05-27-124403.json` | json | 2 | 迁移候选 |
| `docs/reports/gupiao-cloud-performance-2026-05-27-155515.json` | json | 1 | 迁移候选 |
| `docs/reports/gupiao-cloud-performance-2026-05-28-022048.json` | json | 2 | 迁移候选 |
| `docs/reports/gupiao-cloud-performance-2026-05-30-153724.json` | json | 4 | 保留 |
| `docs/reports/gupiao-cloud-performance-2026-05-31-233419.json` | json | 0 | 迁移候选 |
| `docs/reports/gupiao-cloud-performance-2026-05-31-234942.json` | json | 0 | 迁移候选 |
| `docs/reports/gupiao-cloud-performance-2026-06-01-001827.json` | json | 0 | 迁移候选 |
| `docs/reports/gupiao-cloud-performance-2026-06-01-005902.json` | json | 0 | 迁移候选 |
| `docs/reports/gupiao-go-rust-runtime-performance-2026-05-27.json` | json | 1 | 迁移候选 |
| `docs/reports/instrument-metadata-backfill-2026-05-28.json` | json | 4 | 保留 |
| `docs/reports/invalid-daily-bar-cleanup-2026-05-28.json` | json | 1 | 迁移候选 |
| `docs/reports/main-force-model-dataset-smoke.jsonl` | jsonl | 4 | 保留 |
| `docs/reports/main-force-model-production-readiness-2026-05-28.json` | json | 7 | 保留 |
| `docs/reports/main-force-model-related-strategy-readiness-2026-05-28.json` | json | 1 | 迁移候选 |
| `docs/reports/rust-bench-baseline.json` | json | 4 | 保留 |
| `docs/reports/strategy-24m-backtest-2026-05-28.json` | json | 26 | 保留 |
| `docs/reports/strategy-24m-backtest-2026-05-30.json` | json | 6 | 保留 |
| `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json` | json | 2 | 迁移候选 |
| `docs/reports/strategy-24m-optimization-report-2026-05-28.json` | json | 6 | 保留 |
| `docs/reports/strategy-improvement-closed-loop-2026-05-28.json` | json | 24 | 保留 |
| `docs/reports/strategy-system-acceptance-report-2026-05-28.json` | json | 7 | 保留 |

## 后续处理

1. 对“迁移候选”逐项复查引用来源和报告用途。
2. 有审计价值但不适合留在 `docs/reports/` 的产物，迁入 `backend/data/reports/` 或外部 artifact，并在引用文档中更新路径。
3. zip 包优先迁入外部 artifact/object storage，只在仓库保留 Markdown 摘要和校验信息。
4. 迁移完成前，本清单作为历史机器产物的治理入口。
