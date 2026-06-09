# 停用功能 · 资源影响清单（43.143.243.97 · 2026-06-09）

> 性质：**方案/建议，不代执行、不部署、不切流、不改生产代码**。命令需运维在服务器执行。
> 依据：线上只读巡检（4C / 3723 MiB / Swap 1736/1987 重度使用 / CPU load 0.5）+ 本仓库 feature flag、background jobs、compose 盘点。
> 硬边界：不改 `strategy_policy.py`/生产排序/`production_score`；不停核心数据刷新发布；不动 MySQL 主写与数据；strategy_engine 仍 shadow-only。

---

## 0. 核心结论（必须先读）

**"停用低价值业务功能"对这台机器降资源几乎无效——它们大多已被门控关闭、根本没在跑。** 内存被**常驻 Python 进程基线**吃掉（每个 worker 容器都加载整个 app ≈ 470–530M），与"开了哪些业务开关"无关。

**真正"停了能显著省内存"的是停掉冗余进程/容器，不是关业务功能。** 且 **CPU 是闲的（load 0.5/4 核），为省 CPU 关功能没意义——瓶颈是内存与 Swap。**

按本清单停掉冗余进程可释放 **~700M–1G**，让机器**脱离 Swap**。

---

## 1. ✅ 停了能显著省内存（按收益排序）

| 优先级 | 停用项 | 释放 | 性质 | 改法 | 风险/前提 | 回滚 |
|---|---|---|---|---|---|---|
| 1 | **独立 `runtime-scheduler` 进程**：把调度 loop 并入 `runtime-worker`，停掉独立 scheduler 容器 | **~472M**（单项最大） | 进程合并 | `runtime-worker` 容器开启调度（其 env 启用 background 调度角色），`docker compose stop runtime-scheduler` | 中：长任务可能延后定时入队 → 少用户可接受；**先观察一个交易日**确认 quote/物化/收盘发布按时 | 重起独立 `runtime-scheduler` 容器 |
| 2 | **第 2 个 app worker**：`APP_WORKERS` 2 → 1 | **~210M** | 进程数 | `app` 服务 env `APP_WORKERS=1` 后重建容器 | 低：少用户/CPU 闲，1 worker 足够；**核对 SEC2 限流口径**（按真实并发推导） | 改回 2 |
| 3 | **`backtest-worker` 常驻 → 按需** | ~43M + Python 基线 | 重任务功能 | compose `profiles: [heavy]` 默认不启动；跑权威回测时 `--profile heavy up`，完 `down` | 低：回测前需拉起（写 runbook） | 改回 `restart: unless-stopped` 常驻 |
| 4 | **`analytics-worker`（24M DuckDB 报告）常驻 → 按需/停用** | ~19M 常驻 + 重 `duckdb/pyarrow` import 占用 | 分析层功能 | 同上 profile 化；若**极少在服务器跑 24M 报告**，可直接 `stop` | 低：跑 24M 报告/导出前拉起 | 拉起 analytics-worker |
| 5 | **分离验证栈**（`tquant-frontend-web`/`tquant-backend-api`/`tquant-separated-gateway`，公网未代理） | ~33M + 容器开销 | 冗余栈 | `docker compose -f docker-compose.separated.yml down` | 零：本就不对外服务（nginx → 18090） | `-f docker-compose.separated.yml up -d` |

**合计**：1+2+3+4+5 ≈ **释放 ~700M–1G** → 内存用量 3184M → ~2400M、**Swap 1.7G 排空到接近 0**。

---

## 2. ❌ 停了**不省**（已门控关闭，不在跑）

> 这些是审计里的"研究/低价值"功能，**默认已关、停用=释放 0**。无需再动，动了还可能误伤。

| 类别 | 功能 | 证据（默认值） |
|---|---|---|
| 研究后台任务 | `strategy_validation_monthly`、`backtest_research_worker`、`low_buy_strategy_governance`、`strategy_self_evolution` | `tquant_research_jobs_enabled=False`（`config.py:95`） |
| ML 任务 | `ml_signal_incremental_train`、`ml_feature_drift_monitor` | `tquant_ml_jobs_enabled=False`（`config.py:96`） |
| 因子挖掘 | `factor_mining_monthly` | `tquant_factor_jobs_enabled=False`（`config.py:97`） |
| 观察/复盘套件 | `trading_experience_suite`、`trade_review`、`vp_position_tags`、`relative_strength_board`、`holding_discipline`、`limit_up_followthrough`、`t_trade_discipline` | 7 个 flag 全 `False` |
| 关键位引擎 | AKeyLevel | `a_key_level_engine_enabled=False` |
| Agent 集成 | MCP/Hermes/通知 | 默认传输 none |
| 实验策略带 | leader pullback band | `strategy_leader_pullback_band_enabled=False` |

> 结论：平台已把研究/低价值功能门控干净，**不是资源黑洞**；停它们既不省内存，也无意义。

---

## 3. ⚠️ 能省 CPU/唤醒但**不省内存**（本机优先级低）

| 动作 | 效果 | 为何对本机优先级低 |
|---|---|---|
| `RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED=true` | 调度/worker 唤醒频率↓ → CPU 占空比↓ | **CPU 本就闲**（load 0.5）；仅减少 Swap 抖动时的额外开销 |
| 盘后降低 `quote_cache/breadth/hourly` loop 频率（按交易日历） | 盘后 CPU/外网拉取↓ | 同上；不得影响盘中发布 |

---

## 4. 不能停（硬边界，停了破生产）

`low_buy_full_scan`、`market_quote_cache_refresh`、`market_hourly_all_a_snapshot`、`low_buy_materialization_refresh`、`daily_bar_refresh`、`latest_data_watchdog`、`watchlist_signals`、`market_regime_prewarm`、`market_midday_review`、`market_close_review`、`paper_perf_archive`、`paper_ledger_reconcile_preview_daily`、核心 `runtime-worker`（数据刷新）、`mysql`、`redis`、`go-bff-gateway`、`go-market-read-service`、`app`、nginx/HTTPS、OpenAPI 契约。

---

## 5. 量化目标与验收

| 指标 | 现状 | 目标 |
|---|---|---|
| 内存已用 | 3184 MiB | ~2400 MiB |
| **Swap 已用** | **1736 MiB** | **< 300 MiB（接近 0）** |
| 空闲内存 | 539 MiB | ~1200 MiB |
| 常驻容器 | 主栈 10 + 分离 3 | 7–8 |

**验收**：
- `free -m`：Swap < 300M、空闲 > 1G。
- `docker stats --no-stream`：常驻容器内存和较 M0 显著下降。
- `curl -fsS https://weisilianghua.cloud/readyz`：`database/frontend_dist/frontend_next_dist/analytics_dependencies` 全 true。
- **生产不变**：`/monitor→/playbook→/backtest→/paper→/settings` 可用；priority board 排序/`production_score`/低吸语义/交易日发布不变；盘中刷新与收盘发布按时；按需拉起的 analytics/backtest 能正常完成 24M 报告/权威回测。

---

## 6. 风险与回滚（每项独立可回退）

| 停用项 | 回滚 | 生产保护 |
|---|---|---|
| 合并 scheduler | 重起独立 scheduler 容器 | **先观察一个交易日**，定时入队/发布异常立即回滚 |
| APP_WORKERS=1 | 改回 2 | 少用户足够；限流口径核对 |
| backtest/analytics 按需 | 改回常驻 | **不改任务逻辑/回测口径**，仅启动方式 |
| 停分离栈 | `compose -f separated up -d` | 本不对外服务 |
| compact/降频 | 置 False/改回频率 | 仅盘后，盘中不动 |

---

## 7. 一句话总结

**真正能显著降内存的"停用"是停冗余进程，不是关业务功能**：① 合并/停独立 scheduler（−472M）→ ② `APP_WORKERS` 2→1（−210M）→ ③ analytics/backtest worker 改按需（−62M+）→ ④ 停分离验证栈（−33M）。**释放 ~700M–1G，脱离 Swap。** 审计里那些"低价值"业务功能（研究/ML/因子/观察套件/AKeyLevel/agent）**早已门控关闭，停了一分钱内存都省不下来**，不必再动。

---

## 交付说明（合规）
- 未修改任何代码、未部署、未切流、未删旧前端、未改生产策略/排序/`production_score`。
- 本报告为服务器 ops/配置建议；命令需运维在服务器执行，本轮仅出方案。
- 配套：`cloud-server-optimization-plan-2026-06-09.md`（含磁盘清理 `docker builder prune -af` −11.8G、swappiness、mem_limit 等非"停用功能"类优化）。
