# 平台瘦身执行基线（2026-06-09）

## 范围与边界

- 来源计划：`docs/platform-slimming-optimization-execution-plan-2026-06-09.md`
- 来源审计：`docs/reports/platform-slimming-audit-2026-06-09.md`
- 本轮范围：Phase 0-3，本地瘦身落地与报告，不部署、不切流、不删除生产核心能力。
- P0 保护：`low_buy` 生产链路、market、paper、backtest、tasks、BFF、`monitor_snapshot_service`、RuntimeTaskQueue、`strategy_policy.py`、`production_score`、priority board 排序和口径均不触碰。

## Git 基线

开始前执行：

```text
git status --short
?? docs/platform-slimming-optimization-execution-plan-2026-06-09.md
?? docs/reports/platform-slimming-audit-2026-06-09.md
```

跟踪文件数：

```text
git ls-files | wc -l
3000
```

## 本地大目录大小

```text
du -sh docs/reports backend/data backend/.venv rust/tquant-rs/target frontend/node_modules frontend-next/node_modules node_modules .mysql-local .understand-anything 2>/dev/null || true
 53M    docs/reports
2.4G    backend/data
1.3G    backend/.venv
772M    rust/tquant-rs/target
414M    frontend/node_modules
243M    frontend-next/node_modules
4.0K    node_modules
851M    .mysql-local
 42M    .understand-anything
```

结论：

- 本地占盘大头为 `backend/data`、虚拟环境、Rust target、node_modules、`.mysql-local`，多数已被 `.gitignore` 排除，属于开发机/运行时空间。
- 仓库瘦身主目标是 `docs/reports` 中已跟踪的大型 JSON、截图和一次性机器产物。

## docs/reports 跟踪大文件 TOP40

命令：

```text
git ls-files -z docs/reports | xargs -0 du -k 2>/dev/null | sort -nr | head -40
```

结果：

| KiB | 路径 |
|---:|---|
| 12972 | `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` |
| 1444 | `docs/reports/strategy-24m-backtest-2026-05-30.json` |
| 1352 | `docs/reports/strategy-24m-optimization-report-2026-05-28.json` |
| 888 | `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json` |
| 820 | `docs/reports/strategy-24m-backtest-2026-05-28.json` |
| 648 | `docs/reports/frontend-next-visual-review-2026-06-05/review-paper-web.png` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2026-02-02_2026-04-21.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2026-01-05_2026-03-24.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2025-10-09_2025-12-24.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2025-09-01_2025-11-21.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2025-08-01_2025-10-24.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2026-02-02_2026-04-21.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2026-01-05_2026-03-24.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2025-10-09_2025-12-24.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2025-09-01_2025-11-21.json` |
| 612 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2025-08-01_2025-10-24.json` |
| 608 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2025-12-01_2026-02-12.json` |
| 608 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/current/low_buy_market_backtest_24m_confirmed_default_exit_no_guard_no_prefilter_override_2025-11-03_2026-01-23.json` |
| 608 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2025-12-01_2026-02-12.json` |
| 608 | `docs/reports/market-state-guard-walk-forward-2026-05-28/windows/block_retreat/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_no_prefilter_override_2025-11-03_2026-01-23.json` |
| 456 | `docs/reports/frontend-next-visual-review-2026-06-05/review-monitor-action-web.png` |
| 408 | `docs/reports/daily-history-backfill-runs/all-stock-full-2026-05-28/manifest.json` |
| 360 | `docs/reports/frontend-next-density-review-2026-06-06/next-paper-layout-tight-2026-06-07.png` |
| 344 | `docs/reports/frontend-next-visual-review-2026-06-05/review-backtest-web.png` |
| 332 | `docs/reports/frontend-next-visual-review-2026-06-05/review-monitor-market-web.png` |
| 332 | `docs/reports/frontend-next-density-review-2026-06-06/next-paper-console-2026-06-07.png` |
| 316 | `docs/reports/frontend-next-visual-consistency-2026-06-07/strategy-tracking-1440x900.png` |
| 312 | `docs/reports/frontend-next-visual-review-2026-06-05/review-playbook-web.png` |
| 304 | `docs/reports/frontend-next-visual-review-2026-06-05/review-analysis-web.png` |
| 300 | `docs/reports/main-force-related-strategy-backtest-2026-05-28/low_buy_market_backtest_24m_all_states_default_exit_no_guard_no_prefilter_override_2024-05-28_2026-04-21.json` |
| 296 | `docs/reports/frontend-next-screenshots-2026-06-05/strategy-tracking-web.png` |
| 272 | `docs/reports/frontend-next-density-review-2026-06-06/next-settings-command-2026-06-07.png` |
| 264 | `docs/reports/frontend-next-density-review-2026-06-06/next-data-terminal-2026-06-07.png` |
| 260 | `docs/reports/frontend-next-visual-consistency-2026-06-07/settings-1440x900.png` |
| 260 | `docs/reports/frontend-next-visual-consistency-2026-06-07/paper-1440x900.png` |
| 260 | `docs/reports/frontend-next-density-review-2026-06-06/next-login-nerv-register-2026-06-07.png` |
| 256 | `docs/reports/frontend-next-screenshots-2026-06-05/settings-web.png` |
| 252 | `docs/reports/frontend-next-screenshots-2026-06-05/legacy-monitor-action-web.png` |
| 252 | `docs/reports/frontend-next-screenshots-2026-06-05/1280x800-strategy-tracking-web.png` |
| 244 | `docs/reports/frontend-next-visual-consistency-2026-06-07/paper-1280x800.png` |

## 归档目标目录状态

检查：

```text
git check-ignore -v backend/data/reports/archived/2026-06-09/example.json
.gitignore:21:data/ backend/data/reports/archived/2026-06-09/example.json
```

结论：`backend/data/reports/archived/2026-06-09/` 当前被 `.gitignore` 覆盖，可作为本机恢复用 artifact 存储；仓库内保留 manifest、摘要和删除记录，不把大产物重新纳入跟踪。

