# frontend-next 与平台资源优化完成度审计

- 生成时间：`2026-06-08T05:47:39.129283+00:00`
- 总状态：`blocking`
- 结论：目标尚未完成；可继续 /next/* 自用，但不能声明平台资源优化完成或正式 cutover ready。

## 汇总

| 状态 | 数量 |
| --- | ---: |
| passed | 29 |
| warning | 5 |
| blocked | 1 |
| not_verified | 0 |
| total | 35 |

## 逐项审计

| Phase | 检查项 | 状态 | 证据 | 下一步 |
| --- | --- | --- | --- | --- |
| boundary | 本轮不部署、不切流。 | `passed` | deployed=False, cutover=False | 如需正式切流，必须另行授权并复跑 gate。 |
| boundary | 不修改 strategy_policy.py。 | `passed` | strategy_policy_modified=False |  |
| boundary | 不改变生产策略语义、生产排序、production_score、priority_board。 | `passed` | production_semantics_changed=False |  |
| boundary | 旧 frontend/ 不作为本轮改造对象。 | `passed` | old_frontend_modified=False |  |
| phase_a | 根分区 >80% blocking，长期目标 <60%。 | `passed` | root_used_pct=41 | 继续每日巡检；长期目标仍需维持在 60% 附近。 |
| phase_a | Available memory >800MiB，或有明确单机不可达原因。 | `warning` | available_mb=450 | 资源上限和 worker 降载在线生效后复验；若仍低于 800MiB，需在验收报告写明单机不可达原因。 |
| phase_a | MySQL binlog 固化保留 3 天。 | `passed` | binlog_expire_logs_seconds=259200 |  |
| phase_a | max_binlog_size 目标 256M。 | `passed` | max_binlog_size=268435456 | 运维窗口重建 MySQL 容器使 compose max-binlog-size 生效，并复验 @@max_binlog_size。 |
| phase_a | MySQL slow log 单文件 <=256M 并安装 logrotate。 | `passed` | slow_log_bytes=69632; mysql_slow_logrotate_missing=False | 先备份 slow log，再安装 logrotate 并执行轮转/复验。 |
| phase_a | systemd journal 上限 300M/7day 在线生效。 | `passed` | journal_usage_bytes=298110156; journald_dropin_missing=False | 运维窗口安装 journald drop-in 并重启/复验 journal 占用。 |
| phase_a | Docker BuildKit cache 目标 <=2G。 | `passed` | docker_build_cache_bytes=0 | 启用 BuildKit GC 或只清 build cache；禁止清 volume。 |
| phase_a | Docker/journal/BuildKit/MySQL compose command/slow logrotate 配置在线安装或生效并可复验。 | `passed` | no missing config warnings | 按维护窗口计划执行 resource_limits_apply 后重跑 baseline/readiness。 |
| phase_a | MySQL volume 短期 <12G，长期通过 Parquet/manifest 控制增长。 | `passed` | mysql_volume_bytes=8160437862.0 | manifest 全部补齐并完成保留窗口 dry-run 前，不清 MySQL 源数据。 |
| phase_a | 生产机部署归档仅保留最近 3 个可回滚版本。 | `passed` | deploy_backup_count=0, total_bytes=0 | 保留最新 3 个；禁止清当前运行目录、数据库、运行时数据。 |
| phase_a | 执行数据库备份并纳入巡检，备份 gzip/SQL 特征可校验。 | `passed` | mysql_backup_count=1, latest=/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz, verified_path=/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz, gzip_ok=True, sql_signature_ok=True, sha256=f82db5fa2334fdd84abc4f7d2e136fd3af82742354ebb6a3bb24767215380db5 |  |
| phase_b | /next/strategy-tracking 优先走 BFF，请求 <=2 且 items 422=0。 | `passed` | api_request_count=2, items_422_count=0, forbidden_legacy_requests=[] | 保留 request:trace/perf:compare 作为正式 gate。 |
| phase_b | /next/paper 长列表接 VirtualList，DOM <150，机甲组件不改。 | `warning` | dom_nodes=350, non_mecha_descendants=82, mecha_descendants=171 | 若坚持整页 DOM <150，需要另行授权简化机甲组件 DOM。 |
| phase_b | CSS !important <=25。 | `passed` | important_count=23, target=25 |  |
| phase_b | CSS raw <=180KB，或说明不可达原因。 | `warning` | source_css_bytes=299197, target=180000, status=needs-explanation | 当前以说明和视觉一致性 gate 接受；继续优化需逐页截图验证。 |
| phase_b | ECharts 首屏资产为 0，K 线保持 Lightweight Charts。 | `passed` | initial_echarts_assets=0, target=0 |  |
| phase_b | 首屏 JS raw <=350KB。 | `passed` | initial_js_raw_bytes=282841, target=350000 |  |
| phase_c | MySQL max_connections 收敛到 80-120 并在线生效。 | `passed` | max_connections=120, threads_connected=25 | 运维窗口重启 MySQL/容器，使 compose 目标 120 生效并复跑 performance gate。 |
| phase_c | 低优先级重任务暂停开关进入运行容器。 | `passed` | low priority env present | 运维窗口重启 runtime/backtest/analytics/scheduler 容器后复验。 |
| phase_c | Web 主进程不跑重任务。 | `passed` | web_env={'DB_POOL_SIZE': '4', 'DB_MAX_OVERFLOW': '4', 'RUNTIME_BACKGROUND_ROLE': 'web', 'RUNTIME_BACKGROUND_JOBS_ENABLED': 'false', 'APP_WORKERS': '4', 'TQUANT_ANALYTICS_ENABLED': 'false'} |  |
| phase_c | Swap 长期 <20%，短期优化目标 <500MiB。 | `blocked` | swap_used_pct=70.06 | 资源上限和 worker 降载在线生效后复验。 |
| phase_d | daily_bars Parquet manifest 可校验。 | `passed` | ready_count=10, verified_files=267 |  |
| phase_d | strategy/backtest/report 等目标数据集 manifest 全部补齐。 | `passed` | missing_count=0, blocked_count=0, blocked_datasets=[] | 按导出计划显式入队 9 个 analytics export 任务，完成后重跑 manifest verifier。 |
| phase_d | MySQL 热库保留窗口和归档策略明确，且清理前要求 manifest/备份/恢复路径。 | `passed` | mysql maintenance runbook includes manifest-gated retention and cleanup authorization. |  |
| phase_d | manifest 未校验前不清 MySQL 源数据。 | `passed` | acceptance/runbook 明确未清 MySQL 源表，清理仍需单独授权。 |  |
| phase_e | 预构建镜像优先，云端 pull+restart。 | `warning` | phase_e=scripted_not_applied_online | 脚本入口已完成；真实 registry ref 和云端 pull+restart 尚未执行。 |
| phase_e | 部署前资源 gate 纳入 cutover/生产手册，资源不达标停止。 | `passed` | cutover/production runbooks contain platform resource gate references. | 补齐 runbook 后，真实部署前仍需按 gate 重新采集并归档。 |
| phase_f | 线上 Web/API performance gate 当前样本通过。 | `passed` | ok=True, failures=[], readyz p95=4.459ms status=[200], monitor_bff p95=10.475ms status=[200], market_pulse p95=7.998ms status=[200], priority_board p95=19.909ms status=[200], watchlist_signals p95=9.404ms status=[200] | 资源 apply、worker 重启、manifest 导出后必须重新跑三轮 online performance gate。 |
| phase_f | 报告闭环包含 before/after、资源、MySQL、Worker、manifest、回滚、未完成项。 | `passed` | acceptance_status=warning, open_items=2 |  |
| phase_f | 完整 frontend/backend/resource/performance gate 已执行并记录。 | `warning` | progress report records frontend-next full chain and backend 133 passed; online apply 后仍需重跑。 | 资源 apply 和 manifest 导出完成后重跑完整 gate。 |
| phase_f | 资源、备份、部署 guard、manifest 导出和回滚手册完整。 | `passed` | mysql/cutover/production runbooks include resource guard and rollback. |  |
