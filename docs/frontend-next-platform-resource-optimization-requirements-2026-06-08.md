# frontend-next 与平台资源优化统一需求文档（2026-06-08）

状态：需求文档，待排期执行
适用范围：`frontend-next/`、平台运行资源、MySQL 运维、Analytics/DuckDB/Parquet 分层、部署性能门禁
来源文档：`docs/reports/frontend-next-optimization-plan-2026-06-07.md`，并合并 2026-06-08 云服务器 MySQL/binlog/资源盘点结论
默认结论：不替换 MySQL，先不加机器；采用“前端轻量化 + 单机资源硬上限 + MySQL 在线事务瘦身 + DuckDB/Parquet 分析层分担 + Worker 降载 + 预构建部署”的组合方案。

## 1. 问题陈述

`frontend-next/` 已经在 JS 体积、框架运行时和 `/next/monitor` 请求合包上明显优于旧前端，但仍存在以下问题：

1. 个别页面仍未复制 `/next/monitor` 已验证的 BFF 合包模式，`/next/strategy-tracking` 请求数高、存在历史 422 风险。
2. `/next/paper` DOM 数较高，页面渲染成本和交互稳定性仍可优化。
3. CSS 总体积明显高于旧前端，存在 legacy 皮肤复刻债、重复样式和 `!important` 债。
4. ECharts、TanStack/vendor、低频图表 chunk 仍需确认完全懒加载和按需加载。
5. 单元/功能级测试覆盖低于旧前端，cutover 前还需要更强的功能级回归。
6. 云服务器内存和 swap 压力仍偏高，后台 worker、Web app、MySQL 同时常驻导致低配机器波动。
7. MySQL 曾因 binlog/slow log 占用过多磁盘，虽已清理到可用状态，但仍需制度化保留策略、备份策略和自动保护。
8. 历史行情、回测、策略跟踪快照等读多写少大数据仍留在 MySQL，长期会继续推高存储、备份、查询和部署风险。
9. 生产云服务器直接构建 Docker 镜像会重新生成约 6GB build cache，并造成磁盘和 I/O 抖动，影响上线期间性能验证。

本需求目标是把“前端优化”和“平台资源优化”合成一个统一项目，避免只优化页面但后端资源继续成为 cutover 或自用稳定性的瓶颈。

## 2. 当前基线

### 2.1 frontend-next 基线

来自 `docs/reports/frontend-next-optimization-plan-2026-06-07.md`：

| 指标 | 当前基线 |
| --- | ---: |
| JS 总体积 | 1162 KB raw / 380 KB gzip |
| CSS 总体积 | 233 KB |
| bundle budget | 1.25 MB，当前约 1,189,691 bytes |
| 首屏关键块 | 约 412 KB raw |
| ECharts chunk | 约 447 KB，独立 lazy chunk |
| `/next/monitor` | 约 2 API 请求，DOM 230 |
| `/next/paper` | 约 403 DOM，1967 ms |
| `/next/strategy-tracking` | 约 9 API 请求，1906 ms，历史 items 422 |
| CSS 健康 | 约 15.5k 行，`!important` 51 |
| screenshot parity | 8/9 页面 >= 0.85，analysis 历史低于阈值 |
| unit/e2e | unit 83，e2e 35 |

### 2.2 云服务器资源基线

2026-06-08 清理后当前状态：

| 指标 | 当前值 |
| --- | ---: |
| 根分区 | 59G 总量，32G 已用，26G 可用，55% 使用率 |
| 内存 | 3.6GiB 总量，约 3.0GiB 已用，约 620MiB available |
| Swap | 1.9GiB 总量，约 1.8GiB 已用 |
| Docker images | 约 9.5GB |
| Docker build cache | 约 6.0GB |
| Docker volumes | 约 11.3GB |
| MySQL 数据目录 | 约 11G |
| MySQL binlog | 已保留最近 3 天，自动过期 259200 秒 |
| MySQL slow log | 约 3.1G，待处理 |
| MySQL 全库备份 | `/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz`，135M，已校验 |

主要内存占用：

| 组件 | 当前量级 |
| --- | ---: |
| MySQL | 约 866MiB |
| Web app | 约 428MiB |
| runtime worker | 约 346MiB |
| runtime scheduler | 约 335MiB |
| backtest worker | 约 67-118MiB |
| analytics worker | 约 72-75MiB |
| Grafana + Prometheus | 约 75-90MiB |
| Go services | 每个约 2-8MiB |

## 3. 总体目标

1. 保持 MySQL 作为在线事务事实源，不迁移到 SQLite 或其他轻量库。
2. 把历史/分析/回测类大数据逐步迁到 DuckDB/Parquet 分析层。
3. 把 `frontend-next/` 主要页面统一收敛到 BFF 合包、虚拟化、懒加载和共享 UI 组件。
4. 降低 CSS、ECharts、首屏 chunk 和页面 DOM 成本。
5. 降低云服务器磁盘、内存和 swap 压力。
6. 把 binlog、slow log、Docker cache、部署备份纳入自动化运维策略。
7. 保持生产策略语义、生产排序、`production_score`、`priority_board` 口径不变。
8. 所有变更可分阶段回滚，不要求一次性重构或大迁移。
9. 在不加机器前提下完成单机容量治理：根分区长期 <60%，>70% 告警，>80% 阻断部署。
10. 在不牺牲线上性能前提下降低内存压力：Swap 长期 <20%，连续 >50% 触发排查；重任务不得挤占 Web/API。
11. 所有持续增长源必须有硬上限、保留周期、巡检报告和回滚说明，避免再次依赖人工临时清理。

## 4. 硬边界

1. 不修改 `strategy_policy.py`。
2. 不改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
3. 旧 `frontend/` 不作为本需求改造对象，除非另有 cutover 授权。
4. `frontend-next/` 不换栈：继续 SolidJS + TanStack + Lightweight Charts + ECharts 低频 adapter + Worker。
5. K 线继续用 Lightweight Charts；不得改回 ECharts。
6. Worker/WASM 只做显示层 filter/sort/derive/downsample，不做生产策略判断。
7. DuckDB/Parquet 只作为分析层和报告层，不作为生产交易事实源。
8. Web 主进程不得新增 24 个月回测、数据补齐、Parquet 导出、DuckDB 报告等重任务。
9. 禁止直接删除 MySQL `.ibd`、binlog 文件、Docker volumes。
10. 禁止用 PurgeCSS 或脚本批量删除 CSS 而不做截图/视觉验证。
11. 不在生产机器上直接做破坏性数据库迁移；所有清理先备份、再校验、再清理。
12. 不部署、不切流，除非用户单独授权。

## 5. 目标架构

```text
frontend-next
  ├─ BFF workspace queries
  ├─ shared/ui wrappers
  ├─ virtualized lists/tables
  ├─ lazy chart islands
  └─ worker-only display transforms

FastAPI Web
  ├─ light requests
  ├─ auth/permission/settings
  ├─ task submit/status
  └─ BFF payload assembly

MySQL online store
  ├─ user/session/auth
  ├─ settings/feature flags
  ├─ paper orders/trades/positions
  ├─ runtime tasks/events
  ├─ current read models
  └─ audit / rollback evidence

Redis / Go services
  ├─ hot quote cache
  ├─ BFF hot read
  └─ scan/market read fast path

Analytics layer
  ├─ Parquet datasets
  ├─ DuckDB query layer
  ├─ manifests
  └─ reports/artifacts

Workers
  ├─ runtime worker
  ├─ runtime scheduler
  ├─ backtest worker
  └─ analytics worker
```

## 6. 单机资源治理最终方案（不加机器）

本节为 2026-06-08 云服务器资源治理的最终口径：先不加机器，不通过一次性清理解决问题，而是把持续增长源全部纳入生命周期管理。目标是在当前单机上保持功能完整、性能不降、资源增长可控。

### 6.1 治理原则

1. 不加机器、不拆服务作为本阶段默认约束；若后续长期高 swap 仍无法通过限额和降载解决，再单独评估扩容。
2. 不靠手动清理作为长期方案；所有日志、缓存、部署包、数据库历史数据都必须有上限和保留周期。
3. 不做会影响功能和性能的激进操作：不直接 `swapoff`，不清 page cache，不随意降低 InnoDB buffer，不停监控服务，不删 Docker volume。
4. Web/API 优先，实时监控和行情缓存次优先，回测、分析、数据修复为低优先级任务。
5. 任何数据清理必须先备份、再校验、再清理；不得直接删除 MySQL `.ibd`、binlog 或 Docker volume。
6. 部署前必须有容量 gate；资源不达标时停止部署，不允许带风险继续上线。

### 6.2 资源硬上限

| 资源 | 当前问题 | 最终要求 |
| --- | --- | --- |
| 根分区 | binlog、slow log、build cache、旧备份会反复增长 | 长期 <60%，>70% 告警，>80% 阻断部署 |
| Swap | 4G 内存下 Web、MySQL、worker 同时常驻导致 swap 高 | 长期 <20%，连续 >50% 触发排查和低峰降载 |
| MySQL binlog | 曾保留 30 天导致二十多个 1G 文件 | 固化保留 3 天，配置写入 MySQL 持久配置 |
| MySQL slow log | 当前曾达到约 3.1G | 按天/大小轮转，单文件 <=256M，历史压缩保留 14 天 |
| Docker build cache | 生产机构建产生约 6G cache | BuildKit cache 上限 2G；生产优先 pull 预构建镜像 |
| Docker 容器日志 | 默认 json log 无业务级上限 | `max-size=50m`，`max-file=3` |
| systemd journal | 历史系统日志约 1.2G | `SystemMaxUse=300M`，`MaxRetentionSec=7day` |
| 部署归档 | 多个历史源码包/部署目录长期保留 | 生产机仅保留最近 3 个可回滚版本 |
| MySQL 历史快照表 | 历史行情、策略跟踪、回测快照持续推高热库 | 热库只留近期数据，历史转 Parquet/DuckDB |

### 6.3 单机落地路径

P0：容量上限固化。

1. 固化 `binlog_expire_logs_seconds=259200` 和 `max_binlog_size=256M`。
2. 为 MySQL slow log 增加 logrotate：`size 256M`、`rotate 14`、`compress`、`copytruncate`。
3. 为 Docker daemon 增加 json log 限额：`max-size=50m`、`max-file=3`。
4. 为 systemd journal 增加容量限制：`SystemMaxUse=300M`、`MaxRetentionSec=7day`。
5. 为 BuildKit 增加 `keepStorage=2GB` 或等价巡检清理策略。
6. 部署脚本只保留最近 3 个 release/backup。

P1：内存稳定性治理。

1. 按角色设置 Web、runtime worker、scheduler、backtest worker、analytics worker 的并发和连接池预算。
2. backtest/analytics/data repair 任务默认低优先级，在开盘高峰、部署、cutover 验证期间自动降并发或暂停新任务。
3. Web/API 不承担 24 个月回测、数据补齐、Parquet 导出、DuckDB 报告等重任务。
4. 禁止通过清 page cache 或直接 swapoff 伪造内存优化结果。

P2：数据库体积根治。

1. `daily_bar_snapshots`、`strategy_tracking_snapshots`、回测明细、复盘快照、运行日志型业务表建立热库保留窗口。
2. 历史数据导出到 Parquet，DuckDB 负责离线查询/复盘/报告。
3. 后端接口保持兼容，内部按日期或查询类型路由 MySQL 热库或 DuckDB/Parquet 冷数据。
4. 清理 MySQL 历史行前必须有 manifest、行数、日期范围、hash、恢复路径。

P3：部署和观测闭环。

1. 生产机不再默认承担重 build；优先使用本地/CI 预构建镜像，云端只 pull + restart。
2. 部署前检查 `/` 使用率、MySQL volume、binlog、slow log、Docker cache、swap；不达标则停止部署。
3. 部署后输出 `df -h /`、`free -h`、Docker 占用、MySQL 日志状态、`/readyz`、三轮 performance gate。
4. 每日生成资源巡检报告，异常项进入 open-items。

### 6.4 不加机器阶段的验收目标

| 指标 | 目标 |
| --- | ---: |
| 根分区 | 长期 <60%，部署期间 <75%，阻断阈值 80% |
| Swap | 长期 <20%，短期优化目标 <500MiB |
| Available memory | >800MiB，或给出单机不可达原因 |
| MySQL slow log | 单文件 <=256M，归档压缩保留 14 天 |
| binlog | 3 天保留，重启后配置不丢 |
| Docker build cache | <=2G，或部署前自动处理 |
| 部署版本 | 最近 3 个可回滚版本 |
| Web/API p95 | 不回退，通过 online performance gate |
| 平台功能 | 不影响 |
| 生产策略口径 | 不变 |

## 7. 功能需求

### R1. frontend-next strategy-tracking 请求合包

目标：把 `/next/strategy-tracking` 从多请求模式收敛到 BFF workspace 合包。

需求：

1. 新增或启用 strategy workspace query，优先走 `/api/bff/v1/workspace/strategy`。
2. 页面字段从 BFF payload 切片，不重复请求同源数据。
3. 保留旧多请求 fallback，但必须可观测、可关闭。
4. 修复或规避 `items` 422 参数契约问题，不能用假数据掩盖。
5. 统一 query key、staleTime、placeholderData，避免切换筛选时闪空。

验收：

| 指标 | 目标 |
| --- | ---: |
| API 请求数 | 9 -> <=2 |
| items 422 | 0 |
| 页面 p95 | 较基线下降 |
| 字段 hash/parity | 与旧多请求一致 |

### R2. frontend-next paper 虚拟化

目标：降低 `/next/paper` DOM 和渲染成本。

需求：

1. 持仓、委托、成交、绩效等长列表接入 `VirtualList` 或同等 shared UI wrapper。
2. 机甲组件保持 display/review 边界，不改变现有展示。
3. 虚拟化后仍需支持键盘、滚动、空态、加载态和截图验收。

验收：

| 指标 | 目标 |
| --- | ---: |
| DOM 数 | 403 -> <150 |
| paper 延迟 | 较 1967ms 明显下降 |
| paper 视觉 | 不回退 |

### R3. frontend-next CSS 无损瘦身

目标：降低 CSS 体积和维护债，不改变当前新前端视觉。

需求：

1. 扫描 legacy workspace、feature CSS、login CSS、primitives CSS 的未引用选择器。
2. paper 三源样式、strategy/backtest feature slice 与 legacy-workspace 重复规则合并去重。
3. `!important` 从 51 收敛到 <=25，优先处理 monitor-market。
4. CSS 入口保持清晰，禁止隐式双源覆盖。
5. 每次 CSS 删除必须有截图/visual consistency 证据。

验收：

| 指标 | 目标 |
| --- | ---: |
| CSS raw | 233KB -> <=180KB，最终阈值以扫描结果复核 |
| `!important` | 51 -> <=25 |
| 截图/视觉 | 9 页不回退 |
| CSS guard | 通过 |

### R4. ECharts 和首屏 chunk 收敛

目标：保证 ECharts 低频 lazy，降低首屏 raw。

需求：

1. 确认 K 线全部使用 Lightweight Charts。
2. ECharts 仅通过 chart island 懒加载，首屏不得预载。
3. 检查 `echarts/core` 按需注册，不引入全量包。
4. 检查 TanStack/vendor chunk 组成，能懒加载的表格/虚拟化/图表能力移出首屏。

验收：

| 指标 | 目标 |
| --- | ---: |
| 首屏 raw | 412KB -> <=350KB |
| ECharts 首屏加载 | 0 |
| JS budget | <1.25MB |

### R5. shared/ui 去重与请求治理

目标：降低维护成本，减少重复 UI wrapper 和重复请求。

需求：

1. `DataGrid` 纯别名改为 `DataTable`。
2. `StatusBadge`、`StatusPill`、`Tag` tone API 收敛。
3. 统一 Query 策略：热数据 staleTime、错误态、placeholder、重试策略。
4. 保持所有第三方默认样式通过 `frontend-next/src/shared/ui` wrapper 输出。

验收：

1. typecheck/lint/test 通过。
2. 页面视觉不回退。
3. DevTools 无重复 in-flight 请求。

### R6. frontend-next 功能级测试补齐

目标：把 cutover 前风险从 smoke 提升到功能级。

需求：

1. 补 strategy-tracking BFF 合包、筛选、分页、排序、错误态测试。
2. 补 paper 下单/撤单/暂停恢复/权限/风险事件功能级测试。
3. 补 analysis/playbook/backtest/data/settings 的核心流测试。
4. 补 401/403/422/503/502、Response body stream already read 回归测试。
5. parity 阈值纳入 CI gate，防视觉回归。

验收：

1. 新增测试只断言外部行为，不绑定实现细节。
2. `npm test -- --run`、`npm run e2e` 通过。
3. `screenshot:parity`、`visual:consistency` 通过。

### R7. MySQL 日志和备份制度化

目标：避免 binlog/slow log 再次把磁盘打满。

已完成事实：

1. 已做全库备份：`/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz`。
2. 已清 3 天前 binlog。
3. 已设置 `binlog_expire_logs_seconds=259200`。

后续需求：

1. 新增 MySQL 备份 runbook：备份、校验、恢复演练、保留周期。
2. 新增 slow log rotate/truncate 策略。
3. 增加磁盘阈值保护：磁盘 >80% 警告，>90% 禁止部署。
4. 增加 binlog/slow log 监控报告。

验收：

| 指标 | 目标 |
| --- | ---: |
| 根分区 | 长期 <70%，紧急阈值 <80% |
| MySQL volume | 可控，短期 <12G |
| binlog 保留 | 3 天 |
| slow log | 不超过 512M 或按日滚动 |
| 备份 | 可校验、可演练恢复 |

### R8. MySQL 在线事务瘦身

目标：保留 MySQL，但降低内存和连接压力。

需求：

1. 评估 `max_connections=300` 是否降到 80-120。
2. 评估 InnoDB buffer pool 在当前 3.6GiB 内存机器上的合理范围。
3. 按 Web、worker、scheduler、analytics、backtest 分角色调整连接池。
4. 慢查询持续采样，但不得无限增长日志。
5. 禁止把历史分析大查询直接放入 Web request path。

验收：

| 指标 | 目标 |
| --- | ---: |
| MySQL 常驻内存 | 明显低于当前约 866MiB，或有明确不可降原因 |
| Swap | <500MiB |
| `/readyz` | 正常 |
| online performance gate | 通过 |

### R9. DuckDB/Parquet 分析层分担

目标：把历史大数据从 MySQL 在线库迁到分析层。

第一批候选：

1. `daily_bar_snapshots`
2. `strategy_tracking_snapshots`
3. `key_level_snapshots`
4. `low_buy_result_snapshots`
5. 回测明细、策略报告、分析报告明细

需求：

1. 建立 Parquet 数据湖目录和 manifest：
   - `backend/data/analytics/parquet/daily_bars/`
   - `backend/data/analytics/parquet/strategy_tracking/`
   - `backend/data/analytics/manifests/`
2. 每次导出记录数据范围、行数、hash、源表、导出时间、质量状态。
3. MySQL 保留近期热数据；历史查询走 DuckDB/Parquet。
4. 回测输入优先读 Parquet，不再重复扫描 MySQL 大表。
5. 归档后清理 MySQL 旧数据必须先有校验报告和回滚说明。

验收：

| 指标 | 目标 |
| --- | ---: |
| Parquet 导出 | 可重复、可校验 |
| DuckDB 查询 | 可生成报告 |
| MySQL 大表 | 有保留窗口和归档策略 |
| 数据不足 | 显式 blocked，不静默成功 |
| 生产口径 | 不变 |

### R10. Worker 降载与启动策略

目标：降低常驻内存和 swap。

需求：

1. backtest worker 支持按需启动或低频运行窗口。
2. analytics worker 支持定时/按需执行，不必在所有自用场景常驻高频轮询。
3. runtime worker 和 scheduler 降低空转频率和并发。
4. 重任务窗口避开部署、开盘高峰和 cutover 验证。
5. 为不同 worker 增加资源预算和健康检查。

验收：

| 指标 | 目标 |
| --- | ---: |
| Swap | <500MiB |
| Available memory | >800MiB |
| Web p95 | 不回退 |
| runtime task | 不丢任务、不重复执行 |

### R11. 生产部署资源优化

目标：生产机器只运行，不承担重 build。

需求：

1. 引入预构建镜像流程：本地或 CI 构建，云端只 pull + restart。
2. 保留最近 1 个部署备份，旧备份自动清理。
3. Docker build cache 增加阈值策略：可用空间低于 10G 时自动清理。
4. deploy 前检查磁盘、swap、Docker cache、MySQL binlog/slow log。
5. deploy 后执行性能门禁，失败不切流。

验收：

| 指标 | 目标 |
| --- | ---: |
| 部署期间根分区 | 不超过 75% |
| Docker build cache | 可控，不阻塞部署 |
| online performance | 三轮通过 |
| rollback | 可执行 |

### R12. 观测与报告收敛

目标：前端性能、后端性能、数据库资源、部署资源统一看板/报告。

需求：

1. 扩展 `perf:compare` 或新增资源报告，输出：
   - 页面请求数
   - 页面 DOM
   - chunk/CSS 体积
   - API p95
   - MySQL volume/binlog/slow log
   - Docker images/cache/volumes
   - 内存/swap
2. `docs/reports/gupiao-cloud-performance-*.json` 继续作为线上性能证据。
3. 新增资源验收 Markdown 报告，避免 JSON 零散。

验收：

1. 每次优化前后都有 baseline/after。
2. 报告包含可复现命令。
3. 异常时明确阻断项和回滚动作。

## 8. 非功能需求

### 7.1 性能

1. `/next/strategy-tracking` 请求数 <=2。
2. `/next/paper` DOM <150。
3. CSS raw <=180KB，或给出不可降原因。
4. 首屏 raw <=350KB。
5. ECharts 不进入首屏。
6. online Go/Rust performance gate 三轮通过。
7. Web 主进程不做重计算。

### 7.2 稳定性

1. 任何重任务失败不得拖垮 Web。
2. 数据不足必须显式 blocked。
3. 任务必须有状态、进度、错误和重试。
4. 数据归档必须先导出、再校验、再清理。
5. 部署失败不得自动切流。

### 7.3 可维护性

1. 前端 UI 通过 shared/ui wrapper 输出。
2. 后端 API schema 以 OpenAPI 为事实源。
3. 大文件按 `docs/engineering-conventions.md` 拆分。
4. 报告/机器产物按 docs 规范归档。
5. 每个工作包独立可回退。

### 7.4 安全与权限

1. 写操作继续受 safe write contract、权限、审计、rollback 保护。
2. 数据清理命令必须可审计，不直接删生产数据文件。
3. 备份文件权限和保留策略需明确。
4. admin token/environment 复验仍是 cutover 前提。

## 9. 分阶段实施

### Phase A：资源止血与制度化

目标：把当前服务器资源压力制度化管住。

任务：

1. slow log 压缩备份 + truncate/logrotate。
2. binlog 保留 3 天配置固化进 Runbook。
3. Docker build cache 阈值清理脚本。
4. 部署备份保留策略。
5. 资源报告脚本：磁盘、内存、swap、Docker、MySQL volume。

验收：

1. 根分区 <60%。
2. slow log <512M 或按日滚动。
3. `readyz` 正常。
4. 不影响当前服务。

### Phase B：frontend-next P1 高 ROI 优化

目标：先解决请求数、DOM、CSS 三个最高 ROI 项。

任务：

1. R1 strategy-tracking 合包。
2. R2 paper 虚拟化。
3. R3 CSS 无损瘦身。

验收：

1. 请求数、DOM、CSS 指标达标。
2. `api:check/typecheck/lint/test/build/e2e/screenshot:parity/perf:compare` 全绿。
3. 视觉不回退。

### Phase C：MySQL 瘦身与 worker 降载

目标：降低内存和 swap。

任务：

1. 降 MySQL 连接和连接池预算。
2. 调整 app gunicorn worker 数。
3. backtest/analytics worker 按需或定时运行。
4. runtime worker/scheduler 空转降频。

验收：

1. Swap <500MiB。
2. Available memory >800MiB。
3. online performance gate 不回退。

### Phase D：DuckDB/Parquet 数据分层

目标：降低 MySQL 长期增长风险。

任务：

1. daily bars 导出 Parquet。
2. strategy tracking snapshots 导出 Parquet。
3. 建 manifest 和质量校验。
4. 历史查询双源：近期 MySQL，历史 DuckDB/Parquet。
5. 回测读取切到 Parquet 优先。

验收：

1. Parquet 导出/查询可重复。
2. MySQL 热数据保留窗口明确。
3. 历史查询正确。
4. 策略口径不变。

### Phase E：部署方式优化

目标：云服务器不再重 build。

任务：

1. 预构建镜像流程。
2. 云端 pull + restart。
3. deploy 前资源 guard。
4. deploy 后三轮性能门禁。

验收：

1. 部署期间磁盘不超过 75%。
2. build cache 不再成为线上风险。
3. cutover 前性能门禁稳定通过。

### Phase F：测试与验收收敛

目标：把所有优化纳入可重复验收。

任务：

1. 功能级 E2E 补齐。
2. 错误态/权限/rollback 测试补齐。
3. 前端性能、后端性能、资源报告统一。
4. 更新 acceptance/open-items/cutover runbook。

验收：

1. 自动化命令全绿。
2. 报告无互相矛盾状态。
3. cutover 仍需单独授权。

## 10. 验收命令

### 9.1 frontend-next

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run screenshot:parity
npm run perf:compare
```

### 9.2 backend / platform

```bash
cd /Users/j/Documents/gupiao
backend/.venv/bin/pytest backend/tests/test_database_url_driver.py \
  backend/tests/test_market_provider_contract.py \
  backend/tests/test_market_quote_cache_coverage.py \
  backend/tests/test_cloud_performance_script.py -q
python scripts/verify_go_rust_performance_acceptance.py
./scripts/quick_cloud_deploy.sh --verify-only --performance-verify --performance-rounds 3
git diff --check
git status --short
```

### 9.3 production resource checks

```bash
df -h /
free -h
sudo docker system df
sudo docker stats --no-stream
mysql -e "SHOW BINARY LOGS; SELECT @@binlog_expire_logs_seconds;"
du -sh /var/lib/docker/volumes/tquant-mysql_mysql_data/_data
```

## 11. 验收指标总表

| 领域 | 指标 | 当前 | 目标 |
| --- | --- | ---: | ---: |
| 前端 | strategy-tracking API 请求 | 9 | <=2 |
| 前端 | paper DOM | 403 | <150 |
| 前端 | CSS raw | 233KB | <=180KB |
| 前端 | `!important` | 51 | <=25 |
| 前端 | 首屏 raw | 412KB | <=350KB |
| 前端 | ECharts 首屏 | 独立 chunk，需复核 | 0 |
| 前端 | JS budget | <1.25MB | 继续绿 |
| 后端 | monitor BFF p95 | 约 30ms | <500ms |
| 后端 | priority board p95 | 约 103ms | <500ms |
| 后端 | watchlist signals p95 | 约 24ms | <600ms |
| 资源 | 根分区 | 55% | 长期 <60%，上限 <80% |
| 资源 | MySQL volume | 11G | 短期 <12G，长期可控下降 |
| 资源 | slow log | 3.1G | <512M 或按日滚动 |
| 资源 | Swap | 1.8G | <500M |
| 资源 | Available memory | 620MiB | >800MiB |
| 部署 | Docker build cache | 6G | 可控，不阻塞部署 |
| 数据 | Parquet manifest | 部分已有 analytics 能力 | 大表归档可复现 |

## 12. 风险与回滚

| 风险 | 防护 | 回滚 |
| --- | --- | --- |
| CSS 删除导致视觉回退 | 每页截图、visual consistency、逐条删除 | 回退对应 CSS commit |
| BFF 合包字段缺失 | payload hash、fallback 多请求 | flag 回多请求 |
| 虚拟化列表漏显示 | 功能级 E2E、滚动测试 | 回非虚拟渲染 |
| MySQL 参数过低导致连接不足 | 分角色压测、监控连接数 | 恢复原参数 |
| slow log/binlog 清理影响恢复 | 先备份、保留 3 天 binlog | 用全库备份 + binlog 恢复 |
| Parquet 归档漏数据 | manifest 行数/hash 校验 | 不清 MySQL 源数据 |
| worker 降载导致任务延迟 | 任务 SLA 和队列监控 | 恢复常驻 worker |
| 预构建镜像失败 | 保留旧部署脚本 | 回云端 build 但要求磁盘充足 |

## 13. 明确不做

1. 不把 MySQL 全量迁到 SQLite。
2. 不把 DuckDB 当在线事务库。
3. 不删除业务表文件。
4. 不直接删除 Docker volumes。
5. 不为了 CSS 体积牺牲当前新前端视觉。
6. 不把 K 线改回 ECharts。
7. 不绕过安全写契约、权限、审计和 rollback。
8. 不自动 cutover。

## 14. 交付物

1. `docs/operations/mysql-maintenance-runbook.md`：备份、binlog、slow log、恢复演练。
2. `docs/reports/platform-resource-baseline-2026-06-08.md`：资源 baseline。
3. `docs/reports/frontend-next-css-optimization-2026-06-08.md`：CSS before/after。
4. `docs/reports/frontend-next-performance-optimization-2026-06-08.md`：前端 O1-O10 before/after。
5. `docs/reports/platform-resource-optimization-2026-06-08.md`：MySQL/worker/Docker before/after。
6. `backend/data/analytics/manifests/*.json`：Parquet 导出 manifest。
7. 更新 `docs/frontend-next-cutover-runbook-2026-06-05.md`：新增资源门禁。
8. 更新 `PRODUCTION_RUNBOOK.md`：新增资源、备份、部署 guard。

## 15. 建议执行顺序

1. 先做 Phase A：slow log、logrotate、资源报告、Docker cache 阈值。
2. 并行做 Phase B：strategy 合包、paper 虚拟化、CSS 瘦身。
3. 做 Phase C：MySQL/worker 降载，解决内存和 swap。
4. 做 Phase D：daily bars 和 strategy tracking snapshots Parquet 归档。
5. 做 Phase E：预构建镜像，去掉线上重 build。
6. 最后做 Phase F：功能测试、报告收敛、cutover 前复验。

## 16. 最终 Definition of Done

1. `frontend-next` O1/O2/O3 核心指标达标。
2. CSS、首屏、ECharts、shared/ui 去重完成且视觉不回退。
3. MySQL binlog/slow log/备份策略自动化。
4. Swap 从当前约 1.8G 降到 <500M。
5. 根分区长期低于 60%。
6. 至少 `daily_bar_snapshots` 和 `strategy_tracking_snapshots` 有 Parquet 归档方案和 manifest。
7. 云服务器部署不再依赖重 build，或 build cache/磁盘保护足够稳定。
8. 三轮 online performance gate 通过。
9. 旧前端、生产策略语义、生产排序、`production_score`、`priority_board` 口径不受影响。
10. cutover 仍由用户单独授权。
