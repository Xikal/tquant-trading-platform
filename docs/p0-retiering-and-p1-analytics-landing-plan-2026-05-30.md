# 生产策略分层收口 与 Analytics 落地：完整最终方案

> 日期：2026-05-30　分支：`codex/phase4-phase5-architecture`
> 性质：**最终方案（非过渡）**，仅为待执行规格，不在本文件中改代码/部署。
> 配套：`docs/reports/full-project-latest-code-review-2026-05-30.md`（P0、P1-1、P1-3）。
> 数据源：`strategy_24m_duckdb_report.md` / `strategy-24m-backtest-2026-05-30.md`（2026-05-30 全策略 24 个月回测）。

本方案做两件最终决定，并把它们焊死成一个闭环：
1. **生产分层以 24M 证据为唯一事实源**，一次性收口到最终集合（不再“先降级观察一版”）。
2. **Analytics（DuckDB/Parquet）作为一等公民部署上线**（不保留“离线/过渡”形态），让 24M 报告成为可在服务器复现、并驱动分层门禁的权威输入。

二者闭环：**Analytics 产出 24M 报告 → 报告里的 `keep/downweight/default_off/delete_candidate` 即分层准入 → 守卫测试强制 `strategy_policy.py` 与最新报告一致**。今后策略升降级由证据自动驱动，不再靠手改常量拍脑袋。

---

# Part A：生产策略分层的最终收口

## A1. 评估口径（永久门禁规则，写入治理）

对“是否属于生产层（CORE/AUXILIARY）”给出**确定阈值**，全部读最新 24M 报告字段（成交数、PF、最大回撤、平均单笔）：

| 准入 | 阈值 |
|---|---|
| 生产可评估下限 | 成交 ≥ 50 **且** PF ≥ 1.2 **且** 最大回撤 ≥ -25% **且** 平均单笔 > 0 |
| 升 **CORE** | 同时满足：成交 ≥ 400 **且** PF ≥ 1.5 **且** 最大回撤 ≥ -20% |
| 入 **AUXILIARY** | 满足“可评估下限”但未达 CORE；若成交 < 100 标记 `low_sample_capped`（限 cap、降权，不享 CORE 全权重） |
| 落 **RESEARCH** | 未达“可评估下限”（含样本过少不可评估、PF<1.2、回撤<-25%、平均单笔≤0） |
| **FACTOR** | 仅作为加分因子（不单独成生产策略），维持现状 |

> 阈值说明：下限取“成交≥50”而非报告里的 100，是为了不误杀“低频但单笔质量高”的主线策略；但 PF/回撤/平均单笔同时把关，净亏损与巨幅回撤一律出局。

## A2. 套用 24M 证据后的**最终分层**（确定结果，不再观望）

| 策略 | 成交 | PF | 最大回撤 | 平均单笔 | 报告建议 | 现层级 | **最终层级** | 判定依据 |
|---|---:|---:|---:|---:|---|---|---|---|
| 首板回调 `first_board` | 1064 | 2.63 | -5.42% | 1.122% | keep | CORE | **CORE** | 全项达 CORE 标准 |
| 量能低吸 `volume_shrink` | 510 | 1.66 | -13.24% | 0.619% | keep | CORE | **CORE** | 成交≥400、PF≥1.5、回撤≥-20% |
| 收盘强势承接 `late_session_strong_support` | 58 | 2.24 | -7.74% | 1.347% | default_off | AUXILIARY | **AUXILIARY（low_sample_capped）** | 单笔质量高、回撤小，仅样本偏少→限 cap 降权 |
| 中军VWAP/均线回踩 `core_midcap_vwap_ma5_retrace` | 19 | 0.68 | -19.11% | -0.668% | default_off | AUXILIARY | **RESEARCH** | PF<1.2、平均单笔为负、样本不足 |
| 主线首分歧低吸 `sector_mainline_first_divergence_low_buy` | 2 | 0.00 | -5.63% | -2.835% | default_off | AUXILIARY | **RESEARCH** | 样本不可评估、负收益 |
| 主线涨停缩量回调 `mainline_limitup_shrink_retrace_reclaim` | 2 | 0.00 | -4.70% | -2.377% | default_off | AUXILIARY | **RESEARCH** | 样本不可评估、负收益 |
| 长洗N字冲高 `n_pattern_long_wash` | 1585 | 1.15 | **-51.15%** | 0.278% | default_off | **CORE** | **RESEARCH** | 大样本但 PF<1.2、回撤 -51% 远超 -25% |
| 短洗N字冲高 `n_pattern_short_wash` | 1571 | 0.72 | **-88.63%** | -0.491% | delete_candidate | **CORE** | **RESEARCH（删除候选）** | 净亏损、回撤 -88%，硬性出局 |

**最终生产集合（CORE+AUXILIARY）= 3 个**：`first_board`（CORE）、`volume_shrink`（CORE）、`late_session_strong_support`（AUXILIARY，低样本限权）。
其余原生产策略全部退出生产层；研究层/因子层维持，专属规则与样本池不删除。

> 这是“按证据该长什么样”的最终结果。生产集合从 8 收到 3，是诚实的代价：把 -88%/-51% 回撤的策略和 2-19 个样本的不可评估策略，从“生产强买”降到“研究/观察”。它们在研究面板、front_row 观察线仍可见，只是不再以生产强买误导用户。

## A3. 待执行改动点（一次性收口，确定值）

> 全部为“改成什么”的规格，不在本文件执行。

1. **`backend/app/services/low_buy/strategy_policy.py`（:14-19 等）**——直接落最终集合：
   - `CORE_STRATEGIES = {first_board, volume_shrink}`
   - `AUXILIARY_STRATEGIES = {late_session_strong_support}`
   - `RESEARCH_STRATEGIES` 增补：`core_midcap_vwap_ma5_retrace, sector_mainline_first_divergence_low_buy, mainline_limitup_shrink_retrace_reclaim, n_pattern_long_wash, n_pattern_short_wash`（并保留原有研究策略）
   - 逐一复核派生集合：`PRODUCTION_PRIORITY_STRATEGIES`、`STRONG_BUY_PAUSED_STRATEGIES`、`THREE_DAY_PROTECTION_STRATEGIES`、`MAINLINE_REQUIRED_STRATEGIES`——把已退出生产的 key 同步移除，避免悬挂引用。
   - `_TIER_WEIGHTS` 保持 CORE 1.0 / AUXILIARY 0.65；为 `low_sample_capped` 增加一个降权/封顶钩子（如 AUXILIARY 且样本<100 时权重×0.5 或 score cap≤65）。
2. **`backend/app/services/low_buy/production_scoring_config.py`**
   - `PAUSED_PRODUCTION_STRATEGIES` 不再只含 short_wash：凡不在最终生产集合的策略，其 `production_score` 一律 null（最稳的是让 `production_scoring.py` 直接判 `strategy_key not in PRODUCTION_PRIORITY_STRATEGIES → production_score=None`，而非维护第二份名单，消除两份名单漂移）。
   - 清零/置负 N 字与已退出策略在 `PRODUCTION_STRATEGY_PRIORS`、`FRONT_ROW_INTERACTION_WEIGHTS` 的正分。
   - bump `PRODUCTION_SCORING_CONFIG_VERSION`。
3. **`backend/app/services/low_buy/shared.py` PLAYBOOKS 文案**：8 条受影响策略 `subtitle` 与最终层级一致（“核心生产/高风险核心生产”→“研究验证/暂停生产”等）。
4. **元数据与前端**：`strategy_metadata_defaults.py`、`strategy_families.py`、`frontend/src/features/playbook/PlaybookPage.tsx`、`frontend/src/generated/strategyMetaFallback.ts`、`workspaceConstants` 同步层级标签。
5. **统一“分层来源”**：让 `production_scoring.py` 的生产准入直接复用 `strategy_policy.participates_in_priority_board()`，**只留一处真源**（消除 `strategy_policy` 与 `production_scoring_config` 两份名单各说各话的隐患——这正是本次 P0 的成因）。

## A4. 守卫测试（把证据门禁焊死，永久防漂移）

- `test_core_aux_strategies_match_latest_24m_report`：读最新 `strategy_24m_duckdb_report.json` 的 `strategy_adjustment_recommendations`，断言**每个** CORE/AUXILIARY 策略的 `action ∈ {keep, downweight}`；任何 `default_off/delete_candidate` 出现在生产层即失败。
- `test_production_score_null_for_non_production`：非生产集合策略 `production_score is None`。
- `test_baseline_board_excludes_non_production_strong_buy`：构造含已退出策略命中的 rows，断言 baseline 优先榜不输出其 `buy_now/soft_buy_now`。
- `test_low_sample_strategy_is_capped`：`late_session_strong_support` 走 AUXILIARY 但权重/cap 被限制。
- 同步更新会因改动变红的既有用例：`test_low_buy_strategy_replacement.py`、`test_n_pattern_observe_confirmed.py`、`test_low_buy_production_scoring.py`、`test_low_buy_strategy_lanes.py`、`test_main_force_model_*`（凡断言 N 字为 CORE 处）。

## A5. 一次性发布与验证（无观望阶段）

- 改动集中在分层常量 + 配置 + 文案 + 前端标签，**无 schema 变更、无数据迁移**，一次发布到位。
- 发布前：`pytest backend/tests -q` 全绿（含 A4 守卫）、`npm run api:check`、`scripts/qa_smoke.sh`。
- 发布后（线上）：拉 `/api/screeners/low-buy/priority-board?strategy_variant=baseline`，断言结果不含已退出策略的生产强买；研究面板仍可见这些策略（确认是重分层非删除）。

## A6. 回滚

- 回滚 = 还原 `strategy_policy.py` + `production_scoring_config.py`（+ 文案/前端标签）并重启；无迁移、无数据风险。

## A7. 永久治理（替代“临时观察”，让升降级自动化）

- **唯一升降级路径 = A1 门禁**：策略只有在最新 24M 报告里达标才进/留生产层；达不到自动落 RESEARCH。
- 退出生产的策略不删除（保留规则/样本池/研究回测），**当其样本累积且重新达标时，由 A4 守卫驱动重新纳入生产**——这就是它的“回来的路”，无需任何一次性人工过渡。

---

# Part B：Analytics（DuckDB/Parquet）作为一等公民上线（最终形态）

> 决定：**部署上线，不保留离线形态。** 理由：Part A 的分层门禁要求 24M 报告“在服务器可复现、可按需重跑、可被守卫测试读取”。离线形态会让分层准入不可复现，等于把生产分层建在本地一次性产物上——不可接受。

## B1. 镜像（复用现有 build-arg 范式，不污染默认镜像）
- `Dockerfile` 已有 `ARG INSTALL_RL_EXTRAS/WITH_RL`（:46-49）同款模式。**规格**：新增 `ARG INSTALL_ANALYTICS=0`，为 1 时 `pip install -r backend/requirements-analytics.txt`（`duckdb`、`pyarrow`）。
- 产出独立镜像 tag `tquant-analytics:mysql`；web/runtime/backtest 默认镜像体积不变。

## B2. compose 新增 `analytics-worker`（照搬 worker 范式，见 compose:144-265）
- `build.args: INSTALL_ANALYTICS=1`，`image: tquant-analytics:mysql`
- `command: ["python", "backend/scripts/analytics_worker.py", "--poll-interval-seconds", "2"]`（入口已存在，CLI：`--queue/--worker-id/--poll-interval-seconds/--once`，用 `analytics_task_registry()`）
- `depends_on: migration(completed) + mysql(healthy)`；`restart: unless-stopped`
- env 复用 worker 同款（DATABASE_URL/密钥/STRUCTURED_LOGS…）+ 新增 `TQUANT_ANALYTICS_ENABLED=true`、`TQUANT_ANALYTICS_ROOT=/app/backend/data/analytics`、`TQUANT_DUCKDB_THREADS=4`
- 挂 `app_runtime_data:/app/backend/data`（与 worker 共享，落 parquet/manifest/report）
- `deploy.resources.limits`（cpus/mem）限制 DuckDB 多线程吃满；healthcheck：`python -c "import duckdb,pyarrow"` + DB ping
- **队列隔离已天然成立**：runtime-worker 只 claim `RUNTIME_WORKER_TASK_TYPES`（`runtime_worker.py:64`），不会误领 analytics 任务；analytics-worker 按 analytics task_type claim，互不抢占。

## B3. 编排：让 24M 报告成为“按需可复现 + 定时刷新”的权威产物
- **按需**：`POST /api/runtime-tasks {task_type:"backtest_all_strategies_24m"}`（admin）→ 数据不足自动 enqueue `data_backfill_24m`（`quality.py:152-159`）→ analytics-worker 消费 → 跑全策略回测 → DuckDB 出 `strategy_24m_duckdb_report.{md,json}`。
- **定时**：在 `background_jobs.py` 增一个低频 loop（如每周一次）`enqueue` `strategy_24m_duckdb_report`，保证报告随数据滚动更新，分层门禁始终有最新证据。
- **完整性硬门禁保留**：`check_daily_bars_24m_quality` 数据不足返回 `blocked_by_data`、绝不静默续跑（已实现，`analytics_handlers.py:122-127`）。
- **orphan 任务从根上消失**：因为 analytics-worker 已常驻消费，B 计划里那套“离线门禁/回收”不再需要——这是“上线”相对“离线”的额外收益。

## B4. 报告口径修复（P1-3，必须随上线一起做）
- `backend/app/services/analytics/report_queries.py:115` 表头“总收益”→“每日信号等权复利收益”，并新增 `真实组合max5 / 真实组合max10` 列（复用 `low_buy_market_backtest_reporting.py` 的 `portfolio_backtest_metrics`，即 max5/max10：同策略单日≤2、同板块≤2、弱市≤40%、退潮不开仓、同票不重复买、资金占用）。
- 验收：DuckDB 报告与 `strategy-24m-backtest-2026-05-30.md` 同策略数值一致；报告内无裸“总收益”。
- 这条同时保证 Part A 的门禁读到的是“真实组合口径”，而不是被夸大的等权复利。

## B5. 就绪/可观测/运维
- `main.py /readyz`（:297-323）新增 analytics 维度（启用时检查 `import duckdb,pyarrow` + analytics_root 可写）；analytics 任务 queued/running/failed 经 `/metrics` 暴露（复用既有 phase4 task 指标）。
- `PRODUCTION_RUNBOOK.md` 增章节：analytics-worker 启动/补跑（`--once`）、查 artifact 与 Manifest、`data_backfill_24m` 卡住排查、`INSTALL_ANALYTICS` 构建说明、回滚（从 compose 摘除 analytics-worker 不影响主链路）。

## B6. 验收
- 云上 `docker compose ps` 含 analytics-worker 且 healthy；镜像内 `import duckdb,pyarrow` 成功；默认 web/worker 镜像体积不变。
- `POST backtest_all_strategies_24m` 全链路产出报告与 artifact；数据不足时自动补数后重跑，无永久 queued。
- Part A 守卫测试能读到服务器侧最新报告并通过。

---

# Part C：A 与 B 的闭环（这才是“完整方案”的核心）

```
analytics-worker 定时/按需跑 24M 全策略回测（真实组合 max5/max10 口径）
        │
        ▼
strategy_24m_duckdb_report.json: 每策略 keep/downweight/default_off/delete_candidate
        │
        ▼
A1 门禁规则（成交/PF/回撤/平均单笔阈值）= 生产分层准入
        │
        ▼
strategy_policy.py 生产集合（CORE/AUXILIARY） ── 守卫测试强制与最新报告一致
        │
        ▼
baseline 优先榜 / production_score / 模拟盘自动交易 只用通过门禁的策略
```

- **单一事实源**：24M 报告。分层不再有 `strategy_policy` 与 `production_scoring_config` 两份名单互相打架（A3.5 合并为一处真源）。
- **自动纠偏**：策略表现退化 → 下次 24M 报告 `default_off/delete_candidate` → 守卫测试红 → 强制移出生产；表现达标 → 自动可回生产。无人工过渡步骤。
- **当前即时结果**：本轮 24M 证据下，生产集合 = `first_board` + `volume_shrink` + `late_session_strong_support(限权)`；N 字与 3 个不可评估主线策略退出生产、保留研究。

---

## 交付清单（最终方案落地需产出）
- 后端：`strategy_policy.py`、`production_scoring*.py`、`shared.py`、`report_queries.py`、`background_jobs.py`(周报 loop)、`main.py`(readyz)、`Dockerfile`(build-arg)、`docker-compose.mysql.yml`(analytics-worker)。
- 测试：A4 守卫 + 既有用例更新 + analytics 上线冒烟。
- 文档：`PRODUCTION_RUNBOOK.md`(analytics 运维)、`ARCHITECTURE.md`/PLAYBOOKS 文案、本方案归档。
- 一次发布：分层收口 + analytics 上线 + 报告口径修复 同窗口交付，发布后按 A5/B6 验收。
