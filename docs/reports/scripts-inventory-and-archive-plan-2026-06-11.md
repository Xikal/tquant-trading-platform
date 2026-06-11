# Scripts Inventory 与归档建议（2026-06-11）

## 结论

本批次只做盘点和建议，不移动、不删除脚本。当前顶层 `scripts/` 共有 86 个文件，`backend/scripts/` 共有 53 个文件，合计 139 个脚本。

`rg -n "scripts/|backend/scripts/" .github docs Makefile README.md` 命中广泛，说明脚本与 CI、Makefile、Runbook、历史计划和报告耦合较多。无法证明无引用或用途不明的脚本均标记为 `keep_until_owner_review`。

## 分类总览

| 类别 | 脚本 | 建议 |
|---|---|---|
| 生产部署链路 | `deploy_cloud_server.sh`、`quick_cloud_deploy.sh`、`one_click_cloud_deploy.sh`、`deploy_scope.py`、`deploy_delta_package.py`、`cloud_ssh_lib.sh`、`prod_preflight.sh`、`backup_database.sh`、`install_https_nginx.sh`、`install_backup_cron.sh`、`run_platform_component.sh`、`runtime_snapshot.sh`、`build_prebuilt_images.sh` | 保留；入口收敛到 Makefile/Runbook，不新增平行 deploy 入口 |
| 本地开发链路 | `dev_start_all.sh`、`run_local_prod.sh`、`run_public_app.sh`、`stop_public_app.sh`、`mysql_local_install.sh`、`mysql_local_stop.sh`、`switch_backend_to_local_mysql.sh`、`spawn_detached.py` | 保留；补 Runbook 索引即可 |
| CI/质量门禁 | `warning_budget.py`、`full_regression_runner.py`、`check_backend_perf_budget.py`、`check_rust_bench_baseline.py`、`verify_backend_refactor_foundation.sh`、`verify_go_rust_performance_acceptance.py`、`verify_platform_budget.py`、`verify_platform_optimization_readiness.py`、`qa_smoke.sh`、`ui_smoke.sh`、`app_api_smoke.sh`、`version_sync.py` | 保留；Makefile 已有部分入口 |
| 线上资源/运维只读或授权包 | `collect_platform_resource_report.py`、`install_platform_resource_limits.py`、`cloud_server_cleanup.sh`、`measure_cloud_go_rust_performance.py`、`plan_platform_maintenance_window.py`、`deploy_monitoring_stack.sh`、`verify_mysql_backup_artifact.py` | 保留；线上动作必须授权，dry-run/default-safe 保持 |
| Analytics/Worker 主链 | `backend/scripts/analytics_worker.py`、`backend/scripts/export_analytics_parquet.py`、`backend/scripts/run_duckdb_strategy_report.py`、`scripts/plan_analytics_manifest_exports.py`、`scripts/submit_analytics_manifest_exports.py`、`scripts/verify_analytics_manifests.py`、`scripts/backtest_worker.py` | 保留；属于模块化架构基线 |
| 数据补齐/数据修复 | `backfill_daily_history.py`、`daily_history_backfill_runner.py`、`backfill_daily_limit_prices.py`、`backfill_instrument_metadata.py`、`backfill_etf_execution_metadata.py`、`backfill_etf_minute_history.py`、`clean_invalid_daily_bars.py`、`repair_invalid_ohlc.py`、`sync_a_share_universe.py`、`sync_etf_t0_rules.py`、`db_admin.py`、`apply_performance_indexes.py` | 保留；运行前需明确 dry-run/apply 与数据备份 |
| 低吸/策略回测工具 | `low_buy_market_backtest*.py`、`low_buy_execution_matrix.py`、`strategy_24m_*.py`、`strategy_improvement_closed_loop.py`、`strategy_success_rate_diagnostics.py`、`main_force_model_*.py`、`front_row_weighted_*.py`、`strategy_tracking_daily_refresh.py` | 保留；默认机器产物应落 `backend/data/reports/` |
| 一次性 spike/研究候选 | `backtest_24m_precompute_spike.py`、`parallel_scan_spike.py`、`call_auction_provider_spike.py`、`probe_leader_pullback_data.py`、`agent_os_acceptance*.py`、`agent_provider.py` | `keep_until_owner_review`；完成归档前不移动 |
| 一次性审计/报告生成 | `audit_legacy_routes.py`、`audit_platform_resource_optimization_completion.py`、`audit_trade_date_fields.py`、`schema_index_audit.py`、`render_platform_resource_optimization_acceptance.py`、`strategy_system_*`、`strategy_24m_*summary/plan/review`、`focus_strategy_*`、`market_state_guard_walk_forward_summary.py`、`generate_strategy_24m_optimization_report.py` | `keep_until_owner_review`；优先归档到 `scripts/archive/` 但需先更新引用 |
| Native/mobile/release 辅助 | `harden_native_release_config.py`、`native_release_check.py`、`publish_android_update.py` | 保留或标记 deprecated 需产品决策；当前不移动 |
| 安全/配置维护 | `reencrypt_settings.py`、`sync_strategy_meta_fallback.py`、`warm_elasticity_cache.py`、`qa_low_buy_persistence.py` | 保留；补 Runbook 使用条件 |
| 本地清理 | `clean_local_artifacts.sh` | 保留；必须保持 dry-run 默认，不清 `backend/data` |

## 高频入口建议

建议在 Makefile/Runbook 中保持少量稳定入口：

- 本地回归：`make qa`、`make regression`、`make frontend-next-check`。
- 发布前检查：`make prod-preflight`、`make runtime-snapshot`。
- 部署：`make deploy-cloud`、`make deploy-cloud-web`、`make deploy-cloud-verify`。
- 线上只读性能：`scripts/measure_cloud_go_rust_performance.py`，仅授权后运行。
- 分析任务：`backend/scripts/analytics_worker.py` 和 `scripts/submit_analytics_manifest_exports.py`。

## Archive 候选

以下脚本看起来更像一次性审计、报告生成或历史 spike；本批不移动，统一标记 `keep_until_owner_review`：

| 脚本 | 理由 | 建议 |
|---|---|---|
| `backend/scripts/backtest_24m_precompute_spike.py` | spike 性质，报告里明确未接生产 | `keep_until_owner_review` |
| `backend/scripts/parallel_scan_spike.py` | 并行扫描 spike，风险较高 | `keep_until_owner_review` |
| `backend/scripts/call_auction_provider_spike.py` | 集合竞价 G0 spike 当前可能仍需追溯 | `keep_until_owner_review` |
| `scripts/probe_leader_pullback_data.py` | 单策略数据探针 | `keep_until_owner_review` |
| `scripts/audit_legacy_routes.py` | 旧前端/路由审计一次性工具 | `keep_until_owner_review` |
| `scripts/audit_platform_resource_optimization_completion.py` | 平台资源优化审计工具 | `keep_until_owner_review` |
| `scripts/audit_trade_date_fields.py` | 日期字段审计工具 | `keep_until_owner_review` |
| `scripts/schema_index_audit.py` | schema/index 审计工具 | `keep_until_owner_review` |
| `scripts/strategy_system_requirement_audit.py` | 策略系统历史审计 | `keep_until_owner_review` |
| `scripts/strategy_system_promotion_plan.py` | 策略晋级计划生成 | `keep_until_owner_review` |
| `scripts/strategy_system_acceptance_report.py` | 验收报告生成 | `keep_until_owner_review` |
| `scripts/focus_strategy_*` | focus strategy 一次性矩阵/计划/审计 | `keep_until_owner_review` |
| `scripts/agent_os_acceptance*.py` | agent OS 验收工具，当前主链不明 | `keep_until_owner_review` |

## 移动前门禁

任何脚本归档或移动前必须：

1. 执行 `rg --fixed-strings "<script-path>" .github docs Makefile README.md backend frontend-next scripts`。
2. 更新所有命令示例、Runbook、CI 和测试断言。
3. 对部署/数据修复/回测脚本保留 rollback 或恢复说明。
4. 单独提交 archive 变更，不混入策略、部署或业务功能改动。

## 验收命令

```bash
find scripts backend/scripts -maxdepth 1 -type f | sort
rg -n "scripts/|backend/scripts/" .github docs Makefile README.md
test -f docs/reports/scripts-inventory-and-archive-plan-2026-06-11.md
```
