# 平台资源优化 Readiness 聚合报告

- 生成时间：`2026-06-07T23:53:17.138462+00:00`
- 状态：`blocking`
- 阻断项：manifest:manifest_blocked_count=9
- 警告项：resource:resource_config_missing=docker_daemon, resource:resource_config_missing=journald_dropin, resource:resource_config_missing=buildkit, resource:resource_config_missing=mysql_compose_resource_config, resource:resource_config_missing=mysql_slow_logrotate, resource:swap_used_pct=100.0, resource:mysql_slow_log_bytes=3328599654, resource:docker_build_cache_bytes=6400575012, resource:max_binlog_size=1073741824, worker_budget:mysql_max_connections=300, worker_budget:low_priority_pause_env_missing=runtime_worker, worker_budget:low_priority_pause_env_missing=runtime_scheduler, worker_budget:low_priority_pause_env_missing=backtest_worker, worker_budget:low_priority_pause_env_missing=analytics_worker, manifest:manifest_missing_count=9, manifest:manifest_warning_dataset_count=1, export_plan:required_task_count=9, export_plan:manifest_export_required_count=9

## 检查项

| Check | Status | Blocking | Warnings |
| --- | --- | --- | --- |
| resource_limits | warning | - | resource:resource_config_missing=docker_daemon, resource:resource_config_missing=journald_dropin, resource:resource_config_missing=buildkit, resource:resource_config_missing=mysql_compose_resource_config, resource:resource_config_missing=mysql_slow_logrotate, resource:swap_used_pct=100.0, resource:mysql_slow_log_bytes=3328599654, resource:docker_build_cache_bytes=6400575012, resource:max_binlog_size=1073741824 |
| mysql_backup_verification | ready | - | - |
| worker_budget | warning | - | worker_budget:mysql_max_connections=300, worker_budget:low_priority_pause_env_missing=runtime_worker, worker_budget:low_priority_pause_env_missing=runtime_scheduler, worker_budget:low_priority_pause_env_missing=backtest_worker, worker_budget:low_priority_pause_env_missing=analytics_worker |
| analytics_manifest | blocking | manifest:manifest_blocked_count=9 | manifest:manifest_missing_count=9, manifest:manifest_warning_dataset_count=1 |
| analytics_export_plan | warning | - | export_plan:required_task_count=9, export_plan:manifest_export_required_count=9 |
| analytics_export_submission | ready | - | - |

## 下一步

- Install resource limit templates in a maintenance window, then rerun resource baseline.
- Back up and rotate MySQL slow log using the runbook.
- Enable BuildKit GC or perform safe build-cache-only cleanup; do not prune volumes.
- Restart/apply worker budget env and low-priority pause settings, then rerun budget verifier.
- Submit planned analytics manifest export tasks in a low-traffic maintenance window and rerun manifest verifier.
