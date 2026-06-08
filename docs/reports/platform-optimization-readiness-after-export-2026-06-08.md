# 平台资源优化 Readiness 聚合报告

- 生成时间：`2026-06-08T05:47:02.543176+00:00`
- 状态：`warning`
- 阻断项：无
- 警告项：resource:swap_used_pct=70.06, manifest:manifest_warning_dataset_count=1

## 检查项

| Check | Status | Blocking | Warnings |
| --- | --- | --- | --- |
| resource_limits | warning | - | resource:swap_used_pct=70.06 |
| mysql_backup_verification | ready | - | - |
| worker_budget | ready | - | - |
| analytics_manifest | warning | - | manifest:manifest_warning_dataset_count=1 |
| analytics_export_plan | ready | - | - |
| analytics_export_submission | ready | - | - |

## 下一步

- All readiness checks are clear; continue with full validation gates before any cutover decision.
