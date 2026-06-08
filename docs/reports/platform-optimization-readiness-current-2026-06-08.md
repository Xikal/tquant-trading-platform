# 平台资源优化 Readiness 聚合报告

- 生成时间：`2026-06-08T05:12:43.880359+00:00`
- 状态：`blocking`
- 阻断项：manifest:manifest_blocked_count=9
- 警告项：resource:swap_used_pct=94.61, manifest:manifest_missing_count=9, manifest:manifest_warning_dataset_count=1, export_plan:required_task_count=9, export_plan:manifest_export_required_count=9

## 检查项

| Check | Status | Blocking | Warnings |
| --- | --- | --- | --- |
| resource_limits | warning | - | resource:swap_used_pct=94.61 |
| mysql_backup_verification | ready | - | - |
| worker_budget | ready | - | - |
| analytics_manifest | blocking | manifest:manifest_blocked_count=9 | manifest:manifest_missing_count=9, manifest:manifest_warning_dataset_count=1 |
| analytics_export_plan | warning | - | export_plan:required_task_count=9, export_plan:manifest_export_required_count=9 |
| analytics_export_submission | ready | - | - |

## 下一步

- Submit planned analytics manifest export tasks in a low-traffic maintenance window and rerun manifest verifier.
