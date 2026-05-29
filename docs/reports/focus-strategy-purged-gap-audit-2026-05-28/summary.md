# P1 重点策略矩阵 purged-gap 审计

- 报告日期：2026-05-28
- 状态：partial_oos_evidence_purged_gap_not_proven
- 矩阵窗口：21
- 时间顺序通过：是
- 显式训练/验证切分：是
- 建议切分计划：是
- purged-gap 已编码/通过：是 / 否
- purged-gap 计划可执行：是
- 生产可用：否

| 范围 | 窗口 | 起始 | 结束 | 时间顺序 | 缺口 |
|---|---:|---|---|---|---|
| combined_first_board_volume_shrink | 7 | 2025-08-01 | 2026-04-21 | 是 | explicit_train_validation_split_missing, purged_gap_not_encoded_in_source_matrices, online_shadow_settled_sample_lt_required |
| first_board | 7 | 2025-08-01 | 2026-04-21 | 是 | explicit_train_validation_split_missing, purged_gap_not_encoded_in_source_matrices, online_shadow_settled_sample_lt_required |
| volume_shrink | 7 | 2025-08-01 | 2026-04-21 | 是 | explicit_train_validation_split_missing, purged_gap_not_encoded_in_source_matrices, online_shadow_settled_sample_lt_required |

## 生产阻断

- execution_matrix_coverage_partial_only
- online_shadow_settled_sample_lt_required

## 复跑清单

- 状态：executed_complete
- 命令数：21
- 输出目录：`docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/matrix-windows`
- 数据库：`sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db`

## 本地日线覆盖

- 状态：covered
- 日期范围：2024-05-28 至 2026-04-28
- 覆盖窗口：21 / 21
- 单窗口交易日：50 至 58

## 复跑 smoke

- 状态：executed_with_samples
- 输出结构通过：是
- 有效样本：是
- 矩阵文件：1
- 评估样本：576
- 成交样本：554
- 覆盖状态：partial
- 仍为部分覆盖：是
- 说明：Smoke command and output structure passed with evaluated samples.

## 全量复跑

- 状态：executed_complete
- 完成：是
- 矩阵文件：21 / 21
- 评估样本：6336
- 成交样本：5964
- 覆盖状态：partial
- 仍为部分覆盖：是
