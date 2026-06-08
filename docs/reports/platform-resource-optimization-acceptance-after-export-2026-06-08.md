# frontend-next 与平台资源优化验收草案

- 生成时间：`2026-06-08T05:47:26.645596+00:00`
- 总状态：`warning`
- 未部署：`True`
- 未切流：`True`
- 自用状态：可以继续通过 /next/* 自用和验收；阻断项主要影响正式 cutover 和长期稳定性。
- 正式 cutover 状态：`requires_separate_authorization`
- 是否影响平台功能：不影响；当前未部署、未切流，生产策略语义和排序口径未改变。
- 后端改动原因：后端改动用于 BFF 合包、worker 预算/低优先级暂停、analytics Parquet 导出、只读资源/manifest/readiness 验证和部署资源 gate；不改变生产策略语义、生产排序、production_score 或 priority_board 口径。
- 旧 frontend 是否未改：`True`
- strategy_policy.py 是否未改：`True`
- Cutover 是否仍需单独授权：`True`

## 新增/修改重点文件

- frontend-next strategy-tracking BFF 合包、paper 非机甲长列表虚拟化、ECharts 首屏懒加载、CSS guard/报告。
- scripts/collect_platform_resource_report.py：只读采集 df/free/docker/journal/mysql/binlog/slow log/备份状态。
- scripts/install_platform_resource_limits.py 与 deploy/* 模板：Docker log、journal、BuildKit 和 MySQL slow logrotate 上限，默认 dry-run；MySQL binlog/max-binlog 由 docker-compose.mysql.yml command 管理。
- scripts/verify_platform_budget.py：MySQL 连接池、worker 角色预算、Web 重任务 guard。
- scripts/verify_analytics_manifests.py：Parquet manifest 只读校验和 sha256 文件验证。
- scripts/plan_analytics_manifest_exports.py 与 scripts/submit_analytics_manifest_exports.py：导出任务计划和显式 apply 入队。
- scripts/verify_platform_optimization_readiness.py：聚合 resource/budget/manifest/export/submission 总 gate。
- scripts/plan_platform_maintenance_window.py：生成人工维护窗口步骤，不执行命令。
- docs/operations/mysql-maintenance-runbook.md：MySQL 备份、binlog、slow log、analytics manifest 运维流程。
- docs/frontend-next-cutover-runbook-2026-06-05.md 与 PRODUCTION_RUNBOOK.md：补入正式部署/切流前平台资源 gate。
- frontend-next/scripts/perf-profile.mjs：输出结构化 perf JSON，供完成度审计验证 strategy 请求和 paper DOM。

## 证据报告

- `docs/reports/platform-resource-baseline-2026-06-08.md`
- `docs/reports/platform-mysql-backup-verification-2026-06-08.md`
- `docs/reports/platform-budget-2026-06-08.md`
- `docs/reports/platform-analytics-manifests-2026-06-08.md`
- `docs/reports/platform-optimization-readiness-2026-06-08.md`
- `docs/reports/platform-maintenance-window-plan-2026-06-08.md`
- `docs/reports/frontend-next-performance-optimization-2026-06-08.md`
- `docs/reports/frontend-next-css-optimization-2026-06-08.md`
- `docs/reports/frontend-next-perf-compare-2026-06-08.json`
- `docs/reports/frontend-next-chunk-profile-2026-06-08.md`
- `docs/reports/platform-resource-optimization-completion-audit-2026-06-08.md`
- `docs/reports/gupiao-cloud-performance-2026-06-08-131226.json`

## Phase 完成度

| Phase | 状态 |
| --- | --- |
| phase_a_resource_limits | implemented_not_applied_online |
| phase_b_frontend_next_performance | implemented_local_verified |
| phase_c_worker_budget | implemented_not_applied_online |
| phase_d_parquet_manifest | implemented_but_online_manifest_blocking |
| phase_e_prebuilt_deploy | scripted_not_applied_online |
| phase_f_qa_reporting | partial_current_slice_verified |

## Before/After 指标

| 指标 | 当前值 |
| --- | ---: |
| root_used_pct | 41 |
| available_memory_mb | 450 |
| swap_used_pct | 70.06 |
| journal_usage_bytes | 298110156 |
| mysql_volume_bytes | 8160437862 |
| mysql_slow_log_bytes | 69632 |
| docker_build_cache_bytes | 0 |
| deploy_backup_count | 0 |
| mysql_max_connections | 120 |
| threads_connected | 25 |
| frontend_initial_js_raw_bytes | 282841 |
| frontend_initial_echarts_asset_count | 0 |
| online_readyz_p95_ms | 4.459 |
| online_monitor_bff_p95_ms | 10.475 |
| online_priority_board_p95_ms | 19.909 |
| mysql_backup_gzip_ok | True |
| mysql_backup_sql_signature_ok | True |

## 资源与 MySQL 状态

- binlog_expire_logs_seconds：`259200`
- max_binlog_size：`268435456`
- binary_log_count：`8`
- binary_log_total_bytes：`4789307748`
- slow_log_bytes：`69632`
- MySQL 备份数量：`1`
- MySQL 最新备份：`/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz`
- MySQL 备份校验报告：`docs/reports/platform-mysql-backup-verification-2026-06-08.md`
- MySQL 备份 gzip 完整：`True`
- MySQL 备份 SQL 特征：`True`
- MySQL 备份 sha256：`f82db5fa2334fdd84abc4f7d2e136fd3af82742354ebb6a3bb24767215380db5`
- 部署归档数量：`0`

## Worker 降载状态

- MySQL max_connections：`120`
- Threads_connected：`25`
- Pool budget：`28`

## Parquet Manifest 状态

- ready_count：`10`
- missing_count：`0`
- blocked_count：`0`
- verified_files：`267`
- blocked_datasets：无

## 回滚方式

- 资源上限配置：恢复 /etc/tquant-resource-backups/<timestamp>/ 中的配置并重启对应服务。
- Analytics 导出任务：通过 POST /api/runtime-tasks/<task_id>/cancel 取消 queued/running 任务。
- frontend-next：当前未切流；旧 frontend 保持可回滚入口。
- MySQL 源数据：当前未清理；任何热库清理仍需单独授权和恢复路径。

## 线上性能状态

- 报告：`docs/reports/gupiao-cloud-performance-2026-06-08-131226.json`
- ok：`True`
- failures：`[]`
- readyz p95：`4.459` ms
- monitor_bff p95：`10.475` ms
- market_pulse p95：`7.998` ms
- priority_board p95：`19.909` ms
- watchlist_signals p95：`9.404` ms

## 完成度审计

- 报告：`docs/reports/platform-resource-optimization-completion-audit-2026-06-08.md`
- 状态：`blocking`
- 汇总：`{'passed': 21, 'warning': 5, 'blocked': 9, 'not_verified': 0, 'total': 35}`

## Cutover 前必须补齐

- 维护窗口内 apply 资源上限配置并重启/复验相关服务。
- 执行 analytics manifest 导出任务，补齐 9 个缺失 manifest 后重跑 verifier/readiness。
- 复跑 frontend-next 全量验收命令、资源验收、request trace 和 performance gate。
- 用户单独授权 cutover；失败即停止，保留旧 frontend 回滚。

## 未完成项

- warning:resource:swap_used_pct=70.06
- warning:manifest:manifest_warning_dataset_count=1
