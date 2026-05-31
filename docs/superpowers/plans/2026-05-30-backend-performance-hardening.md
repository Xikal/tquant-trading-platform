# Backend Performance Hardening Implementation Plan (2026-05-30)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans。Steps 用 `- [ ]` 跟踪。
>
> **定位（不计成本下的诚实结论）：** 后端最高 ROI **不是换语言、不是 async 全量重写**。当前多语言加速架构（Python 领域逻辑 + Go 读路径 + Rust 金融数学 + DuckDB OLAP + Redis 缓存 + RuntimeTask 队列）**已经是对的**；真实瓶颈是 **① 行情缓存覆盖太窄导致 ~80% 落 MySQL，② PyMySQL 纯 Python 阻塞驱动，③ 热端点在请求线程里做 DB 计算/偶发慢源**。把这三件做掉的收益远大于任何重写。本计划据此收口，**强化而非重构**。

**Goal:** 在不改业务语义、不换主框架的前提下，把"监控工作台/市场脉搏/优先榜"这条最高频读路径的 p95 与 DB 压力显著降下来：Redis 行情命中率从 ~20% 提到 >90%、消除 BFF 慢源超时、用 C 驱动与查询治理压低 DB I/O。

**Tech Stack（保持）：** FastAPI(sync) + SQLAlchemy 2.0 + MySQL + Redis + Go 读服务 + Rust(tquant-rs) + DuckDB + RuntimeTask。**唯一驱动级变更：PyMySQL → mysqlclient(C)**（同步 SQLAlchemy 直接换 URL 驱动，非框架替换）。

---

## 1. 真实瓶颈诊断（依最新代码 + 云性能报告）

| 现象 | 证据 | 根因 |
|---|---|---|
| 行情读 ~20% 命中、2494 次落 MySQL、4 未解析 | `gupiao-cloud-performance-2026-05-30-153724.json`（redis_hits 643 / mysql_fallbacks 2494 / cache_miss 2498） | 缓存预热只覆盖 ~200 标的（自选≤80+高流动性≤200），热聚合查询数千标的 → 大面积回退 |
| 预热覆盖窄 | `market_quote_cache_refresh.py:14`(DEFAULT_LIMIT=200)、`:81-104`(_target_symbols=watchlist+top_liquidity)、`background_jobs.py:300-301`(limit=200) | 预热口径=自选+高流动性，**不等于**实际被查询的集合（优先榜候选/板块成员/持仓/扫描宇宙） |
| BFF 偶发超时 2 + 慢源 | 云报告 `bff_partial_timeout=2`；`market.py:113 build_market_pulse_sync` 每请求做 DB 计算 | 请求线程里现算，叠加同步阻塞 |
| 全同步阻塞 | 409 个 `def` 路由 vs 4 `async def`；`database.py:68 create_engine`(sync) + PyMySQL | 每个 DB/外部 I/O 阻塞一个 gunicorn worker；并发只能靠加 worker |
| DB I/O 偏慢 | compose `mysql+pymysql://`；PyMySQL 纯 Python | C 驱动可显著提速，drop-in 成本低 |
| Go 读链路正确但喂不饱 | `cache_chain.go`（redis→mysql→unresolved + metrics） | 问题在上游缓存覆盖，不在 Go 链路 |

**结论：瓶颈是“缓存未命中 I/O + 阻塞驱动 + 请求内现算”，不是 Python CPU、不是请求并发上限。** 故不引新语言、不做 async 全量重写。

---

## 2. 明确排除（即便不计成本也不做，及理由）

| 选项 | 裁决 | 理由 |
|---|---|---|
| async 全量重写（async SQLAlchemy + asyncmy + async 路由） | ❌ | 100k 行同步代码重写，风险巨大；少用户场景瓶颈是缓存/外部延迟，不是请求并发；收益/成本极低 |
| 用 Go/Rust 重写后端业务 | ❌ | 丢弃成熟 Python 领域逻辑；CPU 密集路径（读聚合/数学）已由 Go/Rust 承担；慢的是 I/O 缓存覆盖 |
| 换 NoSQL / 新数据库 | ❌ | MySQL(OLTP)+Redis(缓存)+DuckDB(OLAP) 已覆盖；再加是过度工程 |
| Kafka / 消息总线 | ❌ | RuntimeTask DB 队列在此规模足够；Kafka 是过度工程 |
| K8s / 微服务爆炸 | ❌ | 单实例 compose 适配少用户；拆分只增运维面 |
| 全站 async | ❌ | 只有“调用外部行情”的少数路径值得 async（见 G3），其余同步 + 缓存即可 |

**唯一值得的“架构动作”是 G3 的选择性异步/请求隔离**：让请求线程永不直接打外部行情源，全部走缓存/物化；仅把“外部拉取”收敛到 worker + 异步 httpx。这是增量隔离，不是重写。

---

## 3. 硬边界（不可跑偏）

1. **不改业务语义/口径**：缓存只改“命中率与覆盖”，不改行情数值、策略评分、回测口径。
2. **不换主框架**：FastAPI(sync) 保持；唯一驱动级变更 PyMySQL→mysqlclient；仅外部 I/O 路径可选 async，不波及业务同步代码。
3. **请求线程不做重计算/不直连外部源**：热端点只读 Redis/物化快照；外部拉取归 worker + 缓存。
4. **缓存覆盖按真实查询需求驱动**，不是固定 200；并以覆盖率 SLA 度量，不达标显式告警，不静默。
5. **Go 读路径保持唯一读聚合加速层**，Python 保留 fallback；不新建并行读服务。
6. **所有改动测量先行**：先用 `/metrics` + 云性能脚本取基线，再改，再对比；无回归才进下一批。
7. **重计算只在 worker**（runtime/backtest/analytics）；Web 默认无后台 loop（沿用 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`）。

---

## 4. Existing Code Anchors

- 行情缓存预热：`backend/app/services/market_quote_cache_refresh.py`（`DEFAULT_LIMIT=200`、`_target_symbols`、`_watchlist_symbols`、`_top_liquidity_symbols`）、`backend/app/runtime/background_jobs.py:293-301`（enqueue limit=200）
- 本地行情缓存：`backend/app/services/market/local_quote_cache.py`（metrics 经 `/metrics` 暴露：`local_quote_cache_*`）
- Go 读路径：`go-services/market-read-service/cmd/market-read-service/{cache_chain.go,redis_cache.go,mysql_cache.go,quote_batch.go}`、`go-services/bff-gateway/*`
- 热端点：`backend/app/api/routes/market.py`（`market_pulse`、`build_market_pulse_sync`、`pulse_cache`、`hourly_snapshot`）、`backend/app/services/bff/*`（workspace 聚合）
- DB：`backend/app/core/database.py`（`create_engine` sync、pool）、`backend/app/core/config.py`（`db_pool_size/db_max_overflow`）、compose `mysql+pymysql://`
- 优先榜/跟踪聚合（N+1 审计目标）：`backend/app/services/low_buy/priority_board.py`、`priority_items.py`、`backend/app/services/strategy_tracking*.py`
- 指标：`backend/app/main.py /metrics`（provider_*、local_quote_cache_*、bff_*、rust_*）、`go-*` `/metrics`、`docs/reports/gupiao-cloud-performance-*.json`
- DuckDB 分析（offload 重扫描，已是 P1-D1）：`backend/app/services/analytics/*`、`backend/scripts/analytics_worker.py`

## 5. Milestones（3 批，按 ROI 排序，独立可验收/回滚）

### M0 基线测量（0.5d）
- 取基线：`/metrics` 的 `local_quote_cache_hits/misses/reads`、`provider_*`；Go market-read `/metrics`（hits/mysql_fallbacks/unresolved）；跑云性能脚本得 monitor_bff/market_pulse/priority_board p95；记录入报告。

### Batch G1｜行情缓存覆盖按需化（最高 ROI，先做）
把命中率从 ~20% 提到 >90%，消除大面积 MySQL 回退与 BFF 慢源。

### Batch G2｜DB I/O 提速 + 热查询治理
PyMySQL→mysqlclient(C)、pool 调优、慢查询日志 + 热聚合 EXPLAIN + N+1 修复。

### Batch G3｜请求隔离 + 选择性异步（仅外部 I/O）
热端点只读缓存/物化；外部拉取收敛到 worker+异步，请求线程永不阻塞在外部 HTTP。

---

## Batch G1 Tasks

### Task G1-1: 预热集合按真实查询需求扩展
- [ ] 失败测试：构造 watchlist + 优先榜物化候选 + 持仓 + 板块成员，断言 `_target_symbols` 覆盖**全部被热读查询的 symbol**（而非仅 watchlist+top_liquidity）。
- [ ] `market_quote_cache_refresh.py: _target_symbols`：并入 ①优先榜最新物化候选 symbol、②当前持仓/纸面持仓、③监控工作台板块成员、④自选，去重；`DEFAULT_LIMIT` 提升到覆盖这些需求所需（分档：核心需求集全量，长尾按流动性截断）。
- [ ] 分层刷新频率：核心需求集（watchlist+board+holdings）高频（现 30s loop），长尾流动性集低频。
- [ ] 测试：覆盖率（被查询 symbol ∩ 已缓存）≥ 目标阈值。

### Task G1-2: 缓存覆盖率 SLA 指标 + 告警
- [ ] `local_quote_cache` 增 `coverage`/`demand_miss` 指标，经 `/metrics` 暴露；定义“热读需求命中率”。
- [ ] 失败测试：命中率 < 阈值（如 90%）→ 产 `quote_cache_coverage_below_target` 告警标记。
- [ ] 经既有 feishu/agent_notification 推送（无 webhook 静默跳过）；接入云性能脚本的 observability 段。

### Task G1-3: Go market-read 未命中可观测收敛
- [ ] 确认 Go `cache_chain.go` 的 `unresolved`/`mysql_fallbacks` 指标随 G1-1 下降；为 unresolved 增“缺哪些 symbol”采样日志（便于定位预热盲区）。
- [ ] 验收：云性能脚本 `market_read.mysql_fallbacks` 较 M0 基线下降 ≥80%，`unresolved_misses=0`，`bff_partial_timeout=0`。

---

## Batch G2 Tasks

### Task G2-1: MySQL 驱动 PyMySQL → mysqlclient(C)
- [ ] Dockerfile runtime 装系统库（`default-libmysqlclient-dev`/`pkg-config` build 期；`libmysqlclient`/`libmariadb` 运行期）；`requirements.txt` 加 `mysqlclient`。
- [ ] DB URL `mysql+pymysql://` → `mysql+mysqldb://`（compose/`.env.docker.example`/runbook）；保留 PyMySQL 作 fallback URL（SQLite 本地不受影响）。
- [ ] 失败/冒烟测试：`ping_database()` 通过；连接/查询正常；`alembic upgrade head` 通过。
- [ ] 验收：同一只读端点（priority_board/market_pulse）p95 较 M0 下降（贴对比）。

### Task G2-2: 慢查询日志 + 热聚合 N+1 审计与修复
- [ ] 开 MySQL 慢查询日志（>200ms）；对 `priority_board.py`/`priority_items.py`/`strategy_tracking*` 跑 EXPLAIN，定位 N+1/全表扫。
- [ ] 失败测试（按发现）：对热聚合加“查询次数上界”断言（如一次榜单构建 DB 往返 ≤ N）。
- [ ] 修复：批量查询/`selectinload`/`in_` 批取代替逐行；核验既有复合索引命中，必要时补索引（走 alembic，遵守 D3 大表迁移 runbook）。
- [ ] 验收：热聚合查询次数与耗时显著下降；功能回归绿。

### Task G2-3: 连接池与 worker 口径
- [ ] 校验 `db_pool_size/max_overflow` 与 `APP_WORKERS×每请求连接` 匹配；`pool_pre_ping` 保持；必要时调参（不盲目加大）。
- [ ] 验收：高峰期无连接等待/超时；`security_config` 多 worker+memory 限流校验仍生效（不回退 SEC2 修复）。

---

## Batch G3 Tasks

### Task G3-1: 热端点请求隔离（只读缓存/物化）
- [ ] 失败测试：`market_pulse`/monitor workspace 在“外部行情源不可达”时仍返回（读 `pulse_cache`/物化），不在请求线程现算/直连外部。
- [ ] `build_market_pulse_sync` 等：确保只读 Redis/物化快照；任何现算下沉为 worker 刷新任务（写入 `pulse_cache`）。
- [ ] 验收：拔掉外部源，热端点 p95 不受影响、不 5xx。

### Task G3-2: 外部拉取选择性异步（仅 provider 路径）
- [ ] 仅把“调用外部行情源”的 provider 客户端改 async httpx 并发批取（`market_quote_cache_refresh` 的 worker 侧 `get_quotes_batch`），缩短预热/补数墙钟；**业务同步代码不动**。
- [ ] 失败测试：批量并发拉取正确、超时/熔断保持（复用 provider circuit）。
- [ ] 验收：预热一批墙钟时间下降；circuit/降级行为不变。

### Task G3-3（引用既有 P1-D1）: 部署 DuckDB 分析层卸载重扫描
- [ ] 按 `维斯量化平台-完整提升整改方案` 第 5 节把 analytics-worker 上线（镜像 build-arg + compose 服务 + `/readyz` 依赖检查）。
- [ ] 验收：24M 报告/重扫描在 analytics-worker 跑，不再压 Web/MySQL OLTP。

---

## 6. Acceptance Matrix（量化门）

| 指标 | M0 基线 | 目标 | 来源 |
|---|---|---|---|
| 行情 Redis 命中率 | ~20%（643/3141） | ≥90% | `/metrics` local_quote_cache_*、Go market-read |
| market-read MySQL 回退 | 2494 | ≤ 基线×0.2 | Go `/metrics` |
| market-read unresolved | 4 | 0 | Go `/metrics` |
| BFF partial timeout | 2 | 0 | 云性能 observability |
| market_pulse p95 | 197ms | 显著下降 | 云性能脚本 |
| priority_board p95 | 160ms | 显著下降 | 云性能脚本 |
| 热聚合 DB 往返 | 待测 | 受控上界 | 慢日志/查询计数测试 |

## 7. Verification Commands
```bash
# 后端回归（每批合入前全绿）
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
# 驱动冒烟（G2）
cd backend && .venv/bin/python -c "from app.core.database import ping_database; ping_database(); print('db-ok')"
cd backend && .venv/bin/python -m alembic upgrade head
# 性能对比（M0 与每批后各跑一次，贴对比）
./scripts/<云性能脚本>.sh  # 取 monitor_bff/market_pulse/priority_board p95 + observability
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" $BASE/metrics | rg "local_quote_cache|provider_|bff_"
# Go 指标
docker compose -f docker-compose.mysql.yml exec go-market-read-service wget -qO- 127.0.0.1:8092/metrics | rg "market_read"
```

## 8. Rollback
- G1：预热集合扩展可配置上限回退到 200；覆盖率 SLA 仅告警，不阻断。
- G2：驱动回退 `mysql+mysqldb://`→`mysql+pymysql://`（保留 PyMySQL 依赖）；索引迁移可 downgrade。
- G3：请求隔离纯读改造可回退；async provider 客户端用开关回退同步；analytics-worker 从 compose 摘除不影响主链路。
- 每批独立、可单独回退；无业务语义变更，回退无数据风险。

## 9. Definition Of Done
- 行情 Redis 命中率 ≥90%、market-read MySQL 回退降 ≥80%、unresolved=0、BFF timeout=0；market_pulse/priority_board p95 较基线显著下降（贴云性能对比）。
- DB 驱动切 mysqlclient(C) 且冒烟/迁移/全量 pytest 绿；热聚合 N+1 修复且有查询次数上界测试。
- 热端点外部源不可达仍可用（只读缓存/物化）；外部拉取仅在 worker 异步。
- 未换主框架、未引新语言、未做 async 全量重写；业务语义/口径不变。
- analytics-worker 上线卸载重扫描（引用 P1-D1）；合入前 `pytest backend/tests` 全绿。
```
