# 维斯量化交易平台 全方位代码审查报告

> 审查日期：2026-05-30
> 项目：tquant-trading-platform（`/Users/j/Documents/gupiao`）
> 分支：`codex/phase4-phase5-architecture`　最新提交：`576ab02d docs: record cloud deployment verification`
> 关键变更提交：`e9dae628 feat: add front-row strategy lanes and analytics reporting`
> 版本：`VERSION.json` = `0.9.0` / `release_stage: stabilization`（即“稳定化阶段”，非正式 1.0）
> 线上：`http://43.143.243.97:18090`（裸 IP + HTTP，无 TLS）
> 审查方式：只读源码逐项核验 + 9 份指定文档 + 回测报告 + 云性能报告；**未运行测试、未访问线上实例**（见第 7 节覆盖说明）

---

## 1. 总结结论

| 决策项 | 结论 | 一句话理由 |
|---|---|---|
| 是否建议继续保持线上运行 | **可以，但有条件** | 平台只做模拟盘/辅助，不下真单；但裸 IP+HTTP 不应承载真实账号与数据，需切到域名+HTTPS |
| 是否建议进入小流量生产观察 | **否** | front_row_weighted 自身 readiness 明确未通过（OOS/walk-forward/分钟逐笔不足），且生产基准榜被 N 字策略污染（P0） |
| 是否建议替换生产排序 | **否（且当前代码确实没有替换，正确）** | `production_sort_replaced=false` 全程成立，front_row 仅 Shadow；替换前必须先修 P0 并通过 OOS |
| 是否存在必须立即修复的问题 | **是** | 1 个 P0（N 字策略仍是 CORE 生产）、4 个 P1（分析层未部署、线上 HTTP cookie、DuckDB 报告口径误导、long_wash 未暂停） |

**核心判断：本次 `front-row strategy lanes + analytics` 的“边界设计”做得相当严谨**——production_score 只允许 `buy_now/soft_buy_now`、`near_entry` 恒为 null、front_row_only 强制 watch-only、max5/max10 真实组合约束齐全、新功能有测试覆盖、前端零 `useState/useReducer`、契约类型已接入回测 wrapper。**问题集中在两个层面**：

1. **新旧系统的“事实源不一致”**：24 个月回测（2026-05-30）给出 `n_pattern_short_wash=delete_candidate(-88%)`、`n_pattern_long_wash=default_off(-51%)`，但 `strategy_policy.py` 仍把这两个策略钉死为 **CORE 生产**，新建的前排 Shadow 暂停清单也只暂停了其中一个。**24 个月证据没有回写到生产分层**。
2. **新能力“写完但没接到线上”**：DuckDB/Parquet 分析层、analytics worker 完整实现且有测试，但**没进 compose、依赖没进镜像**，线上根本跑不起来；DuckDB 报告还用了被废弃的“总收益”口径。

**最优先：先修 P0（策略分层与 24M 证据对齐）→ 再决定 analytics 是否真的要上线（要上就补 compose+镜像，不上就明确标注为离线研究工具）→ 线上切 HTTPS。**

---

## 2. 严重问题清单

### P0（必须立即修复，修复前不建议进入任何“小流量/生产化”讨论）

#### P0-1　亏损/删除候选的 N 字策略仍被列为 CORE 生产策略，进入生产基准优先榜
- **影响范围**：低吸生产基准榜（线上用户实际看到的“原低吸策略”榜）、买点信号 `buy_now/soft_buy_now` 生成、模拟盘自动交易候选。
- **证据**：
  - `backend/app/services/low_buy/strategy_policy.py:14-19` —— `CORE_STRATEGIES` 同时包含 `n_pattern_long_wash`、`n_pattern_short_wash`；`get_tier_weight` 给 CORE 权重 1.0，`strong_buy_paused` 只暂停 RESEARCH/FACTOR，**CORE 可正常产出 buy_now/soft_buy_now**。
  - `docs/reports/strategy_24m_duckdb_report.md:38-39` —— `长洗N字冲高 1613/1585 -8.94% 回撤 -51.15% PF1.15 → default_off`；`短洗N字冲高 1597/1571 -87.07% 回撤 -88.63% PF0.72 → delete_candidate`。
  - `docs/reports/strategy-24m-backtest-2026-05-30.md`（同一回测）样本量证明它们**频繁产生可成交信号**（各 ~1.6 万样本、~1.57 万成交）。
  - `backend/app/runtime/background_jobs.py:74-77` —— 非 SQLite（即线上 MySQL）`_background_low_buy_strategies()` 返回 `list(PLAYBOOKS.keys())`，N 字策略会被全量扫描物化进榜。
- **风险说明**：平台核心价值是信号质量。把一个 PF0.72、24 个月口径回撤 -88% 且被自家报告判为 `delete_candidate` 的策略当作“核心生产”，会直接误导用户买入，并污染生产收益统计与模拟盘自动交易。这正是审查要求里“默认关闭/降权/删除候选策略是否被错误用于生产买入”的反例。
- **修复建议**：
  1. 用 24M 证据回写分层：将 `n_pattern_short_wash` 移出 CORE（建议 RESEARCH 或直接删除候选），`n_pattern_long_wash` 降为 AUXILIARY 并加回撤 cap，或移出生产；
  2. `shared.py` PLAYBOOKS 文案同步（当前仍写“核心生产策略/高风险核心生产策略”，与报告矛盾）；
  3. 在 `strategy_policy.py` 增加“分层必须引用最近一次 24M 报告结论”的单测，防止再次漂移。
- **建议验证方式**：
  - `pytest backend/tests/test_low_buy_*` + 新增“CORE 策略必须在最近 24M 报告中 PF≥1.2 且回撤优于阈值”的断言；
  - 线上拉 `/api/screeners/low-buy/priority-board?strategy_variant=baseline`，确认结果不含 `n_pattern_short_wash` 的 `buy_now/soft_buy_now`。
- **需进一步验证**：`strategy_auto_governance.py:129-156` 的健康度自动暂停**可能**在 MySQL 线上把近期表现差的 N 字暂停掉，但它基于“近期实盘快照”而非 24M 证据、且 SQLite 下不运行（`background_jobs.py:218-219` 直接 return）。需确认线上当前是否真的已暂停，不能默认它兜住了 P0。

---

### P1（高优先，影响“可信度/线上安全/可复现”，应在本周处理）

#### P1-1　DuckDB/Parquet 分析层与 analytics worker“写完但未接入线上”
- **影响范围**：24 个月 DuckDB 报告、数据补齐、数据质量门禁、策略调整建议链路在生产环境**完全不可用**。
- **证据**：
  - 模块与脚本均已实现：`backend/app/services/analytics/{config,duckdb_repository,exporters,manifest,quality,report_queries,schemas}.py`、`backend/app/services/tasks/analytics_handlers.py`、`backend/requirements-analytics.txt`（`duckdb`、`pyarrow`）。
  - **未进部署**：`grep analytics docker-compose.mysql.yml Dockerfile` → 无命中；`duckdb/pyarrow` 不在 `backend/requirements.txt`、`Dockerfile`、compose 中（仅在独立的 `requirements-analytics.txt`）。
  - **无常驻消费者**：compose 只有 `runtime-worker`（`app.workers.runtime_worker`，纯 `RuntimeTaskQueue.claim_next`）与 `backtest-worker`；`analytics_task_registry()`（`registry.py:28-33`）只在 analytics worker 进程构建，compose 没有这个进程。
  - `check_daily_bars_24m_quality(create_backfill_task=True)` 会把 `data_backfill_24m` enqueue 进队列（`quality.py:152-159`），但线上没有任何 worker 注册了该 handler → **任务永久 queued**。
  - `PRODUCTION_RUNBOOK.md` 全文无 analytics/duckdb 字样。
- **风险说明**：`docs/reports/strategy_24m_duckdb_report.md` 是**本地 dev 产物**，不能在云上复现；任何依赖“先补数据再回测”的编排在云上会卡死；给人“24M DuckDB 能力已上线”的错觉。
- **修复建议**：二选一并明确写进 runbook：
  - **A. 真上线**：新增 `analytics-worker` compose 服务（独立镜像或 build-arg 装 `requirements-analytics.txt`），队列 `analytics`，并在 runbook 写启动/补跑/排错；
  - **B. 明确离线**：在文档与 UI 标注“DuckDB/24M 报告为离线研究工具，不在云上运行”，并禁止线上 enqueue analytics 任务（或让 runtime-worker 对未知 analytics 任务直接 fail-fast 而非永久 queued）。
- **建议验证方式**：云上 `POST /api/runtime-tasks {task_type:"strategy_24m_duckdb_report"}` 后观察是否有 worker 认领；`docker compose ... ps` 是否存在 analytics 进程；镜像内 `python -c "import duckdb,pyarrow"` 是否成功。

#### P1-2　线上为裸 IP + HTTP，承载 httpOnly 会话 cookie 即明文传输
- **影响范围**：所有登录用户的会话安全。
- **证据**：线上 `http://43.143.243.97:18090`；`auth.py:194-210` 用 httpOnly cookie 下发会话；`security_config.py:14-19,32-37` 在“production-like（cors 非 localhost 或 env=cloud）”下强制 `AUTH_COOKIE_SECURE=true`，**唯一例外是 `AUTH_ALLOW_INSECURE_HTTP_COOKIE=true`**。要让 cookie 在 HTTP 下工作，线上必然打开了该不安全开关（或 secure=false）。`PRODUCTION_RUNBOOK.md:441-472` 提供了 nginx+Let's Encrypt 的 HTTPS 路径，但**需要域名**，裸 IP 无法签发证书。
- **风险说明**：公网 IP 上明文 HTTP 传输会话 cookie → 中间人/同网段嗅探可劫持会话。`.env.docker.example` 默认是安全的，问题只发生在“为了让裸 IP 跑起来而手动放开”的线上实例。
- **修复建议**：为线上分配域名并启用 `deploy_cloud_server.sh` 的 HTTPS（`AUTO_CONFIGURE_HTTPS=1 HTTPS_REQUIRED=1`）；在拿到 HTTPS 前，线上仅用于无真实数据的内部演示，禁止注册真实用户/导入真实持仓。
- **建议验证方式**：`curl -I https://<domain>` 返回证书有效；确认线上 env `AUTH_COOKIE_SECURE=true`、`AUTH_ALLOW_INSECURE_HTTP_COOKIE` 未开。

#### P1-3　DuckDB 24M 报告使用被废弃的“总收益”口径，且省略真实组合列，存在误导
- **影响范围**：阅读 `strategy_24m_duckdb_report.md` 的决策者。
- **证据**：
  - `docs/reports/strategy_24m_duckdb_report.md:26-30` 表头为 `总收益`，首板回调显示 `362.13%`，**无“每日信号等权复利收益”标注、无 max5/max10 真实组合列**。
  - 同口径在权威 Python 报告里被正确拆分：`docs/reports/strategy-24m-backtest-2026-05-30.md:283-284` —— 首板回调“每日信号等权复利收益 362.13%”但“真实组合 max5 62.31% / max10 28.22%”。两者差距巨大。
  - 生成代码 `backend/app/services/analytics/report_queries.py:115` 表头写死 `总收益`。
- **风险说明**：这正是审查明确警告的“每日信号等权复利收益被当作真实组合收益展示”。362% vs 真实 28–62% 的量级差会严重误导。
- **修复建议**：`report_queries.py` 表头改为“每日信号等权复利收益”，并新增 `真实组合max5/max10` 列（直接复用 Python 报告的 `portfolio_backtests`）；两份报告口径统一。
- **建议验证方式**：重生成后对比两份报告同策略数值一致；grep 报告无裸“总收益”。

#### P1-4　`n_pattern_long_wash` 未纳入前排 Shadow 暂停清单，仍获正向生产先验
- **影响范围**：front_row_weighted Shadow production_score（未来若据此放量则放大风险）。
- **证据**：`production_scoring_config.py:137-138` `PAUSED_PRODUCTION_STRATEGIES = {"n_pattern_short_wash"}`（只暂停短洗）；同文件 `n_pattern_long_wash` 生产先验 `+3.0`（`:42`）、交互 `+4.0`（`:99`）。而 24M 报告 long_wash 为 `default_off(-51%)`。
- **风险说明**：与 P0 同源——长洗 N 字在两套系统里都没有被按证据降级；Shadow 层甚至给它正分。
- **修复建议**：把 `n_pattern_long_wash` 加入 `PAUSED_PRODUCTION_STRATEGIES`（或先验置负 + cap），与 24M 结论一致。
- **建议验证方式**：`pytest backend/tests/test_low_buy_production_scoring.py` 增加“default_off 策略 production_score 必须为 null 或 ≤cap”的断言。

---

### P2（中优先，影响工程质量门禁与长期可维护性）

#### P2-1　CI 只跑 pytest，未接入契约检查与前端检查 → 漂移不可见
- **证据**：`.github/workflows/ci.yml` 仅 `pytest backend/tests`（:39-42）；无 `npm run api:check`、`typecheck`、`vitest`。而 `frontend/package.json:17-19` 已有 `api:export/api:generate/api:check`，DuckDB 方案 §7.7 明确要求“OpenAPI 变了但生成类型没更新，CI 应失败”。
- **风险**：`docs/contracts/openapi.json`（949KB）与 `frontend/src/generated/api-types.ts`（741KB）会静默过期，contract-first 形同虚设；前端回归无门禁。
- **修复建议**：CI 增加 `cd frontend && npm ci && npm run api:check && npm run test -- --run`；`api:check` 产生 diff 即失败。
- **验证**：故意改一个后端 `response_model` 字段，CI 应红。

#### P2-2　`widen strategy tracking snapshot payload` 迁移为 MySQL `TEXT→LONGTEXT`，大表 ALTER 锁风险 + 历史截断隐患
- **证据**：`backend/alembic/versions/20260529_0002_widen_strategy_tracking_snapshot_payload.py:28-39` `alter_column(existing_type=Text, type_=mysql.LONGTEXT...)`；对应修复提交 `ac63c77b fix: widen ... payload`。
- **风险**：① MySQL 对 `strategy_tracking_snapshots`（快照表，可能很大）做 TEXT→LONGTEXT 需重建表，部署期可能锁表/超时；② 触发“widen”说明此前 payload 曾超过 TEXT 64KB 上限 —— 旧快照可能被截断/写入报错（数据完整性历史问题）。
- **修复建议**：部署前评估该表行数与大小，必要时用 `pt-online-schema-change`/低峰执行；排查 widen 之前是否存在被截断的快照并补写；后续快照 payload 应裁剪/分表，避免单行膨胀。
- **验证**：迁移前 `SELECT COUNT(*),AVG(LENGTH(payload)) FROM strategy_tracking_snapshots`；迁移在 staging 计时。

#### P2-3　仓库膨胀：单个 13MB 回测 JSON 及多份 MB 级产物入库
- **证据**：`git ls-files | du -k` Top：`docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` **≈12.9MB**、`strategy-24m-backtest-2026-05-30.json` 1.4MB、`strategy-24m-optimization-report-2026-05-28.json` 1.3MB、`docs/contracts/openapi.json` 928KB、`frontend/src/generated/api-types.ts` 724KB 等。
- **风险**：clone/CI/审查 diff 变慢；大 JSON 进 git 历史不可逆地放大仓库。
- **修复建议**：大体量报告产物移出 git（对象存储/artifact），仓库只保留 Markdown 摘要 + manifest 指针；`generated/api-types.ts` 可改为 CI 生成而非提交（或保留但纳入 `api:check` 校验）；为 `docs/reports/*.json`、`backend/data/analytics/` 配 `.gitignore`/LFS 策略。
- **验证**：`git count-objects -vH` 基线对比；CI 缓存命中率。

#### P2-4　线上 market-read Redis 命中率偏低、BFF 偶发超时（云性能报告告警）
- **证据**：`docs/reports/gupiao-cloud-performance-2026-05-30-153724.json` —— `market_read.cache_misses=2498, mysql_fallbacks=2494, redis_hits=643`（≈20% 命中）、`unresolved_misses=4`；`observability.alerts` 含 `bff_partial_timeout(2)`、`bff_partial_source_error(1)`、`market_read_unresolved_miss(4)`。warmup 仅 80 标的而查询覆盖数千。
- **风险**：大量请求穿透到 MySQL，行情读延迟与 DB 压力上升；BFF 超时导致 monitor 工作台偶发降级。
- **修复建议**：扩大 quote cache 预热覆盖（按自选+优先榜+持仓动态预热而非固定 80）；排查 BFF 超时的慢 Python 源端点；为 `unresolved_misses` 增补兜底数据源或明确标注数据质量。
- **验证**：连续多次跑 `scripts/` 云性能脚本，`redis_hits / (hits+misses)` 显著上升、`bff_partial_timeout` 归零。

#### P2-5　策略调整建议阈值过于粗糙，仅用聚合 PF/样本，不含 OOS/walk-forward
- **证据**：`report_queries.py:172-196` —— `samples<100 → default_off`、`PF<0.9 或 avg<0 → delete_candidate`、其余 `downweight/keep`。未引入 OOS 段、walk-forward 通过率、分季度稳定性。
- **风险**：可能把“样本不足但有效”的策略一刀切默认关，或把“靠单季度堆收益”的策略误判 keep。`首板回调 keep` 结论本身合理，但判据链条太短。
- **修复建议**：建议引入“样本量 + 分季度稳定性 + walk-forward 通过率 + OOS 不显著失效”多门槛；与 `front_row_weighted` 已有的 walk-forward / OOS 脚本结论打通。
- **验证**：对 first_board/volume_shrink 用扩展门槛复算，结论应稳定；对 N 字策略应明确给降级/删除。

#### P2-6（潜在）analytics 模块顶层 `import pandas` 可过、`pyarrow/duckdb` 仅运行时触发
- **证据**：`exporters.py:9 import pandas`（pandas 在默认 `requirements.txt:10` 中，可导入）；`duckdb_repository.py:11-13` 才 try-import duckdb；pyarrow 仅在写 parquet 时触发。
- **风险**：未来若有人在 web/runtime 部署路径 import `app.services.analytics`，**import 阶段不报错**（pandas 在），直到运行时调用 parquet/duckdb 才崩 —— 失败点隐蔽、难定位。
- **修复建议**：在 `analytics/__init__.py` 顶部对 pyarrow/duckdb 做显式可用性探测并给出清晰报错；CI 增加“部署镜像内 import analytics 应在缺依赖时 fail-fast”的冒烟。

---

### P3（低优先 / 记录项）

- **P3-1 孤儿任务**：若管理员经 `POST /api/runtime-tasks` 手动 enqueue analytics 任务，云上无消费者会永久 queued（与 P1-1 同源；运维注意）。证据：`runtime_tasks.py:20-21` enqueue 开放给 admin，但 analytics handler 不在线上 worker。
- **P3-2 文档/文案漂移**：`ARCHITECTURE.md:43-50` 仍写 5 个生产策略；`shared.py` PLAYBOOKS 把 N 字写成“核心生产”，与 24M 报告矛盾（与 P0 同源，建议一并改）。
- **P3-3 回滚手册缺口**：`PRODUCTION_RUNBOOK.md` 覆盖了“迁移容器先行、不删 volume”，但未明确 LONGTEXT 迁移的 downgrade 风险与大体量报告产物的回滚/清理流程（审查点“回滚是否覆盖数据库迁移和大报告文件”）。

---

## 3. 策略与回测专项审查

### 3.1 baseline / front_row_weighted / front_row_only 分别评价

| 策略线 | 评价 | 证据 |
|---|---|---|
| **baseline（原低吸）** | 排序逻辑**未被改动**，仍走旧 `_final_rank_score`；production_score 仅作为附加 shadow 字段注入。**但被 P0 的 N 字 CORE 污染**。 | `priority_items.py:134-140`（priority_score 仍用 `builder._final_rank_score`）、`:192`（production_score 附加） |
| **front_row_weighted** | **正确**：`production_sort_replaced=false`、`paper_enabled=true`、`production_enabled=false`；评分函数忽略 `mode/portfolio_context`、所有结果打 `front_row_weighted_shadow` 标签，结构上就是 Shadow-only。 | `strategy_lanes.py:50-60`、`production_scoring.py:75,82` |
| **front_row_only** | **正确**：强制 `production_score=None`、`watch_only=true`、`production_enabled=false`、`paper_enabled=false`；只出 `elite_watch_score`；不做生产硬过滤。 | `strategy_lanes.py:61-71,135-146`、`priority_items.py:105-107` |

结论：**三条线的边界实现与规划文档一致，front_row 没有替换生产排序，front_row_only 没有变成硬过滤。** 这是本次变更做得最扎实的部分。

### 3.2 near_entry / buy_now / soft_buy_now 生产边界评价
- **正确且严格**：`production_scoring.py:31` `PRODUCTION_STATES={"buy_now","soft_buy_now"}`；`:113-126` 非生产状态（含 `near_entry`/`observe_confirmed`/`watch`）一律 `production_score=None, decision="watch_only"`，`near_entry` 额外打 `near_entry_watch_only`。
- 报告层一致：`strategy-24m-backtest-2026-05-30.md:17,52,166` 明确“生产收益排行仅 buy_now/soft_buy_now；near_entry 单列、不进排行”，near_entry 的 656% 等权复利仅作诊断展示。
- 评分输入只用信号日可见信息（`_entry_structure_score` 用 `entry_distance_pct`、`execution_ready`，无后验收益），符合防未来函数要求。

### 3.3 24 个月数据完整性评价
- **数据本身完整**：`strategy_24m_duckdb_report.md:5-18` —— Manifest `daily_bars_20260530072230`，窗口 2024-05-30→2026-05-30，`row_count 2,355,541 / symbol_count 4,976 / trade_day_count 484`，完整性 ok。
- **门禁有效**：`quality.py:63-198` 计算应有/实际交易日、缺失天数，`status="fail" if blockers`；`analytics_handlers.py:122-127` `handle_backtest_all_strategies_24m` 数据不足直接 `{"ok":False,"status":"blocked_by_data"}`，不静默续跑；`handle_strategy_24m_duckdb_report` `create_backfill_task=True`。
- **但**：以上仅在 analytics worker 内有效，线上未部署（P1-1）。`strategy_24m_duckdb_report.md` 是本地产物，**不能据此声称线上具备 24M 完整性门禁**。

### 3.4 max5 / max10 真实组合口径评价
- **完整且正确实现**（`backend/scripts/low_buy_market_backtest_reporting.py:679-840` `portfolio_backtest_metrics`）：
  - 资金占用：`capital_occupied_during_holding=True`（:811），满仓/现金不足跳过（`max_positions` / `max_positions_cash_occupied`）；
  - 同票持有禁止重复买：`duplicate_symbol_open` 跳过（:737）；
  - 同策略单日 ≤2：`max_daily_per_strategy=2`（:685,744-749）；
  - 同板块 ≤2：`max_per_sector=2`（:686,752-756）；
  - 弱市仓位上限 40%：`weak_market_position_cap_pct=40.0`，状态 `low_volume_wait/fast_rotation`（:687,762-766）；
  - 退潮不新开仓：`block_retreat_new_positions=True`，状态 `high_flyer_retreat/risk_release`（:688,740-742）；
  - 全程 `skip_reason_counts` 记录跳过原因（:840），可解释。
- 报告 `max_5/max_10` 双档输出（:640-641,671-672），与“每日信号等权复利收益”分列（`strategy-24m-backtest-2026-05-30.md:30`）。**这是本次最值得肯定的回测工程。**

### 3.5 默认关闭策略是否仍有辅助价值
- `deep_pullback`、`trend_rebound` 为 FACTOR 层（`strategy_policy.py:45-49`），作为评分加分因子参与，**有辅助价值，保留合理**。
- 24M 报告中 `default_off` 的多数策略（原始低吸/均线支撑/位置支撑/涨停突破回踩/分歧转一致/均线通道/龙头回踩…）样本为 0，处于“休眠”——不产生信号、无直接危害，但分层噪声大，建议在分层文档里标注“休眠/未触发”而非与有效策略混列。

### 3.6 是否存在未来函数 / 过拟合 / 样本缩水 / 长期无票
- **未来函数**：回测有显式前视守卫“信号次日入场”（`engine_helpers.py:228`），评分只用信号日可见字段；前排 readiness 列出 `tick_data_insufficient_for_real_money_production`（`front_row_readiness.py:80`）。规划文档 §18 要求 `signal_time/data_cutoff_time/return_start_time`。**结构上防住了同日成交泄漏**；建议补“walk-forward 脚本实际是否输出这三时间戳”的核验（需进一步验证）。
- **过拟合**：前排加权权重高度主观（文档 §24 自述），训练/验证/OOS 时间切分 + purged gap 在规划中，front_row 自评 OOS 未满 60 日、walk-forward 未达标 → **正确地没有放量**。
- **样本缩水 / 长期无票**：`front_row_only` 信号日留存仅 ~54.76%（`strategy-24m-backtest-2026-05-30.md:108`），已明确标注“低频、可能连续多日无票”并固定为 elite_watch（`front_row_readiness.py:30`）。处理得当。
- **幸存者偏差 / 随机切分**：规划禁止随机切分、要求时间顺序切分；24M 池含 4976 标的（接近全市场），幸存者偏差较低。**需进一步验证**：回测标的池是否包含区间内退市/停牌标的，避免只取“活到今天”的标的。

---

## 4. 工程架构专项审查

### 4.1 DuckDB + Parquet/Arrow
- **设计合理**：Manifest 带 `schema_version/dataset_version/sha256/period/quality`（`manifest.py`、方案 §5.5），按月分区，数据质量表区分 ok/warn/fail；DuckDB 只读分析、不作交易事实源。`duckdb` 延迟 try-import（`duckdb_repository.py:11-13`）。
- **缺口**：见 P1-1（未部署）、P1-3（报告口径）、P2-6（import 失败点隐蔽）。Manifest/质量/导出有测试（`test_analytics_layer.py`、`test_analytics_worker.py`、`test_front_row_weighted_oos_manifest.py`）。

### 4.2 RuntimeTaskQueue + analytics worker
- **向后兼容**：沿用既有 `RuntimeTaskQueue`/`runtime_tasks` API，未破坏接口（`registry.py` 新增独立注册）。
- **worker 语义**：`handlers.py`/`worker.py`/`registry.py` 提供 claim/heartbeat/progress/retry/artifact/failure（方案 §6.5 实现）；`runtime_worker.py:41-58` 是纯队列消费 `claim_next`。
- **不抢占**：analytics 用独立 `analytics_task_registry()`，runtime-worker 不注册 analytics handler，**不会错误认领 analytics 长任务**；但反过来线上**没有进程**认领 analytics 任务（P1-1）。
- **幂等/恢复**：产物按 `task_id`/`dataset_version` 隔离；`handle_backtest_all_strategies_24m` 数据不足返回 blocked。**需进一步验证**：`handle_data_backfill_24m` 调 `backfill_daily_history.py` 子进程的幂等性（重复补数是否按 symbol+date upsert，不产生重复行）。

### 4.3 Contract-first OpenAPI
- **事实源正确**：`backend/scripts/export_openapi_schema.py` 从 FastAPI 导出 `docs/contracts/openapi.json`（+ `openapi.hash`）；`package.json:17-19` 有 `api:export/generate/check`；`openapi-typescript ^7.13`；`frontend/src/api/backtests.ts` **确实 import 了 `generated/api-types`**（非表面引入）。
- **缺口**：`api:check` 未进 CI（P2-1）；`api-types.ts` 724KB 入库（P2-3）。其余手写 `*Types.ts` 是否仍重复后端 DTO，需逐文件核验（本次未逐一展开）。

### 4.4 前端策略线 UI
- **三线清晰**：`strategy_lanes.py` 输出 `display_lane/title/subtitle/role`，前端 `StrategyLaneTabs.tsx`（原低吸/前排加权/前排极精选）；plain-language 文案在 `plain_status_for_lane`（`strategy_lanes.py:186-204`，“只做验证，暂不影响真实排序”等），符合“先结论后原因、避免英文缩写”。
- **状态管理合规**：全前端非测试代码 **0 处 `useState/useReducer`**（`grep` 验证），符合项目禁令；用 Zustand store（`strategyTrackingStore.ts` 等）。
- **同票多命中**：`matched_strategy_variants_for_item`（`strategy_lanes.py:96-107`）+ 主归属优先级 `front_row_only > weighted > baseline`，避免同 lane 重复、显示“同时命中”。
- **测试**：`StrategyLaneTabs.test.tsx` 等存在；但 README 文案/移动端溢出未在本次实跑（覆盖说明）。

### 4.5 部署与运维
- **链路可靠**：`migration` 容器先 `alembic upgrade head`，再 `app/runtime-worker/backtest-worker`（runbook:224,313-316）；Go 三服务为生产主路径、Python 兜底可观测（:317）；HTTPS 路径完备（:441-472）。
- **缺口**：analytics 不在 compose（P1-1）；线上裸 IP/HTTP（P1-2）；`readyz` 仅查 DB+前端 dist（`main.py:297-323`），**未含 analytics/worker 就绪**——若上线 analytics 需补就绪检查；云性能告警未清零（P2-4）。

---

## 5. 安全与合规专项审查

| 维度 | 结论 | 证据 |
|---|---|---|
| **权限-接口** | 良好。`screeners` 全 router `Depends(get_current_user)`，治理写操作 `require_admin_auth`；`runtime-tasks` 全 router `require_admin_auth`（含 POST enqueue）；`backtests` 研究端点 `require_research_access`。 | `screeners.py:25,39`、`runtime_tasks.py:17`、`backtests.py:89,99,119,128,158` |
| **任务触发** | 良好。重任务（回测/补数/写 artifact）经 RuntimeTask API 均需 admin；**未发现未认证即可触发重任务的入口**。 | `runtime_tasks.py:17-21` |
| **数据文件** | 良好。`.gitignore` 覆盖 `backend/.env`、`backend/data/*.db|*.sqlite`、`backend/data/runtime.env`、`data/`；`git ls-files` 无 runtime.env/.db/私钥被跟踪；`.env.docker.example` 全为占位符。 | `.gitignore:16-20`；`git ls-files` 核验 |
| **Cookie/Token** | **风险（P1-2）**。实现是 httpOnly+secure+samesite + 内存短期 access token + 强 CSP（`main.py:43-63`），设计正确；但线上 HTTP 必然放开了 `AUTH_COOKIE_SECURE`/`AUTH_ALLOW_INSECURE_HTTP_COOKIE`。 | `auth.py:194-210`、`security_config.py:14-19` |
| **自动交易边界** | 平台不下真单（仅模拟盘）；`paper_auto_trading_enabled` 默认 true 但仅作用于模拟账户。`AGENT_PROVIDER` 默认 `none`、Agent write/notify 默认关。**边界清晰**，但建议在 UI/文档显式声明“模拟盘≠真实下单”。 | `config.py`、compose `AGENT_PROVIDER:-none` |
| **投资建议合规** | README 有“仅研究/辅助，不构成投资建议”；前排文案强调“只做验证/仅观察/不参与生产排序”。**建议**：在低吸榜与策略跟踪页常驻“非荐股、不保证收益、不自动下单”免责声明，避免“可进真实组合候选”等措辞被误读为荐股。 | `README.md:240`、`strategy_lanes.py:186-204` |

**合规重点提醒**：P0 的 N 字策略若在生产榜出现 `buy_now`，等于向用户输出一个历史 -88% 回撤策略的“买入”信号——这不仅是策略问题，也是**展示合规风险**，应与 P0 一并处理。

---

## 6. 可执行整改路线图（5 个独立整改包）

> 每个包可独立交付、独立验收，互不阻塞。

### 包 1：生产排序与策略边界（含 P0）
- 任务：①`strategy_policy.py` 按 24M 证据重分层（移除/降级 N 字两策略）；②`production_scoring_config.py` 将 `n_pattern_long_wash` 纳入暂停；③`shared.py` PLAYBOOKS / `ARCHITECTURE.md` 文案同步；④新增“CORE 必须满足最近 24M PF/回撤门槛”单测。
- 验收：baseline 榜不再出现 N 字 buy_now/soft_buy_now；`pytest backend/tests/test_low_buy_strategy_lanes.py test_low_buy_production_scoring.py` 通过且含新断言。
- 风险：降级可能减少信号频率；先 Shadow 观察一版再切。

### 包 2：数据 / 回测 / 可交易性验证
- 任务：①统一报告口径——`report_queries.py` 改“每日信号等权复利收益”+真实组合列（P1-3）；②策略建议引入 OOS/walk-forward 多门槛（P2-5）；③回测标的池纳入区间内退市/停牌标的，消除幸存者偏差（需先验证现状）；④walk-forward 脚本输出 `signal_time/data_cutoff_time/return_start_time` 审计字段。
- 验收：两份 24M 报告同策略数值一致且口径一致；建议引擎对 N 字给降级/删除。
- 风险：口径变更需通知历史报告消费方。

### 包 3：任务系统与 Worker 稳定性（决定 analytics 去留）
- 任务（二选一）：**A 上线**——新增 `analytics-worker` compose 服务 + 镜像装 `requirements-analytics.txt` + runbook 补章节 + `readyz` 增 analytics 就绪；**B 离线**——文档/UI 标注离线工具 + runtime-worker 对未知 analytics 任务 fail-fast（避免永久 queued，P3-1）。两方案都要解决 P1-1。
- 验收：A 方案云上能跑通 `strategy_24m_duckdb_report`；B 方案云上 enqueue analytics 任务会被快速失败并提示。
- 风险：A 增加镜像体积与运维面，按需启用。

### 包 4：前端展示与提示文案
- 任务：①低吸榜/策略跟踪常驻免责声明（合规）；②前排加权页固定“只做验证，暂不影响真实排序”、front_row_only 固定“仅观察，不参与生产排序”（已具雏形，确保移动端不溢出）；③`readiness_unknown` 文案明确“未通过”，禁止默认通过（`front_row_readiness.py` 已正确，前端确认呈现）。
- 验收：桌面/移动端三线文案可读不溢出；P0 修复后 N 字不再出现“可进真实组合候选”措辞。
- 风险：低。

### 包 5：部署、安全与性能门禁
- 任务：①线上切域名+HTTPS、关闭不安全 cookie 开关（P1-2）；②CI 增 `api:check`+前端 typecheck/vitest（P2-1）；③大体量报告/生成文件出库或 LFS（P2-3）；④LONGTEXT 迁移在 staging 计时 + 低峰执行 + 补回滚说明（P2-2、P3-3）；⑤扩大 quote cache 预热、排查 BFF 超时（P2-4）。
- 验收：`https://<domain>` 证书有效且 `AUTH_COOKIE_SECURE=true`；CI 能拦截契约漂移；`git count-objects` 显著下降；云性能告警清零。
- 风险：HTTPS 需域名与 80 端口可用。

---

## 7. 覆盖检查（实际检查范围与未覆盖说明）

### 已实际检查
- **指定文档（9/9）**：`AGENTS.md`、`IMPLEMENTATION_PLAN.md`（按标题与近段抽读，198KB 未逐行）、`PRODUCTION_RUNBOOK.md`、`docs/reports/strategy_24m_duckdb_report.md`、`docs/reports/strategy-24m-backtest-2026-05-30.md`（grep 结构+关键段）、`docs/reports/gupiao-cloud-performance-2026-05-30-153724.json`、两份 front-row 开发计划、`docs/TQuant_DuckDB_Parquet_Worker_ContractFirst_开发方案.md`。
- **策略与回测**：`strategy_policy.py`、`production_scoring.py`（全文）、`production_scoring_config.py`、`strategy_lanes.py`（全文）、`priority_items.py`（核心段）、`signal_state.py`（前次审查）、`low_buy_market_backtest_reporting.py:679-840`（组合约束）、`engine_helpers.py`/`broker.py`（前视/撮合，前次审查）、`strategy_auto_governance.py`（决策段）。
- **分析层/任务系统**：`backend/app/services/analytics/*`（config/exporters/manifest/quality/duckdb_repository/report_queries/__init__）、`tasks/{registry,handlers,worker,analytics_handlers}.py`、`workers/runtime_worker.py`。
- **后端/路由/安全**：`main.py`、`api/router.py`、`screeners.py`、`runtime_tasks.py`、`backtests.py`、`admin_auth.py`、`security_config.py`、`config.py`、`auth.py`（cookie 段）。
- **契约/前端**：`frontend/package.json`（api 脚本）、`docs/contracts/openapi.json` + `openapi.hash`（存在性/大小）、`frontend/src/generated/api-types.ts`（存在+被 `backtests.ts` 引用）、`webRouteDefinitions.tsx`、`vite.config.ts`（前次）、全前端 `useState/useReducer` 扫描。
- **部署/迁移/安全卫生**：`Dockerfile`、`docker-compose.mysql.yml`（worker/env/analytics 缺失）、`.github/workflows/ci.yml`、最新 4 个 Alembic 迁移（tick_trade_snapshots、widen payload）、`.gitignore` 与 `git ls-files` 敏感文件/体积扫描、`VERSION.json`、`.env.docker.example`。
- **测试清单**：后端新功能测试存在性（analytics/lanes/production_scoring/front_row_weighted/strategy_variant）、前端 `StrategyLaneTabs.test.tsx`。

### 未覆盖 / 仅部分覆盖（不默认通过）
- **未运行任何测试**：所有“测试存在”仅指文件存在与断言意图，未执行 `pytest`/`vitest`，不代表当前全绿。**建议执行**：`pytest backend/tests -q`、`cd frontend && npm run test -- --run`、`npm run api:check`。
- **未访问线上实例**：`http://43.143.243.97:18090` 是否运行 `e9dae628` 代码、是否真的开了不安全 cookie、N 字是否被 auto-governance 暂停——均**未在线核验**，标注为“需进一步验证”。建议在线拉 `/api/screeners/low-buy/priority-board`、`VERSION.json`、`/readyz`。
- **未逐行读 IMPLEMENTATION_PLAN.md（198KB）** 与 `strategy-24m-backtest-2026-05-30.md` 全文（仅 grep 结构与关键行）。
- **未逐一核验** `low_buy/`（约 130 文件）全部信号规则、`frontend/src/api/*Types.ts` 是否仍有重复手写 DTO、移动端实际溢出表现、`backfill_daily_history.py` 子进程幂等性。
- **未做** ETF T0、模拟盘自动交易、Go/Rust seam 的本轮深审（前次系统评估已覆盖框架，本轮聚焦最新 front-row+analytics 变更）。

---

### 附：与“审查要求”的逐条对应（自检）
- 严厉、不只写优点：是（1 P0 + 4 P1 + 6 P2）。
- 不因测试通过默认安全：是（未运行测试，且 CI 缺契约/前端门禁单列为 P2-1）。
- 检查新增与旧系统交互：是（P0 即新前排 Shadow 与旧 CORE 分层的事实源冲突）。
- 不把 Shadow/Paper 当生产通过：是（front_row 全程 shadow，明确不放量）。
- 不把等权复利当真实组合：是（P1-3 直接点名 DuckDB 报告口径）。
- 不忽略线上/本地不一致：是（P1-1 analytics 未部署、P1-2 线上 HTTP、覆盖说明未在线核验）。
- 建议可落地：是（5 个独立整改包 + 验收 + 验证命令）。
- P0/P1 是否暂停：**建议暂停“小流量生产观察/替换生产排序”的推进，直到 P0 与 P1-1/P1-3 闭环；线上演示可继续，但在切 HTTPS 前不接真实用户与真实持仓数据。**
