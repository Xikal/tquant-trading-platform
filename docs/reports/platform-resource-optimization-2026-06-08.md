# Frontend Next 与平台资源优化进展报告 - 2026-06-08

状态：阶段性落地报告，未部署，未切流
范围：`frontend-next/` 降载、平台资源巡检、运维配置模板、部署资源 gate
当前结论：本轮已完成资源巡检基础设施、云端只读 baseline、资源上限模板、`/next/strategy-tracking` BFF 合包、`/next/paper` 非机甲区域虚拟化与首屏懒挂载，并把回测明细、分析日志、市场复盘、模拟盘复盘纳入 Parquet 分析层；回测 daily bars 输入已支持 Parquet 优先读取，默认关闭并可回退 MySQL。云端当前无磁盘 blocking，但仍有 swap、slow log、Docker build cache 和未安装资源上限配置的 warning，不能声明平台资源治理完成。

## 已完成

### Phase A：资源巡检与上限模板

- 新增只读资源巡检脚本：`scripts/collect_platform_resource_report.py`。
- 支持本机 fixture 和远程 SSH 只读采集。
- 巡检脚本已修复 MySQL 8 `SHOW BINARY LOGS` 三列输出和变量输出解析，当前可正确报告 binlog 数量、总体积、`binlog_expire_logs_seconds` 和 `max_binlog_size`。
- 巡检脚本已新增部署归档观测：采集 `/home/*/gupiao-deploy-backup-*` 数量和总体积，超过 3 个进入 warning；当前云端为 0 个、0 bytes。
- 巡检脚本已新增 MySQL 备份观测：采集 `/home/*/mysql-backups/*.sql.gz` 数量、总体积和最新备份路径；当前云端为 1 个备份，最新 `/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz`，约 140.7MB。
- 新增只读 MySQL 备份文件校验脚本：`scripts/verify_mysql_backup_artifact.py`。
  - 本地/SSH 均只检查 `.sql.gz` 存在性、大小、gzip 完整性、sha256 和 SQL dump 特征。
  - 不恢复、不写库、不删除文件。
  - 当前云端最新全库备份通过校验：gzip 完整，命中 `-- MySQL dump`、`CREATE TABLE`、`INSERT INTO`、`LOCK TABLES`，sha256=`f82db5fa2334fdd84abc4f7d2e136fd3af82742354ebb6a3bb24767215380db5`。
- 输出 JSON 与 Markdown：
  - `docs/reports/platform-resource-baseline-2026-06-08.json`
  - `docs/reports/platform-resource-baseline-2026-06-08.md`
- 部署前资源 gate 已接入 `scripts/quick_cloud_deploy.sh`：根分区 >=80% 阻断，root/build cache/slow log/binlog retention 进入 preflight 输出。
- `scripts/quick_cloud_deploy.sh --verify-only` 已补只读资源 preflight：
  - verify-only 会先运行远程资源 gate，再做健康检查。
  - verify-only 强制 `REMOTE_PREFLIGHT_READ_ONLY=1`、`RUN_REMOTE_SAFE_CLEANUP=0`、`REMOTE_TEMP_SWAP_MB=0`，不删除部署包、不 prune Docker、不创建临时 swap。
  - preflight 修复了 `docker system df` 中 `5.961GB` 被误解析为 0 的问题，并改用 `sudo du` 读取 MySQL slow log，避免因权限导致 slow log 误报 0。
  - preflight 已补 `journald_resource_config` 和 `mysql_backup_count` 只读检查；当前云端输出 `journald_resource_config=missing` warning，`mysql_backup_count=1`。
- 新增资源上限配置模板：
  - `deploy/mysql/mysql-slow-logrotate.conf`
  - `deploy/docker/daemon-resource.json`
  - `deploy/systemd/journald-resource.conf`
  - `deploy/buildkit/buildkitd-resource.toml`
- MySQL binlog/max-binlog 运行态配置已落到 `docker-compose.mysql.yml` 的 MySQL `command`：`MYSQL_BINLOG_EXPIRE_LOGS_SECONDS=259200`、`MYSQL_MAX_BINLOG_SIZE=256M`。这比写宿主机 `/etc/mysql/conf.d` 更可靠，因为当前 MySQL 运行在 Docker 容器内；本轮不再保留宿主机 MySQL cnf 模板，避免后续误按错误路径操作。
- 新增默认 dry-run 的资源上限安装脚本：`scripts/install_platform_resource_limits.py`。
  - 默认只输出计划，不写系统目录。
  - `--apply` 才写入配置；写入前备份旧文件到 `/etc/tquant-resource-backups/<timestamp>/`。
  - Docker daemon 配置使用 JSON merge，保留既有 daemon 配置，只覆盖 `log-opts` 边界。
  - 脚本不写宿主机 MySQL cnf，不清理 MySQL 数据、不清理 binlog、不 prune Docker volumes。
- 新增 MySQL 与平台资源上限运维手册：`docs/operations/mysql-maintenance-runbook.md`。
- 这些模板和安装脚本本轮只在本地 dry-run 验证，未安装到云服务器。

### Phase B：frontend-next 高 ROI 降载

- `DataGrid` 纯别名已移除，源码中已无 `DataGrid` 引用。
- `/next/strategy-tracking` 已从前端 fallback-first 推进到后端 BFF 合包：
  - `backend/app/models/schema_defs/bff.py` 将 `StrategyWorkspaceBffResponse` 扩展到 `schema_version=v16`，包含 `items`、`summary`、`performance`、`holding_analysis`、`review`、`tracking_notes` 等首屏/常用 payload。
  - `backend/app/services/bff/strategy_workspace.py` 复用 `StrategyTrackingService.list_items(range_days=60, board_filter="include_all", limit=50, offset=0, sort="max_gain_desc")` 和现有 live overlay，只读合包，不改变生产策略语义、生产排序、`production_score` 或 `priority_board`。
  - `docs/contracts/openapi.json`、`docs/contracts/openapi.hash`、`frontend-next/src/generated/api-types.ts` 已同步。
  - 新后端实例验证：`/api/bff/v1/workspace/strategy` 返回 `schema_version=v16`、`item_count=5`、`total=5`、`has_summary=true`、`performance_count=3`、`partial_errors=[]`。
  - `FRONTEND_NEXT_API_TARGET=http://127.0.0.1:8011 API_BASE=http://127.0.0.1:8011 npm run perf:compare` 下，`/next/strategy-tracking` 首屏请求为 2 个：`/api/auth/me` + `/api/bff/v1/workspace/strategy`，不再请求 `/api/strategy-tracking/items`，`items` 422 为 0。
  - 本机默认 8000 后端进程尚未重启时仍返回旧 `schema_version=v15`；前端现在保持首屏 2 requests，并用 UI telemetry 标记 `strategy-workspace-contract=outdated`，不再自动触发多接口首屏 fallback。
- `/next/paper` 已完成非机甲区域降载：
  - 新增 `frontend-next/src/shared/ui/VirtualDataTable.tsx`，复用 TanStack Virtual 输出稳定表格结构。
  - 当前持仓使用 shared `VirtualList`，工作流明细表使用 `VirtualDataTable`。
  - 自动化/复盘工作流改为首屏懒挂载，用户点击“展开工作流”后再渲染大表和 tabs。
  - 机甲组件按用户边界保持原样，不改 DOM 和特效。
  - 当前 DOM 复测：整页 `* = 343`，机甲组件 descendants `171`，非机甲页面 descendants `82`，懒挂载入口 descendants `4`，未展开 workflow panel descendants `0`。在“机甲组件不改”边界下，整页 `<150` 不可达；非机甲区域已低于 150。
- `request:trace` 增加逐路由请求预算守卫：`/next/strategy-tracking` 总 API 请求 `<=2`，且禁止首屏请求 `/api/strategy-tracking/items`、`/api/strategy-tracking/summary`、`/api/strategy-tracking/performance`。
- CSS 无损收敛：
  - `frontend-next/scripts/css-budget.mjs` 已按需求口径输出 `source_css_bytes_target=180000`、`source_css_important_target=25`，避免继续把 raw 299KB 误标为完全达标。
  - 第一批/第二批只移除状态色、页面根 display、单类背景/边框这类低风险 `!important`，不碰 reduced-motion、机甲特效和 legacy 结构覆盖。
  - `!important` 从 51 收敛到 23，达到 <=25 目标。
  - source CSS raw 当前 299197 bytes，仍高于 180KB；因为当前新视觉依赖独立 feature CSS + legacy workspace 皮肤双层资产，直接删除候选选择器有视觉回退风险，本轮保留 raw 未达标解释，不做 PurgeCSS 或批量删除。
  - `npm run visual:consistency` 复验 9 页 x 4 视口，共 36 张截图，0 failed。
- ECharts/chunk 复验：
  - `npm run build` 通过。
  - ECharts 仍被拆成独立低频 chunks：`echarts-renderers`、`echarts-components`、`echarts-charts`，未并入 `index` 首屏入口。
  - 新增 `npm run chunk:profile`，基于正式 `dist/index.html` 与 `dist/assets` 生成可重复证据：
    - 报告：`docs/reports/frontend-next-chunk-profile-2026-06-08.md/json`。
    - 首屏 JS raw：282841 bytes，低于 350000 bytes 目标。
    - 首屏 JS gzip：85336 bytes。
    - 首屏 ECharts assets：0。
    - ECharts lazy assets：3 个，总 raw 457660 bytes，均未出现在 HTML `script`/`modulepreload` 初始资产中。
  - 当前 JS bundle budget 仍通过，lint 输出 `Bundle budget passed (29 chunks, 1219287 bytes)`。

### Phase D：DuckDB/Parquet 数据分层

- 已在现有 analytics 层基础上新增多张快照表归档能力：
  - `backend/app/services/analytics/schemas.py` 新增 `STRATEGY_TRACKING_SNAPSHOTS_SCHEMA`。
  - 新增 `KEY_LEVEL_SNAPSHOTS_SCHEMA`、`LOW_BUY_RESULT_SNAPSHOTS_SCHEMA`。
  - `backend/app/services/analytics/exporters.py` 新增 `export_strategy_tracking_snapshots_parquet`、`export_key_level_snapshots_parquet`、`export_low_buy_result_snapshots_parquet`。
  - `backend/app/services/tasks/registry.py` 新增 analytics worker 任务类型 `analytics_export_strategy_tracking_snapshots`、`analytics_export_key_level_snapshots`、`analytics_export_low_buy_result_snapshots`。
  - `backend/app/services/tasks/analytics_handlers.py` 新增对应 handler。
- 回测明细已纳入分析层：
  - 新增 `backend/app/services/analytics/backtest_exporters.py`。
  - 新增 `BACKTEST_RUNS_SCHEMA`、`BACKTEST_TRADES_SCHEMA`、`BACKTEST_DAILY_SNAPSHOTS_SCHEMA`。
  - 新增只读导出函数 `export_backtest_runs_parquet`、`export_backtest_trades_parquet`、`export_backtest_daily_snapshots_parquet`。
  - 新增 analytics worker 任务类型 `analytics_export_backtest_runs`、`analytics_export_backtest_trades`、`analytics_export_backtest_daily_snapshots`。
  - `backend/tests/test_analytics_layer.py` 已覆盖 manifest、no_data、DuckDB `read_parquet` 可读性。
- 报告/分析明细已纳入分析层：
  - 新增 `ANALYSIS_LOGS_SCHEMA`、`MARKET_REVIEW_REPORTS_SCHEMA`、`PAPER_REVIEW_REPORTS_SCHEMA`。
  - 新增只读导出函数 `export_analysis_logs_parquet`、`export_market_review_reports_parquet`、`export_paper_review_reports_parquet`。
  - 新增 analytics worker 任务类型 `analytics_export_analysis_logs`、`analytics_export_market_review_reports`、`analytics_export_paper_review_reports`，并纳入低优先级暂停清单。
  - `backend/tests/test_analytics_layer.py` 已验证三类报告/分析明细 manifest 与 DuckDB 可读性。
- 导出行为只读 MySQL，按 `generated_at`、`trade_date` 或 `latest_trade_date` 日期分区写入 Parquet，并生成 manifest，记录 `source_table`、日期范围、行数、文件 hash、路径、质量状态。
- 无数据时 manifest 显式 `quality_status=no_data`，不伪造 Parquet 文件。
- 当前未实现任何 MySQL 源表清理；清理仍需 manifest 校验、恢复路径和单独授权。
- 新增 `backend/app/services/analytics/retention.py` 作为热库保留窗口只读 planner：
  - 依据 manifest 的 `dataset_key`、`source_table`、`period_start`、`period_end`、`row_count`、`files[].sha256` 校验归档证据。
  - 白名单支持 `daily_bars`、`strategy_tracking_snapshots`、`key_level_snapshots`、`low_buy_result_snapshots`、`backtest_runs`、`backtest_trades`、`backtest_daily_snapshots`、`analysis_logs`、`market_review_reports`、`paper_review_reports`。
  - 只输出 `candidate_range`、`candidate_row_count`、`dry_run_sql`、`cleanup_sql_template`、`blockers` 和安全要求；不执行 `DELETE`，不清 MySQL 源数据。
  - 清理 SQL 只是模板，必须另行完成备份、恢复路径、manifest 校验和用户/运维授权后才能执行。
- 新增只读 manifest 复验脚本 `scripts/verify_analytics_manifests.py`：
  - 校验 latest manifest、dataset/source/date window/row_count、Parquet 文件存在性和 sha256。
  - 本地/远程均只读；远程通过 `sudo python3 -` 读取 Docker volume 文件，不导出、不删除、不修改 manifest 或 MySQL。
  - 报告写入 `docs/reports/platform-analytics-manifests-2026-06-08.md/json`。
  - 当前云端复验：`daily_bars` manifest present，2,443,775 rows，25 个 Parquet 文件 hash 全部匹配；旧 manifest 缺 `manifest_id` 只列 warning。其余 9 类新增快照/回测/报告 manifest 仍 missing，整体 status blocking，不能作为 MySQL 热库清理依据。
- 新增 dry-run 导出计划脚本 `scripts/plan_analytics_manifest_exports.py`：
  - 输入 `docs/reports/platform-analytics-manifests-2026-06-08.json`，输出 `docs/reports/platform-analytics-export-plan-2026-06-08.md/json`。
  - 只把 manifest 缺口映射成低优先级 `analytics-worker` 任务计划，不 enqueue、不执行 exporter、不修改 MySQL、不清源表。
  - 当前计划状态为 `blocking`：`daily_bars` 计为 ready 但建议 lifecycle refresh；9 类新增快照/回测/报告数据集需要导出并复验。
  - 必须等这些导出任务完成且 `scripts/verify_analytics_manifests.py` 复验无 blocking 后，才允许进入 MySQL 热库保留窗口 dry-run；仍需单独授权才能清理源表。
- 新增默认 dry-run 的导出任务提交器 `scripts/submit_analytics_manifest_exports.py`：
  - 输入 `docs/reports/platform-analytics-export-plan-2026-06-08.json`，输出 `docs/reports/platform-analytics-export-submission-dry-run-2026-06-08.md/json`。
  - 默认只生成提交预览，不写 `runtime_tasks`；`--apply` 模式还必须提供固定确认词 `--confirm-apply submit-analytics-manifest-exports`。
  - apply 模式只通过 `RuntimeTaskQueue.enqueue` 写入任务队列，不执行 exporter、不启动 worker、不清源表。
  - 当前 dry-run 选中 9 个缺失 manifest 导出任务，priority=900，submitted tasks=0。
- `docs/operations/mysql-maintenance-runbook.md` 已补 Analytics Manifest 导出与复验流程：
  - 先只读复验 manifest，再生成导出计划和 dry-run 提交预览。
  - 显式 apply 只入队低优先级 analytics worker 任务。
  - 提供 worker/队列观察、任务取消和导出后 `--fail-on-blocking` 复验步骤。
  - 明确即使 manifest 复验通过，也不能自动清 MySQL 源表，仍需备份、恢复路径和单独授权。
- 新增平台资源优化 readiness 聚合脚本 `scripts/verify_platform_optimization_readiness.py`：
  - 汇总资源 baseline、MySQL backup verification、Worker 预算、Analytics manifest、导出计划和提交预览六类检查。
  - 只读聚合 JSON，不连接数据库、不写任务队列、不执行清理。
  - 输出 `docs/reports/platform-optimization-readiness-2026-06-08.md/json`。
  - 当前总状态为 `blocking`：`mysql_backup_verification` 和 `analytics_export_submission` 为 ready，阻断项为 9 个 manifest 仍缺失；资源上限配置缺失、swap 100%、slow log 3.1G、Docker build cache 5.961G、`max_binlog_size=1GB`、运行容器缺低优先级暂停 env 均列为 warning。
- 新增运维窗口执行计划脚本 `scripts/plan_platform_maintenance_window.py`：
  - 输入 readiness 聚合报告和 manifest 导出计划，输出 `docs/reports/platform-maintenance-window-plan-2026-06-08.md/json`。
  - 只生成有序命令清单，不执行命令、不部署、不切流、不清 MySQL 源表；命令清单明确本地控制端、SSH 远端执行目录和失败即停策略。
  - 当前计划包含 9 个步骤：资源只读复验、同日期 MySQL 备份校验、资源上限 dry-run、资源上限 apply、资源复验、manifest 复验/计划/dry-run、manifest 显式入队、worker 观察、导出后复验、最终性能与全量验收 gate。
  - 资源 apply、容器重启、MySQL slow log 备份/强制轮转和 manifest apply 入队均通过 SSH 在 `/home/ubuntu/gupiao-upload` 执行；dry-run/apply/submission 报告通过 `scp` 回传本地 `docs/reports/`，避免远端证据丢失。
  - readiness 命令显式传入同日期 `platform-mysql-backup-verification-*.json`，避免维护窗口复用旧备份证据。
  - 最终 after-export readiness 显式传入 after-limits resource/budget/backup 与 after-export manifest/export/submission 全套报告，避免 manifest 导出后仍误读旧阻断报告。
  - 最终 gate 包含三轮线上 `quick_cloud_deploy.sh --verify-only --performance-verify`、frontend-next 全链路、后端组合、Go/Rust acceptance、最终 acceptance/audit 和 git 边界检查；最终 acceptance/audit 同样显式传入 after-limits/after-export 全套报告，并通过最新 `gupiao-cloud-performance-*.json` 消费刚复跑出的三轮线上性能证据。
  - 标记 `resource_limits_apply` 和 `analytics_manifest_enqueue` 为需要人工执行的 apply 步骤，并写明回滚/取消方式。
- 回测输入降载：
  - 新增 `backend/app/services/backtest/parquet_data_provider.py`。
  - `BacktestJobService` 通过 `_daily_bar_data_provider` 工厂选择数据源。
  - 默认 `BACKTEST_PARQUET_DAILY_BARS_ENABLED=false`，不改变当前回测行为。
  - 开启后优先从 daily_bars Parquet/DuckDB 读取 `trade_dates` 和 `bars`；低吸信号仍从事务库读取，保持信号语义不变。
  - 缺 manifest、DuckDB/pyarrow 依赖或 Parquet 文件时，默认 `BACKTEST_PARQUET_DAILY_BARS_FALLBACK_TO_MYSQL=true` 回退 MySQL。
  - backtest worker 已共享 `app_runtime_data:/app/backend/data`，并可安装 analytics 依赖；Web 主进程仍不启用 analytics 重任务。

### Phase C：Worker 降载

- 已新增默认关闭的低优先级任务暂停开关：
  - `backend/app/core/config.py` 新增 `runtime_low_priority_tasks_paused`。
  - `runtime_low_priority_task_types` 默认覆盖 analytics export、24M DuckDB 报告、数据回补/修复、回测研究、ML/factor 等重任务。
  - `backend/app/services/tasks/queue.py` 在 `claim_next` 时过滤暂停清单，仅阻止 worker 领取这些任务，不删除、不取消、不改任务 payload。
- `/api/runtime-tasks/summary` 已新增低优先级暂停观测字段：
  - `low_priority_tasks_paused`：当前是否启用低优先级暂停。
  - `paused_task_types`：当前暂停任务类型清单。
  - `paused_queued`：queued 中因暂停清单暂不领取的任务数。
  - `claimable_queued`：queued 中仍可被 worker 领取的任务数。
  - `paused_task_type_counts`：按任务类型拆分的暂停积压。
- 该 summary 计算只读，不触发 stale recovery，不修改任务状态；worker 是否领取仍只由 `claim_next` 控制。
- `frontend-next` `/next/data` 已接入 `runtimeTaskSummary`，在“数据处理后台与链路积压”卡片显示低优先级降载状态、暂停积压和可领取队列数，便于 cutover/部署窗口确认重任务已降载。
- `docker-compose.mysql.yml` 已把 `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` 和 `RUNTIME_LOW_PRIORITY_TASK_TYPES` 传入 `runtime-worker`、`runtime-scheduler`、`backtest-worker`、`analytics-worker`，云端可在部署/cutover 验证期统一暂停重任务领取。
- `docker-compose.mysql.yml` 已固化默认低优先级任务清单，覆盖 analytics export、回测导出、24M DuckDB 报告、数据回补/修复、研究回测、ML/factor。云端不设置 `RUNTIME_LOW_PRIORITY_TASK_TYPES` 时也不会用空字符串覆盖应用默认清单。
- 默认配置为关闭，因此现有运行行为不变。
- 该开关用于开盘高峰、部署、cutover 验证或 swap 连续偏高时临时降载；恢复开关后队列继续按原 priority 执行。
- MySQL 与 SQLAlchemy 连接预算已收敛为单机默认：
  - MySQL `MYSQL_MAX_CONNECTIONS` 默认从 300 调整为 120，仍可通过环境变量覆盖。
  - Web pool 默认 `4 + 4 overflow`；runtime/backtest worker 默认 `2 + 2 overflow`；scheduler 默认 `2 + 2 overflow`；analytics 默认 `4 + 4 overflow`。
  - 该配置只影响未来 compose 启动/部署，当前未对云端容器执行重启。
- 新增只读运行态复验脚本 `scripts/verify_platform_budget.py`：
  - 输出 `docs/reports/platform-budget-2026-06-08.md/json`。
  - 读取远程 `docker compose config`、运行容器 env 和 MySQL `max_connections`/`Threads_connected`/`Threads_running`。
  - 报告只保留连接池/Worker 降载相关白名单 env，不写 token、password、secret。
  - 当前云端复验：无 blocking；应用连接池预算总和 28，Web `RUNTIME_BACKGROUND_JOBS_ENABLED=false`、`TQUANT_ANALYTICS_ENABLED=false`；运行态 `max_connections=300`，低优先级暂停 env 尚未进入运行容器，需要后续运维窗口重启/配置生效后复验。

### Phase E：预构建镜像部署入口

- 新增 `scripts/build_prebuilt_images.sh` 作为本地/CI 预构建镜像产出入口：
  - 默认只 build + tag，不 push，不部署。
  - 显式 `--push` 才推送镜像。
  - 输出 `DEPLOY_PREBUILT_WEB_IMAGE_REF`、`DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF`、`DEPLOY_PREBUILT_GO_BFF_IMAGE_REF`、`DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF`、`DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF`，可直接传给部署脚本。
- `scripts/deploy_cloud_server.sh` 已新增预构建镜像 pull + restart 路径，默认 `DEPLOY_PREBUILT_IMAGES_ENABLED=auto`：
  - 当提供完整镜像 ref 时，云端优先 `docker pull` 并 tag 到 compose 使用的本地镜像名。
  - Web 侧 tag：`tquant-web:mysql`。
  - Analytics 侧 tag：`tquant-analytics:mysql`。
  - Go 侧 tag：`tquant-go-bff:mysql`、`tquant-go-market-read:mysql`、`tquant-go-scan-worker:mysql`。
  - 镜像 ref 不完整时自动回退原云端 build 路径；若显式 `DEPLOY_PREBUILT_IMAGES_ENABLED=1`，缺少任一所需 ref 会失败并停止部署。
- `scripts/quick_cloud_deploy.sh` 已新增 CLI：
  - `--prebuilt-images`
  - `--prebuilt-web-image <ref>`
  - `--prebuilt-analytics-image <ref>`
  - `--prebuilt-go-bff-image <ref>`
  - `--prebuilt-go-market-read-image <ref>`
  - `--prebuilt-go-scan-image <ref>`
- `.env.deploy.local.example` 已补充预构建镜像配置样例和构建脚本入口。
- 本轮只落地脚本能力和测试，未向云服务器推送新镜像，未执行 pull + restart，未部署、未切流。

## 当前云端资源 Baseline

采集命令：

```bash
cd /Users/j/Documents/gupiao
python3 scripts/collect_platform_resource_report.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --json-output docs/reports/platform-resource-baseline-2026-06-08.json \
  --markdown-output docs/reports/platform-resource-baseline-2026-06-08.md
```

结果摘要：

| 指标 | 当前值 | 状态 |
| --- | ---: | --- |
| 根分区 | 59G total / 32G used / 26G available / 56% | OK |
| 内存 | 3723MB total / 154MB available | Warning |
| Swap | 1987MB used / 100% | Warning |
| Docker images | 9.525GB | 观察 |
| Docker volumes | 11.35GB | 观察，未清理 |
| Docker build cache | 5.961GB | Warning，目标 <=2GB |
| systemd journal | 1.2G | Warning，目标 300M/7day |
| MySQL volume | 11G | 观察 |
| MySQL slow log | 3.1G | Warning，目标 <=512M 或轮转 |
| binlog retention | 259200 秒 | OK |
| binlog count | 5，约 4.73GB | 观察 |
| max binlog size | 1073741824 bytes | Warning，模板目标 256M |
| deploy backups | 0 个 / 0 bytes | OK |
| MySQL backups | 1 个 / 140674550 bytes | OK，最新 `/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz` |
| MySQL backup artifact verification | gzip OK / SQL signature OK / sha256 `f82db5fa2334fdd84abc4f7d2e136fd3af82742354ebb6a3bb24767215380db5` | OK，只读校验，不恢复 |
| 连接池预算 | 应用预算总和 28 / `Threads_connected=21` | OK |
| MySQL max_connections | 300 | Warning，compose 目标 120 尚未运行态生效 |
| Analytics manifests | `daily_bars` ready / 9 missing | Blocking，不能清理 MySQL 源数据 |

当前 warning：

- `swap_used_pct=100.0`
- `mysql_slow_log_bytes=3328599654`
- `docker_build_cache_bytes=6400575012`
- `max_binlog_size=1073741824`
- `resource_config_missing=docker_daemon`
- `resource_config_missing=journald_dropin`
- `resource_config_missing=buildkit`
- `resource_config_missing=mysql_compose_resource_config`
- `resource_config_missing=mysql_slow_logrotate`

当前 blocking：无。

### quick deploy verify-only 资源 gate 复验

命令：

```bash
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false RUN_REMOTE_SAFE_CLEANUP=0 ./scripts/quick_cloud_deploy.sh \
  --verify-only --skip-public-entry-verify \
  --host 43.143.243.97 --user ubuntu --key /Users/j/Downloads/gupiao.pem \
  --port 18090 --public-base-url http://43.143.243.97:18090
```

结果：

- PASS，未部署、未切流。
- verify-only 先执行只读资源 preflight，再执行远程健康检查。
- `preflight:root_used_pct=56`，无 blocking。
- `preflight:docker_build_cache_gb=5`，输出 `preflight:warning_docker_build_cache_gb=5`。
- `preflight:mysql_slow_log_mb=3163`，输出 `preflight:warning_mysql_slow_log_mb=3163`。
- `preflight:binlog_expire_seconds=259200`，保留周期 OK。
- `preflight:max_binlog_size_mb=1024`，输出 `preflight:warning_max_binlog_size_mb=1024`。
- `preflight:mysql_compose_resource_config=missing`，输出 `preflight:warning_mysql_compose_resource_config=missing`。
- `preflight:journald_resource_config=missing`，输出 `preflight:warning_journald_resource_config=missing`。
- `preflight:deploy_backup_count=0`，无部署归档堆积。
- `preflight:mysql_backup_count=1`，当前存在全库备份观测证据。
- 后续远程健康检查通过：MySQL、runtime scheduler/worker、analytics worker、Go BFF/market/scan、web image、`/readyz`、受保护 API、MySQL tuning 均通过。

### 连接池/Worker 降载只读复验

命令：

```bash
python3 scripts/verify_platform_budget.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --json-output docs/reports/platform-budget-2026-06-08.json \
  --markdown-output docs/reports/platform-budget-2026-06-08.md
```

结果：

- PASS，未部署、未切流、未重启容器。
- 状态 `warning`，blocking 0。
- MySQL `max_connections=300`，仍未应用 compose 目标 120。
- `Threads_connected=21`、`Threads_running=2`。
- 应用连接池预算总和 28，低于脚本目标 40。
- Web 容器 `RUNTIME_BACKGROUND_JOBS_ENABLED=false`、`TQUANT_ANALYTICS_ENABLED=false`，符合“Web 主进程不跑重任务”边界。
- 运行容器暂缺 `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` env；compose/代码已准备，需运维窗口重启后复验。
- 报告已做 env 白名单，未保存 token/password/secret。

### Analytics Manifest 只读复验

命令：

```bash
python3 scripts/verify_analytics_manifests.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics \
  --json-output docs/reports/platform-analytics-manifests-2026-06-08.json \
  --markdown-output docs/reports/platform-analytics-manifests-2026-06-08.md
```

结果：

- PASS，远程只读；未导出、未删除、未清 MySQL 源数据。
- 状态 `blocking`，原因是 9 类新增 manifest 缺失。
- `daily_bars`：manifest present，`row_count=2443775`，`quality_status=ok`，25 个文件 sha256 全部匹配。
- `daily_bars` 旧 manifest 缺 `manifest_id`，作为 lifecycle warning 保留，不影响当前文件 hash 复验。
- 缺失：`strategy_tracking_snapshots`、`key_level_snapshots`、`low_buy_result_snapshots`、`backtest_runs`、`backtest_trades`、`backtest_daily_snapshots`、`analysis_logs`、`market_review_reports`、`paper_review_reports`。
- 结论：不能作为 MySQL 热库清理依据；需先在线生成并校验缺失 manifest。

### Analytics Manifest 导出计划

命令：

```bash
python3 scripts/plan_analytics_manifest_exports.py \
  --manifest-report docs/reports/platform-analytics-manifests-2026-06-08.json \
  --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics \
  --end-date 2026-06-08 \
  --json-output docs/reports/platform-analytics-export-plan-2026-06-08.json \
  --markdown-output docs/reports/platform-analytics-export-plan-2026-06-08.md
```

结果：

- PASS，本地 dry-run；未提交 runtime task、未执行 exporter、未连接数据库、未清 MySQL 源数据。
- 状态 `blocking`，`manifest_export_required_count=9`。
- `daily_bars`：当前 manifest 可用，属于 `lifecycle_refresh_optional`，可在低峰期刷新 manifest lifecycle 字段。
- 需要导出的 9 个低优先级任务：`analytics_export_strategy_tracking_snapshots`、`analytics_export_key_level_snapshots`、`analytics_export_low_buy_result_snapshots`、`analytics_export_backtest_runs`、`analytics_export_backtest_trades`、`analytics_export_backtest_daily_snapshots`、`analytics_export_analysis_logs`、`analytics_export_market_review_reports`、`analytics_export_paper_review_reports`。
- 每个任务 payload 已写入 `docs/reports/platform-analytics-export-plan-2026-06-08.json`，统一包含 `output_root`、`end_date` 和 `idempotency_key`。
- 任务完成后必须复跑 manifest 复验；复验无 blocking 前，不能进入 MySQL 热库清理。

### Analytics Manifest 导出任务提交预览

命令：

```bash
python3 scripts/submit_analytics_manifest_exports.py \
  --export-plan docs/reports/platform-analytics-export-plan-2026-06-08.json \
  --json-output docs/reports/platform-analytics-export-submission-dry-run-2026-06-08.json \
  --markdown-output docs/reports/platform-analytics-export-submission-dry-run-2026-06-08.md
```

结果：

- PASS，dry-run；未写 runtime task、未执行 exporter、未清源表。
- 状态 `ready_to_submit`。
- 选中 9 个任务，提交数 0。
- 所有任务优先级为 900，使用 `analytics-export:<dataset>:2026-06-08` 作为 idempotency key。
- 后续若进入运维窗口，需显式执行 `--apply --confirm-apply submit-analytics-manifest-exports`；执行后仍只入队，不会在该脚本中同步执行导出。
- 具体运维顺序已写入 `docs/operations/mysql-maintenance-runbook.md` 的“Analytics Manifest 导出与复验”章节。

### 平台资源优化 Readiness 聚合

命令：

```bash
python3 scripts/verify_platform_optimization_readiness.py \
  --json-output docs/reports/platform-optimization-readiness-2026-06-08.json \
  --markdown-output docs/reports/platform-optimization-readiness-2026-06-08.md
```

结果：

- PASS，只读聚合；未部署、未切流、未写 runtime task、未执行 exporter、未清 MySQL 源数据。
- 总状态 `blocking`。
- 阻断项：`manifest:manifest_blocked_count=9`。
- 资源 warning：缺 Docker daemon、journald drop-in、BuildKit、MySQL compose resource command、slow logrotate 配置；swap 100%；slow log 3.1G；Docker build cache 5.961G；`max_binlog_size=1GB`。
- Worker warning：线上 `max_connections=300`，运行容器缺低优先级暂停 env。
- 导出计划 warning：仍有 9 个 required export task。
- 提交预览状态：ready，9 个任务已选中，submitted=0。

### 运维窗口执行计划

命令：

```bash
python3 scripts/plan_platform_maintenance_window.py \
  --readiness-report docs/reports/platform-optimization-readiness-2026-06-08.json \
  --export-plan docs/reports/platform-analytics-export-plan-2026-06-08.json \
  --date-tag 2026-06-08 \
  --json-output docs/reports/platform-maintenance-window-plan-2026-06-08.json \
  --markdown-output docs/reports/platform-maintenance-window-plan-2026-06-08.md
```

结果：

- PASS，只生成计划；未执行命令、未部署、未切流、未写队列、未清 MySQL 源表。
- 计划步骤 9 个：资源 readiness 只读复验、同日期 MySQL 备份校验、资源上限 dry-run、资源上限 apply、资源复验、manifest preflight、manifest 入队、worker 观察、manifest 后验、最终性能与全量验收 gate；远端 apply 步骤显式备份并强制轮转 MySQL slow log，关键远端报告通过 `scp` 回传；最终 readiness 使用 after-limits resource/budget/backup 与 after-export manifest/export/submission 报告，最终 acceptance/audit 使用最新 `gupiao-cloud-performance-*.json` 作为线上性能证据。
- 人工 apply 步骤 2 个：`resource_limits_apply` 和 `analytics_manifest_enqueue`。
- 安全边界写入报告：`does_execute_commands=false`、`does_deploy=false`、`does_cutover=false`、`does_clean_mysql_source_tables=false`、`does_delete_docker_volumes=false`。

### 最终验收草案聚合

命令：

```bash
python3 scripts/render_platform_resource_optimization_acceptance.py \
  --json-output docs/reports/platform-resource-optimization-acceptance-2026-06-08.json \
  --markdown-output docs/reports/platform-resource-optimization-acceptance-2026-06-08.md
```

结果：

- PASS，只聚合现有报告；未执行命令、未部署、未切流、未写队列、未清 MySQL 源表。
- 输出：
  - `docs/reports/platform-resource-optimization-acceptance-2026-06-08.json`
  - `docs/reports/platform-resource-optimization-acceptance-2026-06-08.md`
- 总状态 `blocking`，open items 19。
- 自用结论：可以继续通过 `/next/*` 自用和验收。
- 正式 cutover 状态：`not_ready`；必须先补齐 9 个 manifest、在线 apply/复验资源上限、复跑完整 gate，并由用户单独授权。
- 报告已覆盖新增/修改重点文件、Phase 完成度、before/after 指标、资源状态、MySQL 日志/备份状态、Worker 降载状态、Parquet manifest 状态、回滚方式、未完成项、旧 `frontend/` 与 `strategy_policy.py` 保护结论。

### 完成度审计

命令：

```bash
python3 scripts/audit_platform_resource_optimization_completion.py \
  --json-output docs/reports/platform-resource-optimization-completion-audit-2026-06-08.json \
  --markdown-output docs/reports/platform-resource-optimization-completion-audit-2026-06-08.md \
  --fail-on-incomplete
```

结果：

- 预期返回 `42`，因为当前目标尚未完成；报告已正常写出。
- 输出：
  - `docs/reports/platform-resource-optimization-completion-audit-2026-06-08.json`
  - `docs/reports/platform-resource-optimization-completion-audit-2026-06-08.md`
- 总状态 `blocking`。
- 汇总：21 passed / 5 warning / 9 blocked / 0 not_verified / total 35。
- 9 个 blocking：`max_binlog_size=1GB`、slow log 3.1G/logrotate 未在线安装、systemd journal 1.2G/journald drop-in 未在线安装、Docker build cache 5.961G、资源配置未在线 apply、MySQL `max_connections=300` 未收敛、低优先级暂停 env 未进运行容器、swap 100%、9 个目标 manifest 缺失。
- 未完成项快照已单独记录：`docs/reports/platform-resource-optimization-open-items-2026-06-08.md`。
- 新增机器化证据：`frontend-next/scripts/perf-profile.mjs` 现在写出 `docs/reports/frontend-next-perf-compare-2026-06-08.json`，完成度审计优先读取该 JSON 验证 `/next/strategy-tracking` 首屏 2 API / items 422 为 0、`/next/paper` 非机甲 DOM 82。
- Cutover/生产资源 gate 已补入 `docs/frontend-next-cutover-runbook-2026-06-05.md` 和 `PRODUCTION_RUNBOOK.md`；正式部署/切流前必须跑 platform resource readiness，blocking 即停止。
- 该审计是当前是否可声明目标完成的硬证据：可以继续 `/next/*` 自用，但不能声明平台资源优化完成或正式 cutover ready。

## 测试结果

已运行：

```bash
backend/.venv/bin/pytest backend/tests/test_platform_resource_report.py -q
backend/.venv/bin/pytest backend/tests/test_bff_strategy_workspace.py backend/tests/test_bff_routes.py::test_strategy_workspace_uses_bff_contract backend/tests/test_contract_first_openapi.py -q
backend/.venv/bin/pytest backend/tests/test_analytics_layer.py backend/tests/test_analytics_manifest_lifecycle.py -q
backend/.venv/bin/pytest backend/tests/test_runtime_task_queue.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_runtime_task_queue.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_backtest_v2_worker_persistence.py backend/tests/test_cloud_performance_script.py::test_backtest_worker_can_read_shared_parquet_analysis_layer -q
backend/.venv/bin/pytest backend/tests/test_cloud_performance_script.py backend/tests/test_cloud_deploy_scripts.py::test_quick_deploy_runs_remote_resource_preflight_without_destructive_prune -q
backend/.venv/bin/pytest backend/tests/test_cloud_deploy_scripts.py -q
backend/.venv/bin/pytest backend/tests/test_platform_resource_report.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_performance_script.py backend/tests/test_platform_resource_report.py backend/tests/test_cloud_deploy_scripts.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_runtime_task_queue.py backend/tests/test_backtest_v2_worker_persistence.py backend/tests/test_cloud_performance_script.py backend/tests/test_platform_resource_report.py backend/tests/test_cloud_deploy_scripts.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_worker_handlers.py backend/tests/test_analytics_production_chain.py backend/tests/test_analytics_worker.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_v2_engine_contract.py backend/tests/test_backtest_v2_api_contract.py -q
python3 scripts/install_platform_resource_limits.py --backup-root /tmp/tquant-resource-backups-test
python3 -m py_compile scripts/install_platform_resource_limits.py scripts/collect_platform_resource_report.py
ruby -e 'require "yaml"; YAML.load_file("docker-compose.mysql.yml"); puts "compose_yaml:ok"'
backend/.venv/bin/python -m py_compile backend/app/models/schema_defs/bff.py backend/app/services/bff/strategy_workspace.py backend/app/api/routes/bff.py
npm run api:generate
npm run typecheck
npm run lint
npm run css:budget
npm run visual:consistency
npm run build
npm run perf:compare
npm run e2e -- tests/e2e/strategy-tracking.spec.ts
npm run e2e -- tests/e2e/paper-mecha.spec.ts
FRONTEND_NEXT_API_TARGET=http://127.0.0.1:8011 API_BASE=http://127.0.0.1:8011 npm run perf:compare
npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build && npm run e2e && npm run request:trace && npm run screenshot:parity && npm run visual:consistency && npm run perf:compare && npm run css:budget && npm run css:unused-report
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_runtime_task_queue.py backend/tests/test_backtest_v2_worker_persistence.py backend/tests/test_cloud_performance_script.py backend/tests/test_platform_resource_report.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_analytics_worker_handlers.py backend/tests/test_analytics_production_chain.py backend/tests/test_analytics_worker.py backend/tests/test_backtest_v2_engine_contract.py backend/tests/test_backtest_v2_api_contract.py backend/tests/test_bff_strategy_workspace.py backend/tests/test_bff_routes.py::test_strategy_workspace_uses_bff_contract backend/tests/test_contract_first_openapi.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_platform_resource_optimization_acceptance.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_platform_resource_optimization_completion_audit.py -q
BACKEND_PYTHON=backend/.venv/bin/python python3 scripts/verify_go_rust_performance_acceptance.py
```

结果：

- `backend/tests/test_platform_resource_report.py`：9 passed，1 个 LibreSSL warning。
- `backend/tests/test_platform_resource_report.py`：16 passed，1 个 LibreSSL warning；覆盖部署归档数量/体积、MySQL 备份状态、缺备份 warning、journald drop-in missing warning、超过 3 个部署归档 warning、0 个归档不误报。
- `backend/tests/test_mysql_backup_artifact_verifier.py`：4 passed，1 个 LibreSSL warning；覆盖本地 `.sql.gz` 校验、坏 gzip 阻断、远程只读命令边界和非破坏性源码守卫。
- `backend/tests/test_platform_resource_report.py` + `backend/tests/test_cloud_deploy_scripts.py::test_quick_deploy_runs_remote_resource_preflight_without_destructive_prune`：17 passed，1 个 LibreSSL warning；覆盖资源巡检和 quick deploy 只读 preflight gate。
- `backend/tests/test_platform_budget_verifier.py`：6 passed，1 个 LibreSSL warning；覆盖连接池预算、Web 不跑重任务、低优先级暂停 env、报告敏感 env 白名单。
- `backend/tests/test_analytics_manifest_verifier.py`：5 passed，1 个 LibreSSL warning；覆盖 manifest hash 校验、缺 manifest blocking、旧 manifest lifecycle warning 和只读源码守卫。
- `backend/tests/test_analytics_manifest_export_plan.py` + `backend/tests/test_analytics_manifest_verifier.py`：9 passed，1 个 LibreSSL warning；覆盖缺失 manifest 到低优先级导出任务计划、hash mismatch 重导、list/dict 报告格式兼容和非破坏性源码守卫。
- `backend/tests/test_analytics_manifest_export_submitter.py` + manifest plan/verifier：14 passed，1 个 LibreSSL warning；覆盖提交器 dry-run 不写库、dataset 过滤、apply 双确认、注入 enqueue 函数和非破坏性源码守卫。
- `backend/tests/test_platform_optimization_readiness.py`：5 passed，1 个 LibreSSL warning；覆盖 readiness 聚合当前 blocking/warning、全 ready、MySQL backup verification 阻断、submission mismatch 阻断和非破坏性源码守卫。
- `backend/tests/test_platform_maintenance_window_plan.py`：2 passed，1 个 LibreSSL warning；覆盖运维窗口执行计划步骤顺序、同日期 MySQL backup verification 证据链、SSH 远端执行目录、scp 证据回传、MySQL slow log 备份后轮转、after-limits/after-export 最终 readiness 报告链、三轮线上性能/全量验收收口、最新云端性能报告传递、apply 双确认、安全边界和非执行源码守卫。
- `backend/tests/test_platform_resource_optimization_acceptance.py`：2 passed，1 个 LibreSSL warning；覆盖最终验收草案当前 blocking、自用/正式 cutover 结论、旧 frontend/strategy_policy 保护、MySQL 备份/manifest 阻断字段和非破坏性源码守卫。
- `backend/tests/test_platform_resource_optimization_completion_audit.py`：2 passed，1 个 LibreSSL warning；覆盖完成度审计当前 blocking、关键阻断项、warning 项和非破坏性源码守卫。
- `backend/tests/test_platform_optimization_readiness.py backend/tests/test_platform_resource_optimization_acceptance.py backend/tests/test_platform_resource_optimization_completion_audit.py backend/tests/test_mysql_backup_artifact_verifier.py`：15 passed，1 个 LibreSSL warning；覆盖 MySQL 备份校验进入 readiness 总 gate、验收草案、完成度审计和备份文件 verifier。
- `quick_cloud_deploy.sh --verify-only --skip-public-entry-verify`：PASS；只读 preflight 输出 `preflight:journald_resource_config=missing`、`preflight:deploy_backup_count=0`、`preflight:mysql_backup_count=1`，未部署、未切流、未清理。
- `backend/tests/test_bff_strategy_workspace.py` + BFF/OpenAPI contract smoke：3 passed，1 个 LibreSSL warning。
- `backend/tests/test_analytics_layer.py` + manifest lifecycle：9 passed，1 个 LibreSSL warning。
- `backend/tests/test_runtime_task_queue.py`：8 passed，1 个 LibreSSL warning。
- `backend/tests/test_runtime_task_queue.py`：11 passed，1 个 LibreSSL warning；覆盖低优先级暂停、暂停 backlog summary、worker/failure/artifact 观测和 stale recovery 只读 summary。
- `py_compile`：`backend/app/models/schema_defs/phase4.py`、`backend/app/services/tasks/queue.py`、`backend/tests/test_runtime_task_queue.py` PASS。
- `backend/scripts/export_openapi_schema.py`：PASS，`RuntimeTaskSummaryResponse` 的低优先级暂停观测字段已同步到 `docs/contracts/openapi.json/hash`。
- `frontend-next` `api:generate`：PASS，`frontend-next/src/generated/api-types.ts` 已同步 runtime task summary 字段。
- `frontend-next` `api:check`：PASS，覆盖新增 `runtimeTaskSummary` operation 和 generated types。
- `frontend-next` `typecheck`：PASS。
- `frontend-next` `lint`：PASS。
- `frontend-next` `tests/e2e/backtest-data-settings.spec.ts`：3 passed；覆盖 `/next/data` 降载观测展示和默认保护模式无写请求。
- `backend/tests/test_analytics_layer.py` + `backend/tests/test_runtime_task_queue.py`：22 passed，1 个 LibreSSL warning。
- `backend/tests/test_analytics_layer.py` + backtest worker persistence + backtest worker Parquet compose 断言：23 passed，1 个 LibreSSL warning。
- `backend/tests/test_cloud_performance_script.py` + deploy preflight smoke：8 passed，1 个 LibreSSL warning。
- `backend/tests/test_cloud_deploy_scripts.py`：34 passed，1 个 LibreSSL warning。
- `backend/tests/test_platform_resource_report.py`：12 passed，1 个 LibreSSL warning。
- `bash -n scripts/quick_cloud_deploy.sh scripts/deploy_cloud_server.sh`：PASS。
- `backend/tests/test_cloud_deploy_scripts.py::test_quick_deploy_runs_remote_resource_preflight_without_destructive_prune`：1 passed，1 个 LibreSSL warning；覆盖 verify-only 只读 preflight、Docker cache/slow log/journald resource/MySQL backup warning 输出、禁止 destructive prune/volume prune。
- `backend/tests/test_analytics_manifest_lifecycle.py`：5 passed，1 个 LibreSSL warning；覆盖 manifest 生命周期、retention planner ready/no_data 阻断和源码非破坏性守卫。
- `py_compile`：`backend/app/services/analytics/retention.py`、`backend/app/services/analytics/__init__.py`、`backend/tests/test_analytics_manifest_lifecycle.py` PASS。
- `backend/tests/test_cloud_performance_script.py::test_mysql_compose_keeps_role_pool_budget_below_single_host_limit`：随 52-test 组合通过。
- `backend/tests/test_analytics_layer.py` + runtime queue + cloud performance/deploy/resource 组合：75 passed，1 个 LibreSSL warning。
- `backend/tests/test_analytics_layer.py` + runtime queue + backtest persistence + cloud performance/deploy/resource 组合：87 passed，1 个 LibreSSL warning。
- `backend/tests/test_analytics_worker_handlers.py` + analytics production chain + analytics worker：10 passed，1 个 LibreSSL warning。
- `backend/tests/test_backtest_v2_engine_contract.py` + `backend/tests/test_backtest_v2_api_contract.py`：21 passed，1 个 LibreSSL warning。
- `scripts/install_platform_resource_limits.py` dry-run：PASS，5 个配置项均为 `applied=false`。
- `py_compile`：资源脚本 PASS。
- `docker-compose.mysql.yml` YAML 解析：PASS。
- `py_compile`：PASS。
- `frontend-next` `api:generate`：PASS，generated types 已同步。
- `frontend-next` typecheck：PASS。
- `frontend-next` lint：PASS。
- `frontend-next` css:budget：PASS；`important_count=23` 达标，`source_css_bytes=299197` 仍需解释；dist CSS gzip `48132` bytes 仍在预算内。
- `frontend-next` css:unused-report：PASS；29 个 CSS 文件、128 个代码文件、1332 个唯一 class selector，792 个被引用，110 个候选未引用 selector，597 个已归类为动态或 legacy selector。
- `frontend-next` 性能汇总报告：`docs/reports/frontend-next-performance-optimization-2026-06-08.md`。
- `frontend-next` CSS 汇总报告：`docs/reports/frontend-next-css-optimization-2026-06-08.md`。
- `frontend-next` visual:consistency：PASS，36 captures / 0 failed。
- `frontend-next` build：PASS；ECharts 为独立 chunks，未并入主入口。
- `frontend-next` chunk:profile：PASS；首屏 JS raw 282841 bytes，首屏 ECharts assets 0，报告写入 `docs/reports/frontend-next-chunk-profile-2026-06-08.md/json`。
- `frontend-next` perf:compare 默认本机后端：PASS；`/next/strategy-tracking` 634ms、2 API 请求、items 422 为 0；`/next/paper` 691ms、整页 DOM 343、非机甲 DOM 82；默认 8000 旧 BFF v15 会通过 UI telemetry 标记合约过旧。
- `frontend-next` strategy-tracking E2E：1 passed。
- `frontend-next` paper E2E：3 passed。
- `frontend-next` perf with new backend 8011：`/next/strategy-tracking` 首屏 2 requests；`/next/paper` DOM breakdown 输出非机甲区域 82 descendants。
- `frontend-next` 全链路：`api:check`、`typecheck`、`lint`、unit、build、E2E、request trace、screenshot parity、visual consistency、perf、CSS budget、unused report 全部通过；unit 86、E2E 46、request trace 9 routes / 0 failures、visual consistency 36 captures / 0 failed。
- 后端组合：资源、预算、Analytics、manifest、Worker、Backtest、BFF/OpenAPI、部署脚本和验收审计相关 133 passed，1 个 LibreSSL warning。
- Go/Rust 性能验收：PASS，输出 `docs/reports/go-rust-performance-acceptance-2026-05-27.json`；Go market-read cached payload benchmark 8091 ns/op、11471 B/op、215 allocs/op，Rust seam speedup max_drawdown 7.157 / rolling_mean 11.844 / atr_wilder 9.446。
- 线上 Web/API performance 机器证据：`docs/reports/gupiao-cloud-performance-2026-06-08-000012.json` 为 `ok=true`、`failures=[]`；p95：`readyz=7.336ms`、`monitor_bff=30.266ms`、`market_pulse=28.294ms`、`priority_board=103.424ms`、`watchlist_signals=24.109ms`。资源 apply、worker 重启、manifest 导出后仍必须重跑三轮 online performance gate。
- MySQL 备份文件校验：`docs/reports/platform-mysql-backup-verification-2026-06-08.md/json` 为 status ok；最新备份 `/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz` gzip 完整、SQL dump 特征通过、sha256 已归档。

## 未完成项

| Phase | 未完成项 | 原因/下一步 |
| --- | --- | --- |
| A | 安装 Docker daemon、BuildKit、slow logrotate、journald drop-in 上限配置 | 模板、dry-run 安装脚本、巡检 warning 和部署 preflight gate 已完成；本轮按边界不部署、不改云端配置，需要单独运维执行窗口。 |
| A | slow log 3.1G 轮转/压缩/截断 | runbook 已补“先备份再轮转”；尚未在线执行，需要运维窗口验证 MySQL/readyz。 |
| A | `max_binlog_size` 仍为 1GB | Compose 目标已补为 `MYSQL_MAX_BINLOG_SIZE=256M`；线上容器尚未重建，需要运维窗口 `up -d mysql` 后复验 `@@max_binlog_size`。 |
| A | Docker build cache <=2G | 需要安装 BuildKit GC 或在部署前执行安全 build cache 清理；不得清 volume。 |
| B | `/next/paper` 整页 DOM <150 | 非机甲区域已虚拟化并降到 82 descendants；机甲组件自身 171 descendants 且按边界不能改，因此整页 <150 需要用户另行授权简化机甲 DOM。 |
| B | CSS raw <=180KB | `!important` 已达标到 23；raw 仍 299197 bytes。当前 raw 由 legacy workspace 皮肤 + 页面级样式共同构成，未做批量删除以避免视觉回退；继续优化需逐页拆双源并每步截图验证。 |
| C | MySQL 连接池/worker 并发预算 | Compose 默认池预算、低优先级暂停 guard、summary 可观测字段和 `/next/data` 展示已落地；线上只读预算复验、readiness 聚合和运维窗口执行计划已完成，当前运行态 `max_connections=300` 且低优先级暂停 env 尚未进入容器，需要运维窗口重启/配置生效后复验 swap 下降与三轮 online performance gate。 |
| D | 线上真实 manifest 生成和校验 | `daily_bars` 已在线只读校验通过 25 个文件 hash，但旧 manifest 缺 `manifest_id`；其余 9 类新增快照/回测/报告 manifest 缺失，不能清理 MySQL 源数据。已生成 dry-run 导出计划、提交预览、runbook 和 readiness 聚合报告；下一步需在低峰/运维窗口显式 apply 入队 9 个低优先级 analytics worker 导出任务并复验。 |
| D | 历史查询双源 | 回测 daily bars 输入已支持 Parquet 优先读取，默认关闭并可回退 MySQL；更多历史查询双源路由尚未完成。 |
| E | 预构建镜像 pull+restart 流程 | 构建脚本、部署脚本入口和测试已落地，默认 auto；尚未在云端实际启用，需要 CI/本地产出镜像 ref 后再按运维窗口验证。 |
| F | 线上资源 apply 后的最终全量验收 | 本地 `frontend-next` 全链路、后端组合测试、Go/Rust 性能验收、线上 Web/API performance 当前样本、只读云端资源 gate 和完成度审计已完成；但资源上限与 manifest 导出尚未在线 apply，正式 cutover 前需在运维窗口完成 apply/导出/复验后重跑完整 frontend/backend/resource/performance gate。 |

## 平台影响

不影响。当前改动未部署、未切流；旧 `frontend/` 不作为本轮改造对象；未修改 `strategy_policy.py`；后端改动仅为 strategy workspace BFF 只读合包和 contract schema 扩展，未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。

## 回滚方式

- strategy BFF 合包可回滚 `backend/app/models/schema_defs/bff.py`、`backend/app/services/bff/strategy_workspace.py`、`backend/app/api/routes/bff.py`、`docs/contracts/openapi.json`、`frontend-next/src/generated/api-types.ts` 与对应测试。
- 前端 strategy 请求降载可回滚 `frontend-next/src/features/strategy-tracking/StrategyTrackingPage.tsx` 与对应 E2E 断言。
- paper 非机甲降载可回滚 `frontend-next/src/shared/ui/VirtualDataTable.tsx`、`frontend-next/src/features/paper/PaperPage.tsx`、`frontend-next/src/features/paper/paper-page.css` 与对应 E2E 更新。
- 资源巡检脚本和配置模板未安装到服务器，删除对应新增文件即可回退。
- 云端当前未安装任何本轮模板配置，无运行态回滚动作。

## Cutover 状态

仍需用户单独授权。当前报告不是 cutover 授权，也没有执行部署或切流。
