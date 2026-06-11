# 全项目工程质量审查报告（2026-06-11）

> 性质：**只读审查 + 报告**。未重构、未删除模块、未部署、未切流、未执行线上写操作。
> 分支：`codex/phase4-phase5-architecture`；跟踪文件 2939 个。
> 在途保护：工作树存在**集合竞价 provider spike**（`backend/app/services/auction/`、spike 脚本/测试、执行计划与 dry-run 报告）——本轮未触碰。
> 取证方式：18 组命令证据（全量测试实跑 + rg/grep 逐项核验）；引用昨日体检（`platform-system-check-2026-06-10.md`）已验证事实时显式标注。
> 边界遵守：未改 `strategy_policy.py`/生产排序/`production_score`/风控阈值/交易日门控；strategy_engine 保持 shadow-only。

---

## 一、执行摘要

### 当日实测基线（全部今日新跑）

| 维度 | 结果 |
|---|---|
| 后端全量 pytest | **1492 passed / 0 failed**（含在途竞价 spike 测试） |
| frontend-next 单测 | **131/131**；typecheck/lint/CSS guard(25 文件)/boundary guard/bundle budget 全绿 |
| frontend-next e2e | **47/47 passed**（昨日 5 个 data/settings 失败已被并行工程修复） |
| Bundle | 654KB / 22 chunks（echarts 已移除） |
| CI | 已分层：backend（compileall→覆盖门→全量 pytest→警告预算）+ frontend-next（api:check→typecheck→lint→test→build→playwright **串行**）；**零旧前端引用** |
| 旧前端退役 | CI 0 引用；`deploy/frontend/Dockerfile` 仅构建 frontend-next；**后端只服务 FRONTEND_NEXT_DIST**（`main.py:581`），readyz 的 `frontend_dist` 键已指向 frontend-next |
| 大文件 | 仓库仅剩 1 个 >2MB 跟踪文件（12MB front-row JSON） |

### 最高风险 Top 10（按当前实际风险排序）

| # | 风险 | 等级 | 状态 |
|---|---|---|---|
| 1 | **线上服务器内存超卖未收口**（4C/3.7G、Swap 1.74G 重度使用、compose 上限之和 ~3.9G > 物理内存）——配置已在仓库，**线上未执行** | P1 | 待授权执行（O4/O8） |
| 2 | first_board 最近季度 OOS 代理 **PF 0.75/-1.01%**（策略域，已有 S2 诊断计划） | P1 | 待执行 |
| 3 | 热聚合 N+1 嫌疑未测量：`priority_items.py:71` 逐行循环（needs_measurement） | P1 | 待测量（O10） |
| 4 | 无结构化日志：`backend/app/core/` 无 structlog/json 日志配置，线上排障靠裸文本 | P1 | 建议 |
| 5 | 12MB `front-row-weighted-...2026-05-29.json` 仍跟踪在仓库（违反规范 §6.7） | P2 | 待出库 |
| 6 | 优化后线上性能从未复测（Redis 命中率/p95 均为优化前数据） | P2 | 待授权只读复测（O11） |
| 7 | 旧 `frontend/` 源码（3.5M）+300 单测仍在仓库但已不在 CI/服务路径——**测试退化无人发现**的灰色态 | P2 | 需归档决策 |
| 8 | `docs/reports` 磁盘 53M（多为未跟踪截图/产物） | P3 | 清理建议 |
| 9 | analytics 测试日期漂移缺共享工具（同类假红已发生 ≥2 次） | P3 | O6 |
| 10 | `tquant_internal_service_token` 默认空=fail-closed（**正确**），但分离部署若未配置会导致 scan-worker 内部调用静默 403 | P3 | 文档化 |

**总评**：经过近两周的连续整改（架构边界、瘦身、退役、体检修复），平台工程质量处于**本会话观察期内最佳状态**——三端测试全绿、CI 分层、守卫完备、退役收口。剩余风险集中在**线上执行类**（内存、性能复测）与**测量类**（N+1）事项，仓库内代码风险已基本清空。

---

## 二、模块清单

| 模块 | 职责 | 入口 | 主要依赖 | 风险级 |
|---|---|---|---|---|
| `backend/app/api/routes`（48 路由） | API 入口/鉴权/编排 | `main.py:91 include_router` | services 层 | 低（鉴权抽查通过，见 §3） |
| `backend/app/services/low_buy`（~25k 行） | 生产策略/榜单/物化 | screeners、BFF | market、tasks | 低（67 守卫绿）；复杂度高=keep-but-shrink |
| `backend/app/services/market`（~10k 行） | 行情/缓存/regime | quote_router 等 | providers、Redis | 低（超时/fallback 模式齐：`quote_router.py:37-73` 3s 超时+ThreadPool fallback） |
| `backend/app/services/{paper,backtest,tasks,bff,analytics}` | 模拟盘/回测/队列/聚合/分析 | 各自 router/worker | MySQL/DuckDB | 低 |
| `backend/app/services/auction`（在途） | 竞价 provider spike | spike 脚本 | provider 框架 | 在途，无生产触点（仅 provider_spike*） |
| `backend/app/services/{ml_signal,factor_mining,decision_context,strategy_improvement,strategy_engine,trading_experience,key_levels}` | 研究/影子层 | 默认门控关 | — | 低（`config.py:101-104` 四开关全 False；flags `:69-76` 全 False） |
| workers（runtime/scheduler/analytics/backtest） | 重任务执行 | compose | RuntimeTaskQueue | 低（注册表治理：`registry.py` 32 定义 + `test_runtime_task_registry_governance.py`） |
| `frontend-next`（2.0M src） | 唯一生产前端 | routeTree | TanStack/Solid/lightweight-charts | 低（131 单测+47 e2e 全绿） |
| 旧 `frontend`（3.5M src） | 已退役（CI 0 引用、服务端不再挂载） | — | — | **灰色态**：源码+300 测试留仓但无 CI 看护 |
| `go-services`（240K） | bff/market-read/scan 加速 | compose | Redis/MySQL | 低 |
| `rust/tquant-rs`（16K src） | 金融数学（11 文件复用） | PyO3 | — | 低 |
| `scripts`（1.9M） | 部署/运维/回测脚本 | Makefile | — | 中（数量多，历史一次性脚本待归档） |
| `docs`（58M） | 文档/报告 | — | — | 中（磁盘大头为未跟踪产物） |

---

## 三、问题列表（P0–P3，全部带证据）

### P0（阻断级）
**无。** 今日三端全量验证零失败；昨日体检发现的 2 处生产回归（paper 预热、smoke 路径）与 7 个红测均已修复并复验。

### P1

**P1-1 线上内存超卖未收口（执行类）**
- 证据：2026-06-09 线上只读巡检（Swap 1736/1987MiB）；compose 上限之和 mysql 1024+app 768+runtime-worker 768+scheduler 640+analytics 512+redis 128 ≈ 3.9G > 3.7G 物理内存（compose 实测，06-10 核验）。
- 影响：重度 Swap 拖慢全栈（API 延迟、chunk 加载慢的环境根因）。
- 修复：已有完整方案（`cloud-server-optimization-plan-2026-06-09.md` + 优化计划 O8）：`RUNTIME_WORKER_EMBED_SCHEDULER=true`（开关已存在，`config.py:58`）、heavy worker profiles 化、builder prune、swappiness。
- 验收：`free -m` Swap<300M；`/readyz` 全 true；收盘发布按时。**需单独授权（线上操作）。**

**P1-2 first_board OOS 失效未诊断（策略域）**
- 证据：`strategy_24m_duckdb_report.md`：OOS quarter_proxy 46 笔 PF 0.75 / -1.01% vs 样本内 PF 2.63。
- 修复：S2 诊断（按月×market_state×板块拆亏损，用既有 `strategy_improvement/{walkforward,temporal_guard}.py`）→ 结论三选一，禁无结论调参。**不混入本平台审查执行，按 S 计划走。**

**P1-3 热聚合 N+1 needs_measurement**
- 证据：`backend/app/services/low_buy/priority_items.py:71` `for row in rows:` 逐行 `_build_priority_item`；是否真有逐行 DB 往返**未测量**。
- 修复：O10——先写"DB 往返计数"测试（SQLAlchemy `before_cursor_execute` 计数，N=20 候选断言上界），超界才修（批量预取+共享上下文），golden 守卫榜单 sha256 零漂移。
- 验收：计数测试 + 67 项策略守卫全绿。

**P1-4 无结构化日志**
- 证据：`grep structlog|STRUCTURED_LOGS|json log` 在 `backend/app/core/logging*.py`、`main.py` 零命中（compose 有 `STRUCTURED_LOGS` env 但核心无对应实现挂接核验点）。
- 影响：线上排障/审计依赖裸文本日志；与 `/metrics`、readyz 相比，日志是观测三支柱中最弱一环。
- 修复：core 层统一 JSON 格式器（logging.Formatter 即可，不必引 structlog），关键路径（任务执行、收盘发布、provider 失败）带 `trade_date/task_id/symbol` 结构字段。
- 验收：采样日志可被 `jq` 解析；不改业务行为。

### P2

**P2-1 12MB 跟踪 JSON 未出库**
- 证据：`git ls-files` 唯一 >2MB：`docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`（12MB）。其余大产物已在瘦身中删除。
- 修复：留 MD 摘要+manifest 指针后出库（artifacts/LFS）；规范 §6.7。
- 验收：`git ls-files` 无 >2MB；`rg --fixed-strings <basename>` 无代码引用。

**P2-2 线上性能未复测**
- 证据：现存命中率/p95 数据全部为优化前（Redis 命中 ~20%、monitor_bff p95 一度 852ms 为 5/30-6/4 数据）；其后已落地 C 驱动、需求集预热（含本周修复的 paper 缺口）、BFF 合包。
- 修复：O11 只读复测包：`/metrics` 切片 + 云性能脚本，对照门 命中≥90%、`bff_partial_timeout=0`、p95≤500ms。**需服务器只读访问授权。**

**P2-3 旧前端"灰色态"**
- 证据：`frontend/src` 3.5M + ~300 单测仍在仓库；CI 0 引用（`grep -c frontend/ ci.yml = 0`）；后端仅服务 frontend-next dist（`main.py:581`）；deploy Dockerfile 仅 frontend-next。
- 影响：源码无 CI 看护=测试腐化无感知；占仓库与认知成本；但**物理删除需单独授权**（硬边界）。
- 修复建议：二选一决策——① 归档分支/tag 后从主干移除（推荐，保留 git 历史可恢复）；② 保留但在 README 标注"已退役、无 CI 看护"。
- 验收：决策落档；如归档，`git ls-files | grep -c "^frontend/"` 归零且 tag 可检出。

**P2-4 scripts 目录历史脚本堆积**
- 证据：`scripts/` 1.9M，混含部署主链（deploy_cloud_server/one_click/quick）与历史一次性脚本；规范 §6.2.7 要求可重复工具与一次性草稿分离。
- 修复：盘点分类→一次性脚本移 `scripts/archive/`；Makefile 收敛常用入口。

### P3

**P3-1 测试日期漂移缺共享工具**（O6）——同类假红 ≥2 次（analytics 3 处、low_buy read_paths 1 处）；本周修复时已建 `backend/tests/support/export_time.py`（今日核验 `test_analytics_layer.py:42` 已引用 `EXPORT_WINDOW_END_DATE`），**剩余动作**：把约定写进 conventions 并推广到其余日期窗口测试。
**P3-2 `tanstack-misc` 139KB**（O7）——budget 内；先 `chunk:profile` 评估，引用面 ≤2 页才拆。
**P3-3 internal token 部署文档化**——`internal_scan_worker.py:11-15` fail-closed 正确；但分离部署未配 `tquant_internal_service_token` 时 scan-worker 内部调用会静默 403，需在部署 runbook 标注必配项。
**P3-4 `docs/reports` 磁盘 53M**——多为未跟踪截图/walk-forward 产物；按保留期归档（不入库）。
**P3-5 late_session walk-forward 0/7**——策略域，已正确限权（low_sample_capped），等样本累积（S7），无平台动作。

---

## 四、性能优化清单

| 项 | 现状证据 | 动作 | 预期 |
|---|---|---|---|
| 热读路径 | 需求集预热已上线（7 类需求集，paper 缺口本周已修）；命中率未复测 | O11 复测 → 未达 90% 再调预热集合/TTL | 命中 ≥90% |
| N+1 | `priority_items.py:71`（needs_measurement） | O10 计数测试先行 | 榜单构建往返有上界 |
| DB | `database.py:59-67` pre_ping + pool 12/24 + recycle 1800 ✅；驱动已 mysqldb(C) ✅ | 维持；慢查询日志在 O11 一并采样 | — |
| 缓存 | Redis 主缓存 + local_quote_cache + BFF workspace cache 三层齐 | 复测命中率（O11） | — |
| 前端 bundle | 654KB/22 chunks、echarts 已移除 ✅ | 仅 O7 可选项 | 维持预算 |
| 任务队列 | 注册表 32 定义 + 治理测试 ✅ | 维持 | — |
| 报告生成 | DuckDB/Parquet 在 analytics worker（门控） | 维持 worker 化 | — |
| 构建/测试耗时 | 后端全量 60s、前端 unit 2s、e2e 14.5s | 健康，无动作 | — |
| 服务器 | Swap 重度（执行类） | O4/O8 | 全栈延迟改善 |

## 五、稳定性增强清单

| 项 | 现状 | 增强 |
|---|---|---|
| 降级 | quote_router 3s 超时+fallback（`:37-73`）；BFF partial 不阻断主数据；publish-if-ready 门控 | 维持；O11 复测 `bff_partial_timeout` |
| 重试/幂等 | RuntimeTask 重试+幂等键+注册表 ✅ | 维持 |
| 熔断 | provider circuit 既有 | 竞价 provider（在途）按同模式接入 |
| feature flag 默认 | 研究/重任务/前端实验全默认 False ✅（`feature_flags.py:60-81`、`config.py:101-104`） | 维持；新竞价 4 flag 默认关（PRD 已约定） |
| 失败隔离 | Web 零后台 loop；worker claim 范围守卫 | 维持 |
| 告警 | quote 覆盖率告警函数已存在；漂移告警 flag 默认关 | S8 开 track record 后再放开 |
| 异常观测 | healthz/readyz/metrics ✅（`main.py:325-369`） | **补结构化日志（P1-4）** |
| chunk 白屏自愈 | frontend-next 已有 chunkReload + RouteLoading | 维持 |

## 六、模块处置建议（delete / default-off / keep-but-shrink / keep）

| 类别 | 模块 | 证据 |
|---|---|---|
| **delete（需单独授权，本报告非授权）** | 12MB front-row JSON（出库）；`scripts/` 一次性历史脚本（归档式删除）；旧 `frontend/`（**归档 tag 后移除**，CI/服务端已零依赖） | §P2-1/P2-3/P2-4 |
| **default-off（维持现状即可）** | trading_experience 7 flag、AKeyLevel、leader_pullback、frontend_wasm/solid_island、研究/ML/因子/进化 jobs | 全部已默认 False（今日核验） |
| **keep-but-shrink** | `low_buy`（~25k 行：owner+边界文档+死代码扫描，不动生产语义）；`scripts`（分类归档）；`docs/reports`（磁盘产物保留期） | 规模证据 §二 |
| **keep（不可动）** | low_buy 生产链、market、paper、backtest、tasks、bff、go 三件套、rust、frontend-next、核心 jobs、openapi 契约 | 核心闭环 |

## 七、推荐实施路线（D0–D7）

| 批 | 目标 | 范围 | 验收 | 停止条件 |
|---|---|---|---|---|
| **D0** | 基线冻结 | 本报告 + 今日三端全绿记录 | 已完成 | — |
| **D1** | N+1 测量（O10 前半） | 新增计数测试，不改实现 | 测试落地出数 | 无 |
| **D2** | 结构化日志（P1-4） | core JSON formatter + 3 个关键路径字段 | `jq` 可解析；pytest 全绿 | 日志量异常→回退 formatter |
| **D3** | 12MB JSON 出库 + scripts 归档盘点 | docs/reports、scripts | `git ls-files` 无 >2MB；引用 grep 零命中 | 发现引用→停 |
| **D4** | 服务器内存收口（**需授权**） | O4/O8：embed scheduler/profiles/prune/swappiness | Swap<300M、readyz 全 true、收盘发布按时观察 1 交易日 | 发布异常→立即回滚 env |
| **D5** | 线上性能复测（**需授权，只读**） | O11：metrics+p95 对照门 | 复测报告落档 | — |
| **D6** | N+1 修复（视 D1 结果） | 批量预取+共享上下文 | golden sha256 零漂移 + 守卫全绿 | golden 漂移→revert |
| **D7** | 旧前端归档决策 + 日期工具推广（O6 收尾） | 决策文档 + conventions 更新 | 决策落档 | — |

策略域（S2/S1/S4b 竞价 Phase1）按 `strategy-success-rate-optimization-plan-2026-06-10.md` 独立推进，不混入本路线。

## 八、不建议改动清单（硬保护）

- `strategy_policy.py`、`production_scoring*`、priority board 排序语义、生产策略公式、风控阈值、`participates_in_priority_board` 单一门。
- 交易日发布门控：`publish_latest_trade_date_if_ready`、收盘 15:01 刷新、invalid OHLC blocker、交易日历口径。
- strategy_engine shadow-only（`replacement_enabled=false`）、execution model preview 不替代事实源。
- `portfolio_backtest_metrics` 唯一组合事实源；研究/ML/因子任务不回 Web 主进程。
- 核心闭环：monitor→playbook→backtest→paper→settings 及其后端服务、RuntimeTaskQueue、go 读路径、OpenAPI 契约。
- 在途竞价 spike 工作面（由其作者推进，按 PRD 边界）。

## 九、最终结论

**先做（低风险高收益，纯仓库改动，无需授权）**：D1 N+1 计数测试、D2 结构化日志、D3 大文件出库+脚本归档、O6 日期工具推广。合计 ~3 人日。

**需单独授权**：D4 服务器内存收口（线上 env/容器操作）、D5 性能只读复测（服务器访问）、旧前端归档移除（物理删除授权）、12MB JSON 出库的最终删除提交。

**需线上数据/测量后再判断**：N+1 是否真修（看 D1 计数）、缓存命中率是否达 90%（看 D5）、tanstack 拆分（看 chunk:profile）、竞价过程信号（看 Phase 3 前向样本）。

**总体判断**：连续两周的整改链（架构边界→瘦身→退役→体检修复→e2e 收口）已把平台带到三端全绿、守卫完备、CI 分层的状态；**仓库内已无 P0**，剩余事项以"线上执行 + 测量驱动"为主。最大的两个未了结风险——服务器 Swap 与 first_board OOS——分别有现成方案（O4/O8）与诊断计划（S2），只差执行授权与排期。
