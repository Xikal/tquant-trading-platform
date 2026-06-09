# 云服务器降本完整方案（2026-06-09）

> 性质：**只出方案，不改代码、不部署、不切流、不删旧前端**。所有改动点均为待执行规格（含证据/预期/风险/回滚/验收）。
> 配套：`client-app-feasibility-and-cloud-resource-impact-2026-06-09.md`（已论证"客户端化不能显著降云"，本方案给出真正能降云的正交杠杆）、`platform-slimming-audit-2026-06-09.md`（进行中）。
> 依据：`docker-compose.mysql.yml`（13 服务 + 4 卷）实测 + 后端 worker/job/feature flag 盘点。
> 硬边界：不改 `strategy_policy.py`/`production_score`/priority_board/生产排序；不停核心数据刷新/物化/收盘发布；不动 MySQL 主写与生产事实源；strategy_engine 仍 shadow-only。

---

## 0. 一句话结论

**本平台云成本的主体是"常驻基础设施 + 单机实例规格"，与用户数无关。降云最有效的不是减请求，而是：① 给所有容器设资源上限并右调实例规格；② 把空闲常驻 Worker（analytics/backtest）改按需启动；③ 用 compact 模式右调 scheduler 频率；④ 数据/日志/备份治理。** 预计可在不动任何生产链路的前提下，把常驻内存与实例规格压下一档（典型可省 30–50% 实例成本）。**最高 ROI 是 L1（设上限+右调实例）与 L2（空闲 Worker 按需化），均为低风险。**

---

## 1. 现状与成本结构（实测）

`docker-compose.mysql.yml` 常驻 13 服务：

| 服务 | 角色 | 常驻? | 是否随用户量 | 实测配置/问题 |
|---|---|---|---|---|
| `mysql` | 生产事实源 | 是 | 否 | **无资源上限**；buffer pool 未按实例右调 |
| `redis` | 行情缓存 | 是 | 弱 | **无资源上限** |
| `app`（FastAPI/BFF） | API/聚合 | 是 | 是 | `APP_WORKERS=2`；**无上限** |
| `runtime-worker` | 数据刷新/物化 | 是 | 否 | 核心，必须留 |
| `runtime-scheduler` | 定时入队 | 是 | 否 | `COMPACT_MODE` 开关存在但默认关 |
| `backtest-worker` | 权威回测 | **是（但多数时间空闲）** | 否 | `restart: unless-stopped` 常驻；回测任务**按需/低频** |
| `analytics-worker` | DuckDB/Parquet 导出 | **是（但多数时间空闲）** | 否 | 常驻 + 2s 轮询；analytics 任务**门控/低频** |
| `go-bff-gateway` | BFF 聚合加速 | 是 | 是 | 轻量 |
| `go-market-read-service` | 行情读加速 | 是 | 弱 | 轻量 |
| `go-scan-worker` | 扫描加速 | 是 | 否 | 轻量 |
| `migration` | 一次性 | 否（`restart: no`） | — | OK |
| `mysql-backup` | 备份 | 周期 | 否 | 频率/保留期未优化 |
| 卷 `mysql_data/app_runtime_data/redis_data/mysql_backups` | 磁盘 | — | 否 | `backend/data` 本地 2.4G（parquet/duckdb） |

**三个关键事实**：
1. **全栈无资源上限**（`grep cpus:/memory:/deploy.resources` 命中 0）→ 容器可无序膨胀，实例只能按峰值买大。
2. **`backtest-worker`、`analytics-worker` 常驻但多数空闲**（重任务门控/低频）→ 白占常驻内存。
3. **成本随实例规格走，不随用户走**（少用户、p95 已不高）→ 降云=压常驻面+右调实例，不是优化请求。

---

## 2. 降云杠杆分级（按 ROI 与风险）

### L1 零风险：资源上限 + 实例右调 + 数据/日志/备份治理（**最高 ROI**）

| 动作 | 证据 | 预期降幅 | 风险/回滚 |
|---|---|---|---|
| **给每个容器设 `deploy.resources.limits`（cpus/memory）** | 当前全部无上限 | 防膨胀；实例可按"上限之和"右调，典型省 1 档规格 | 设过低会 OOM → 先按 `docker stats` 观测峰值×1.3 设；回滚=移除 limits |
| **MySQL 右调**：`innodb_buffer_pool_size` 按实例内存（如实例内存×40–50%）、连接数、`mysql-backup` 频率/保留（如日备 + 留 7 天） | buffer pool 未右调、备份未优化 | 内存可控；备份磁盘↓ | 备份保留期改回；buffer pool 调小仅影响缓存命中，不丢数据 |
| **日志治理**：compose 加 `logging.options.max-size/max-file`（如 10m×3） | 容器日志默认无限增长 | 磁盘↓、IO↓ | 回滚=移除 logging 配置 |
| **数据治理**：`backend/data` 旧 parquet/duckdb/24M 产物按保留期清理（配合进行中的瘦身把大报告出库） | `backend/data` 2.4G | 磁盘↓ 1–2G | 产物可由 analytics-worker 重生成；先 manifest 后清 |
| **APP_WORKERS 右调**：少用户下 2→按实测 QPS 设（1–2），结合 `gunicorn` 内存×worker 数 | `APP_WORKERS=2` | app 常驻内存↓ | 回滚=改回 2；注意 SEC2 限流口径随并发推导 |

### L2 低风险：空闲常驻 Worker 按需化（**高 ROI**）

| 动作 | 证据 | 预期降幅 | 风险/回滚 |
|---|---|---|---|
| **`analytics-worker` 改按需**：用 compose `profiles`（如 `--profile analytics`）默认不启动，仅在跑 24M 报告/导出时拉起；或合并入 `backtest-worker` 为单"重任务 worker" | 常驻 + 2s 轮询、任务门控/低频 | 省 1 个常驻 Python 容器内存（数百 MB 级） | 任务来时需先拉起 worker（编排/runbook）；回滚=改回 resident |
| **`backtest-worker` + `analytics-worker` 合并**为单多队列 worker（claim 两类队列） | 二者都空闲常驻 | 省 1 容器 | 高峰期回测与导出争用 → 少用户可接受；回滚=拆回两容器 |
| **`go-scan-worker` 按需/合并**：扫描低频时与 `go-market-read` 合并或 profile 化 | 3 个 Go 容器 | 省 1 容器（Go 轻，省得少） | 扫描时延略增；回滚=独立 |

### L3 低-中风险：调度频率与并发右调

| 动作 | 证据 | 预期降幅 | 风险/回滚 |
|---|---|---|---|
| **启用 `RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED=true`** | 开关已存在、默认 False | scheduler/worker 唤醒频率↓ → CPU 占空比↓ | compact 下部分刷新变慢 → 仅非交易时段/夜间开；回滚=置 False |
| **刷新频率右调**：非交易时段降低 `quote_cache/breadth/hourly` 等 loop 频率（盘后无需 30s 刷） | 多个 loop 固定频率 | 盘后 CPU/外网↓ | 不得影响盘中发布；按交易日历分时段；回滚=改回频率 |
| **研究/ML/因子 job 维持门控关**（已默认 False） | `config.py:95-97` 全 False | 已是零资源 | 维持；勿误开 |

### L4 架构级（仅建议，需评估）

| 动作 | 说明 | 风险 |
|---|---|---|
| **单机实例右降一档** | L1/L2 压下常驻后，把云主机规格降一档（如 4C8G→2C4G，按右调后峰值定） | 中：需观测窗口确认峰值不超 |
| **Worker 拓扑收敛** | runtime/backtest/analytics 收敛为"1 实时 worker + 1 按需重任务 worker" | 中：编排改动 |
| **冷热分离/对象存储** | parquet/报告/备份移对象存储，`backend/data` 只留热数据 | 中：读路径改造 |
| **Serverless/定时拉起**（可选） | 极低频的 24M 回测/导出用定时任务/临时实例跑完即销 | 中：编排复杂度 |

---

## 3. 量化目标（M0 → 目标）

> 实际数值需先用 `docker stats` 取 M0 基线；下表为右调方向。

| 指标 | M0（现状） | 目标 |
|---|---|---|
| 常驻容器数 | 10（除 migration/backup/一次性外） | **7–8**（合并/按需化 analytics+backtest±scan） |
| 容器资源上限 | 无 | **每容器有 cpus/memory 上限** |
| 常驻总内存 | 无上限/按峰值 | 上限之和较 M0 ↓ 30–50% |
| 云实例规格 | 当前档 | **右降一档**（L1/L2 后） |
| `backend/data` 磁盘 | 2.4G | ↓ 1–2G（产物治理/出库） |
| 容器日志磁盘 | 无限 | 受 `max-size/max-file` 约束 |
| 盘后 CPU 占空比 | 固定频率 | compact + 分时段后↓ |
| 生产链路/数据正确性 | 基线 | **不变**（硬门保护） |

---

## 4. 实施路线

- **Phase 1（零风险，先做）**：取 `docker stats` 基线 → 给所有容器设资源上限（峰值×1.3）→ MySQL buffer pool/备份右调 → 日志 `max-size/max-file` → `backend/data` 产物治理（配合进行中的瘦身出库）→ APP_WORKERS 右调。**不动任何代码逻辑，仅 compose/配置。**
- **Phase 2（低风险）**：`analytics-worker` profile 化按需启动；评估 `backtest-worker`+`analytics-worker` 合并为单重任务 worker；`go-scan` 按需/合并。补 runbook（重任务来时如何拉起）。
- **Phase 3（低-中风险）**：非交易时段启用 compact 模式 + 刷新频率分时段右调（按交易日历，不影响盘中发布）。
- **Phase 4（架构级，评估后）**：L1–L3 稳定运行一个观测窗口后，云实例右降一档；Worker 拓扑收敛；冷数据对象存储。

---

## 5. 验收标准

1. **生产不变（硬门）**：`/monitor→/playbook→/backtest→/paper→/settings` 闭环可用；priority board 排序/`production_score`/低吸语义/日期发布口径不变；后端策略 pytest 全绿；数据刷新/物化/收盘发布按时。
2. **资源下降可量化**：`docker stats` 常驻总内存较 M0 ↓；实例右降后峰值不超新规格；`backend/data`/日志磁盘↓。
3. **重任务仍可跑**：analytics/backtest 按需拉起后能正常完成 24M 报告/导出/权威回测（结果口径不变）。
4. **盘中无回退**：交易时段刷新频率与发布时延不受 compact/分时段影响。
5. **回滚可行**：每项均可独立回退（见下）。

---

## 6. 风险与回滚

| 杠杆 | 回滚方式 | 生产保护 |
|---|---|---|
| 资源上限 | 移除 `deploy.resources` | 先按峰值×1.3 设，OOM 即上调 |
| MySQL 右调 | 改回 buffer pool/备份配置 | 仅缓存/备份，**不丢数据**；主写不动 |
| 日志限制 | 移除 logging 配置 | 无 |
| 数据治理 | 从 manifest/对象存储重拉或 worker 重生成 | 先 manifest 后清，热数据不动 |
| analytics/backtest 按需化 | 改回 `restart: unless-stopped` 常驻 | **不改任务逻辑/不改回测口径**，仅启动方式 |
| compact/频率右调 | 置 `COMPACT_MODE=false`/改回频率 | 仅非交易时段，盘中不动 |
| 实例右降 | 升回原规格 | 需观测窗口确认 |

**绝对不动**：`strategy_policy.py`、生产排序、`production_score`、priority board、低吸生产语义、paper 账本写、MySQL 主写、daily bar/quote cache/物化/收盘发布、核心 `runtime-worker`/`runtime-scheduler`、`go-bff/go-market-read`、OpenAPI 契约。

---

## 7. 结论与优先级

- **最高 ROI、立即可做（L1）**：给所有容器设资源上限 + MySQL/备份/日志/数据治理 + APP_WORKERS 右调 → 防膨胀、压常驻、为实例右降铺路。**零生产风险，纯 compose/配置。**
- **次高 ROI（L2）**：`analytics-worker`/`backtest-worker` 空闲常驻 → 按需化/合并，省 1–2 个常驻容器内存。
- **稳态优化（L3）**：compact 模式 + 盘后分时段降频。
- **最终（L4）**：观测窗口后**云实例右降一档**——这是"显著降云"的落点。
- **不要指望客户端化降云**（已论证）；**真正降云=压常驻面 + 右调实例规格 + 数据治理**，与客户端化正交。

**预计效果**：在不动任何生产链路前提下，L1+L2 压下常驻内存后实例右降一档，**典型可省 30–50% 云主机成本**；磁盘随产物治理与日志限制进一步下降。

---

## 交付说明（合规）
- 未修改任何代码；仅新增本报告。
- 未部署、未切流、未删旧前端、未改生产策略/排序/`production_score`。
- 进行中的"平台瘦身"改动未被回滚。
