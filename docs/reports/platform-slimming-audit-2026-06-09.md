# 平台瘦身与资源占用审查报告（2026-06-09）

> 性质：**只读审查，未修改代码、未部署、未提交、未 push、未删除文件**。仅新增本报告。
> 基线：`git status --short` 仅 2 个脏文件（`frontend-next/src/features/auth/authModel.tsx`、`shared/api/auth.ts`，他人在途，已保护）；`git ls-files` = **3000** 个跟踪文件。
> 已读：`AGENTS.md`、`docs/engineering-conventions.md`、`docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`。
> 硬边界遵守：未动 `strategy_policy.py` / 生产排序 / `production_score` / 核心交易闭环 / 行情读取 / 任务队列 / 数据刷新；废弃 API/重任务仅标记不改。

---

## 1. 执行摘要

### 当前最重的 5 个资源/复杂度来源

| # | 来源 | 体积/规模 | 跟踪? | 性质 |
|---|---|---|---|---|
| 1 | `backend/data/`（analytics/parquet/duckdb/sqlite 本地数据） | **2.4 GB** | 否（gitignore） | 本地/运行时数据，非仓库膨胀 |
| 2 | `backend/.venv` 1.3G + `rust/tquant-rs/target` 772M | **~2.1 GB** | 否（gitignore） | 本地构建产物 |
| 3 | `frontend/node_modules` 414M + `frontend-next/node_modules` 243M | **~657 MB** | 否 | **两套前端**各自依赖 |
| 4 | `docs/reports/` 跟踪大文件 | **53 MB**（含单个 **13MB** JSON + ~30MB 截图 PNG） | **是** | **真·仓库膨胀**（违反规范 §6.7） |
| 5 | `backend/app/services/low_buy/` | **24,975 行** / ~130 文件 | 是 | 核心但复杂度最高 |

> 关键区分：① 占盘大头（data/venv/target/node_modules）都已 **gitignore，不进仓库、不进生产镜像** → 属"开发机清理"，非平台瘦身；② 真正进仓库的膨胀是 `docs/reports` 的大 JSON/截图。

### 最值得优先瘦身的 5 个模块/项

1. **`docs/reports` 大产物出库**（13MB `front-row-weighted-...json` + 3 个 frontend-next 截图目录 ~12MB + 多个 strategy-24m JSON）→ 转 artifacts/LFS，仓库留 MD 摘要+指针。**零风险，最高 ROI**。
2. **两套前端并存**（`frontend/` 485M 生产 + `frontend-next/` 247M 影子）→ cutover 决策前不动；决策后收敛为一套。**架构级，需用户决策**。
3. **已 flag-off 的研究套件**（`trading_experience`、`key_levels/AKeyLevel`）→ 维持隐藏，决定"启用还是归档"。**已隐藏，零运行成本**。
4. **研究/ML/因子后台任务**（ml_signal、factor_mining、strategy_evolution、strategy_validation）→ **已默认门控关闭**，无需停 job；剩余是代码维护成本，长期可归档。
5. **agent 集成（MCP/Hermes/通知）** → 可选集成、默认关，前台无闭环 → 维持隐藏/标记归档候选。

### 明确不能动（保护清单）

- `backend/app/services/low_buy/strategy_policy.py`、`production_scoring*`、`priority_board*`、`priority_read_model`、`low_buy_materialization`、`strategy_tracking*`、front-row weighted 排序。
- 核心闭环路由 `/monitor → /monitor/market → /analysis → /playbook → /backtest → /paper → /data → /settings` 及兼容跳转。
- 核心后台 job：`low_buy_full_scan`、`market_quote_cache_refresh`、`market_hourly_all_a_snapshot`、`low_buy_materialization_refresh`、`daily_bar_refresh`、`latest_data_watchdog`、`market_*_review`、`watchlist_signals`、`market_regime_prewarm`、`paper_*`。
- `backend/app/services/{market,paper,backtest,tasks,bff}`、`monitor_snapshot_service`、RuntimeTaskQueue。
- `docs/contracts/openapi.json`（契约事实源，1.1MB 必须留）。

---

## 2. 模块分级表

### P0 核心保留（不可动）
| 模块 | 证据 | 价值 |
|---|---|---|
| low_buy 生产（strategy_policy/production_scoring/priority_board/materialization/read_model） | `services/low_buy/` 24,975 行；48 路由中 `screeners.py`(555) | 生产排序/买点信号，闭环核心 |
| market 读路径 | `services/market/` 10,075 行；`market.py`(504) | 行情/快照/breadth/pulse |
| paper 模拟盘 | `services/paper/` 9,042 行；`paper*` 路由 | 模拟盘闭环 |
| backtest | `services/backtest/` 4,276 行；`backtests.py`(750) | 回测闭环 |
| tasks 队列 + 核心 worker/job | `services/tasks/` 1,424；`runtime_worker.py`；8 个核心 loop | 数据刷新/物化/队列 |
| bff/monitor 聚合 | `bff.py`(917)、`services/bff/`、`monitor_snapshot_service` | 监控页主数据 |
| 旧前端核心页 | `frontend/src/features/{monitor,playbook,backtest,paper,settings,strategy-tracking,analysis,data-console}` | 主交易闭环 |

### P1 保留但优化
| 模块 | 证据 | 优化点 |
|---|---|---|
| `bff.py` 917 行 / `backtests.py` 750 行 | route 文件偏大（规范评审阈值 350/500） | 路由拆 service/query，入口瘦身（不改契约） |
| low_buy ~130 文件 / 24,975 行 | 规范已记 E3 | 模块 owner + 边界文档 + 死代码扫描（不重构生产） |
| `docs/contracts/openapi.json` 1.1MB | 契约必留 | 不动；仅作为大文件基线说明 |
| 旧前端 bundle | `antd-core`等首屏 AntD 较重（历史审查 F1/B4） | 已在 frontend-next 收敛；旧前端只做小修 |

### P2 默认隐藏/Feature Flag 关闭（已隐藏，维持）
| 模块 | flag（默认值） | 是否有测试 | 处置 |
|---|---|---|---|
| AKeyLevel 关键位引擎 | `a_key_level_engine_enabled=False` | 是（`test_key_levels_*`） | 维持隐藏；决定启用或归档 |
| 交易经验/观察套件 | `trading_experience_suite_enabled=False`、`trade_review_suite_enabled=False`、`vp_position_tags_enabled=False`、`relative_strength_board_enabled=False`、`holding_discipline_assistant_enabled=False`、`limit_up_followthrough_enabled=False`、`t_trade_discipline_enabled=False` | 是（`test_trading_experience_*` 5+） | 维持隐藏；前台无闭环时不启用 |
| leader pullback band 策略 | `strategy_leader_pullback_band_enabled=False` | 部分 | 维持隐藏 |
| agent（MCP/Hermes/通知） | 默认传输 none（可选集成） | 部分 | 维持隐藏；前台无闭环 |
| 旧前端 `ritual-ui`（仪式祝福弹窗）、`key-levels`、`trading-experience` feature 目录 | 对应后端 flag off | 部分 | 入口隐藏/降级高级态 |

### P3 停用后台任务（**多数已默认门控关闭，无需停**）
| 任务 | 门控 | 现状 |
|---|---|---|
| `strategy_validation_monthly`、`backtest_research_worker`、`low_buy_strategy_governance`、`strategy_self_evolution` | `tquant_research_jobs_enabled` | **默认 False**（`config.py:95`）→ 不运行，零资源 |
| `ml_signal_incremental_train_weekly`、`ml_feature_drift_monitor_monthly` | `tquant_ml_jobs_enabled` | **默认 False**（`config.py:96`）→ 不运行 |
| `factor_mining_monthly` | `tquant_factor_jobs_enabled` | **默认 False**（`config.py:97`）→ 不运行 |
| `analytics_24m_duckdb_report` | research 门控 + analytics worker | 受门控；DuckDB/Parquet 分析层（资源中，仅分析/报告，不得作生产事实源） |
| `agent_priority_notifications`、`agent_daily_report_push` | agent 配置 | 默认关 |

> 结论：研究/ML/因子 job 已被 `_research_jobs_enabled()`（`background_jobs.py:92-105,532`）正确门控，**默认关闭=零运行资源**，"停 job"在资源层面已完成；剩余是**代码维护成本**（见 P4）。

### P4 归档/移除候选
| 候选 | 证据 | 前置条件 |
|---|---|---|
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` **13MB** | 单个最大跟踪文件；规范 §6.7 要求 docs/reports 只放 MD 摘要、大 JSON 进 artifacts | 留 MD 摘要 + manifest 指针后出库 |
| `docs/reports/{frontend-next-screenshots-2026-06-05,frontend-next-density-review-2026-06-06,frontend-next-visual-consistency-2026-06-07,frontend-next-visual-review-2026-06-05}` ~16MB PNG | 截图产物，非源码 | 转 artifacts；保留最新一份签收 |
| `docs/reports/strategy-24m-*.json`（1.4M+1.3M+888K+820K） | 回测机器产物 | 出库，留 MD |
| `docs/reports/{market-state-guard-walk-forward 8.8M, daily-history-backfill-runs 3.8M}` | 历史一次性产物 | 归档 `docs/archive/` 或出库 |
| 研究模块代码（ml_signal/factor_mining/decision_context/strategy_improvement/strategy_engine shadow） | 有测试但默认门控关、前台无闭环 | **不删**；标 `research_only`，长期看 cutover 后是否归档（规范 §6.10 先标记后删） |
| `frontend-next/`（影子）或 `frontend/`（旧） 二选一 | 两套并存 657M 依赖 | **需 cutover 决策**；决策前都不动 |

---

## 3. 候选模块证据明细（重点项）

### C1 docs/reports 大产物（最高 ROI、零风险）
- 文件：`docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`（13,267 KB）、`strategy-24m-backtest-2026-05-30.json`（1,442KB）、`strategy-24m-optimization-report-2026-05-28.json`（1,348KB）+ 4 个 frontend-next 视觉/截图目录（~16MB PNG）+ `market-state-guard-walk-forward`（8.8M）+ `daily-history-backfill-runs`（3.8M）。
- 入口：无代码依赖（机器产物/截图）；`rg --fixed-strings <basename>` 应先核引用。
- 测试：无。被调用：报告类，非运行时依赖。
- 资源成本：**仓库 ~40MB+**；clone/拉取变慢。
- 用户价值：历史证据，低频查阅。
- 风险：低（出库后留 MD 摘要+指针即可）。
- 推荐动作：**归档/出库**（artifacts 或 LFS），仓库留 Markdown 摘要 + manifest。规范 §6.7 明确支持。

### C2 两套前端并存
- 路径：`frontend/`（485M，生产旧前端，路由 `/*`）、`frontend-next/`（247M，影子 `/next/*`，未 cutover）。
- 入口：旧前端是线上主入口；新前端是 `/next/*` shadow（多份审计确认未切流）。
- 测试：各自有（旧 300+、新 99-105）。
- 资源：**两份 node_modules ~657M（本地）+ 两套 CI/构建**；进生产镜像的是其一。
- 用户价值：新前端体积/框架已大幅领先（gzip −52%、框架运行时 −97%），但功能 parity 与 cutover 未完成。
- 风险：高（cutover 决策）。
- 推荐动作：**需用户决策**；在 cutover 前两套都保留，决策后收敛为一套并归档另一套，避免长期双维护。

### C3 研究/ML/因子模块（已门控关，代码维护成本）
- 路径：`services/{ml_signal 2384, factor_mining 1708, decision_context 1979, strategy_improvement 1853, strategy_engine}`；job 见 P3。
- 门控：`config.py:95-97` 三个开关默认 False；`runtime_worker.py:532` 跳过未启用研究任务。
- 测试：有（`test_factor_mining.py`、`test_ml_signal_drift_monitor.py`、strategy_engine boundary 等）。
- 资源：**默认零运行时**（门控关）；仅占代码行数与认知负担。
- 用户价值：研究/影子，前台无生产闭环。
- 推荐动作：**保留 + 维持门控关**；规范 §6.10 先标记 `research_only`，cutover/产品定型后再评估归档；**不删除**（有测试、有审计价值）。

### C4 已 flag-off 的观察/关键位套件
- 路径：`services/{trading_experience 2230, key_levels 1415}`；旧前端 `features/{trading-experience, key-levels, ritual-ui}`。
- flag：`trading_experience_suite_enabled` 等 7 个 + `a_key_level_engine_enabled` 全默认 False。
- 测试：有（`test_trading_experience_*` 5 个、`test_key_levels_*` 2 个）。
- 资源：隐藏态零前台成本；AKeyLevel 物化任务若启用才有成本。
- 推荐动作：**维持隐藏**；若 6 个月无启用计划，按 §6.10 标 `deprecated/remove_candidate` 进入归档评估。

### C5 路由/route 文件偏大（P1 优化，不删）
- `bff.py`(917)、`backtests.py`(750)、`screeners.py`(555)、`strategy_tracking.py`(524) 超规范 route 评审阈值（350）/拆分阈值（500）。
- 推荐动作：route 入口保留、抽 service/query（不改 OpenAPI 契约、不改排序语义）。Web 请求重任务入口需复核（规范要求不在请求线程跑重任务——本轮未发现新违规，沿用 RuntimeTaskQueue）。

---

## 4. 优先级路线图

### Phase 1：零风险瘦身（只隐藏/出库，不删代码）
1. `docs/reports` 大产物出库（C1）：13MB JSON + 4 个 frontend-next 截图目录 + strategy-24m JSON → artifacts/LFS，留 MD+manifest。仓库 −40MB+。
2. 维持研究/ML/因子 job 门控关（已是默认，确认 `.env` 未误开）。
3. 维持 trading_experience/AKeyLevel/agent flag off（已是默认）。
4. 开发机清理（非仓库）：`backend/data`(2.4G)、`.venv`、`rust target`(772M)、`.mysql-local`、`.understand-anything` 可按需清理重建（均 gitignore）。

### Phase 2：低风险清理
1. 死代码/无引用扫描：对研究模块与旧前端 `ritual-ui`、未用组件做 `rg --files` + import 图谱，列"无引用"清单（先列后删）。
2. 过期报告归档：`docs/reports` 历史一次性产物（market-state-guard、daily-history-backfill）移 `docs/archive/`。
3. 重复文档收敛：多份 frontend-next 视觉/审计报告合并索引。

### Phase 3：中风险下线（需测试+契约+观测）
1. 废弃 API 候选：对 agent/research 路由做"近 N 天零调用"线上只读观测（**线上只读验证**，不重启）后再标弃用；OpenAPI 先标 deprecated 不删。
2. AKeyLevel/trading_experience：若确定不启用，按 §6.10 标 `remove_candidate` + 保留一次引用检查记录。
3. analytics DuckDB 报告任务：确认仍只在 analytics worker、不进 Web 请求线程；评估报告频率降本。

### Phase 4：架构级收敛（仅建议，不执行）
1. 前端单栈收敛（C2）：cutover 决策后归档另一套前端。
2. 研究层模块化下沉：ml/factor/decision_context/strategy_engine 收敛为可选研究包（独立 extras，默认不装）。
3. 容器/worker 拓扑：确认 analytics-worker 按需启动而非常驻（资源中、收益低时）。

---

## 5. 风险与回滚

- **生产排序/低吸/priority board/strategy tracking/模拟盘/回测保护**：本审查全程只读；所有 P0 模块、`strategy_policy.py`、`production_score`、核心 job 均不在任何处置建议的"删除/停用"清单内（仅在"保护清单"）。
- **回滚方式**：
  - C1 出库：保留出库前 git 历史；如需恢复 `git checkout <sha> -- <file>` 或从 artifacts 拉回。
  - flag/门控隐藏：改回对应 `_DEFAULT_FLAGS`/`config` 默认即恢复，无数据迁移。
  - job 停用：研究 job 由 env 开关驱动，置 True 即恢复。
  - 前端收敛（Phase 4）：cutover 前不动；任何收敛都先并行观察期，旧前端保留可回退。
- **契约保护**：OpenAPI 为事实源，任何"废弃 API"仅标 deprecated，删除前必须契约确认 + 线上零调用观测。

---

## 6. 最终结论

### 可以立即做（零风险）
- `docs/reports` 13MB front-row JSON + frontend-next 截图目录 + strategy-24m JSON **出库/归档**（留 MD 摘要），仓库 −40MB+。
- 确认 `.env` 未误开研究/ML/因子开关（默认已关）。
- 开发机本地大目录（data/venv/target/.mysql-local/.understand-anything）按需清理（均 gitignore，可重建）。

### 需要灰度观察
- agent / 研究路由的"近 N 天零调用"**线上只读**观测后，再决定是否标 OpenAPI deprecated。
- AKeyLevel / trading_experience 是否在可见周期内有启用计划。

### 不建议移除
- low_buy 生产链、market 读路径、paper、backtest、tasks 队列、bff/monitor、核心 job、核心闭环路由、`openapi.json`、`strategy_policy.py`。
- 有测试的研究模块（ml_signal/factor_mining/decision_context/strategy_engine/trading_experience/key_levels）——**先标记，不删**（规范 §6.10）。

### 需要用户决策
- **两套前端是否收敛**（cutover frontend-next 还是保留 frontend）——本审查不替代该决策，仅指出长期双维护成本。
- 研究层（ml/factor/RL/decision_context）是否长期保留为研究包还是归档。
- 大报告产物的归档策略（LFS / 对象存储 / docs/archive）。

---

## 交付说明（合规）
- **未修改任何代码**（仅新增本报告文件）。
- **未部署、未提交、未 push、未删除文件**。
- `git status --short` 仅含他人在途的 2 个 auth 文件 + 本报告（新增），未回滚他人改动。
