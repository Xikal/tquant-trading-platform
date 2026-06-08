# frontend-next 与平台资源优化未完成项快照

- 记录时间：`2026-06-08`
- 来源：`docs/reports/platform-resource-optimization-completion-audit-2026-06-08.json`
- 当前审计：`21 passed / 5 warning / 9 blocked / 0 not_verified / total 35`
- 当前结论：`/next/*` 可以继续自用和验收；正式 cutover 仍为 `not_ready`，需要用户单独授权。
- 执行边界：未部署、未切流；旧 `frontend/` 未作为本轮改造对象；未修改 `strategy_policy.py`；未清 MySQL 源数据、binlog 或 Docker volumes。

## Blocking

| ID | 当前证据 | 关闭条件 |
| --- | --- | --- |
| `phase_a.max_binlog_size` | `max_binlog_size=1073741824`，线上仍为 1GB。 | 运维窗口重建 MySQL 容器，使 compose `MYSQL_MAX_BINLOG_SIZE=256M` 生效，并复验 `@@max_binlog_size <= 268435456`。 |
| `phase_a.slow_log_rotation` | `slow_log_bytes=3328599654`，`mysql_slow_logrotate_missing=True`。 | 先备份 slow log，再安装 `/etc/logrotate.d/tquant-mysql-slow-log`，执行轮转并复验单文件 `<=256M`、`/readyz` 和 MySQL 查询正常。 |
| `phase_a.journal_retention` | `journal_usage_bytes=1288490188`，`journald_dropin_missing=True`。 | 安装 journald drop-in，重启 `systemd-journald`，复验 journal 使用量 `<=300M`。 |
| `phase_a.docker_build_cache` | `docker_build_cache_bytes=6400575012`。 | 启用 BuildKit GC 或只清 build cache，复验 `<=2G`；禁止清 Docker volumes。 |
| `phase_a.resource_configs_applied` | 缺 `buildkit`、`docker_daemon`、`journald_dropin`、`mysql_compose_resource_config`、`mysql_slow_logrotate`。 | 按 `docs/reports/platform-maintenance-window-plan-2026-06-08.md` 执行 `resource_limits_apply`，并重跑 baseline/readiness。 |
| `phase_c.mysql_connections` | `max_connections=300`，目标 80-120。 | 重建/重启 MySQL 容器，使 `max_connections=120` 生效，并复跑三轮 online performance gate。 |
| `phase_c.low_priority_pause_env` | runtime/backtest/analytics/scheduler 容器缺 `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` env。 | 重启相关容器，复验低优先级暂停 env 进入运行容器，且任务不丢不重复。 |
| `phase_c.swap_target` | `swap_used_pct=100.0`。 | 资源上限和 worker 降载生效后复验；目标长期 `<20%`，短期 `<500MiB`。 |
| `phase_d.all_required_manifests` | 9 组 manifest missing/blocked：`strategy_tracking_snapshots`、`key_level_snapshots`、`low_buy_result_snapshots`、`backtest_runs`、`backtest_trades`、`backtest_daily_snapshots`、`analysis_logs`、`market_review_reports`、`paper_review_reports`。 | 低峰显式 apply 入队 9 个 analytics export 任务，导出完成后重跑 manifest verifier/readiness；复验无 blocking 前不得清 MySQL 源表。 |

## Warning

| ID | 当前证据 | 处理口径 |
| --- | --- | --- |
| `phase_a.available_memory` | `available_mb=219`，目标 `>800MiB`。 | 资源上限和 worker 降载在线生效后复验；若单机仍不可达，需在最终验收报告写明原因。 |
| `phase_b.paper_virtualization_dom` | `/next/paper` 整页 DOM 343；非机甲 DOM 82，机甲 DOM 171。 | 非机甲区域已达标；若坚持整页 `<150`，需另行授权简化机甲组件 DOM。 |
| `phase_b.css_raw` | `source_css_bytes=299197`，目标 180000；`!important=23` 已达标。 | 当前以说明和视觉一致性 gate 接受；继续瘦身必须逐页截图验证，禁止批量删除导致视觉回退。 |
| `phase_e.prebuilt_deploy` | 脚本入口已完成，云端真实 registry ref 和 pull+restart 尚未执行。 | 产出镜像 ref 后在运维窗口验证；失败回退原 build 路径。 |
| `phase_f.full_gate` | 本地 frontend/backend gate 已过；资源 apply 和 manifest 导出后尚未复跑完整 gate。 | 完成 apply/export 后复跑 frontend-next 全链路、后端组合、Go/Rust acceptance、三轮线上性能、readiness、acceptance 和 audit。 |

## 后续关闭顺序

1. 低峰执行资源上限 apply：备份/安装配置、备份并轮转 slow log、重启 Docker/journald/BuildKit/MySQL/worker 容器。
2. 复验资源：`collect_platform_resource_report.py`、`verify_platform_budget.py`、`verify_mysql_backup_artifact.py`、`verify_platform_optimization_readiness.py`。
3. 显式入队 9 个 analytics manifest 导出任务，观察 worker 队列，导出完成后复验 manifest。
4. 复跑最终 gate：三轮 online performance、frontend-next 全链路、后端组合、Go/Rust acceptance、acceptance/audit、`git diff --check` 和边界检查。
5. 只有 audit 无 blocking 后，才能重新讨论正式 cutover；cutover 仍需用户单独授权。
