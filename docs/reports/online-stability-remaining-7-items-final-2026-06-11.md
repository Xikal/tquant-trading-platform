# 线上稳定性 7 项收尾执行报告

- 检查时间：2026-06-11 21:42-22:25 CST
- 服务器：`ubuntu@43.143.243.97`，远端目录 `/home/ubuntu/gupiao-upload`
- 域名：`https://weisilianghua.cloud`、`https://www.weisilianghua.cloud`
- 直连入口：`http://43.143.243.97:18090`、`https://43.143.243.97`
- 本地分支：`codex/phase4-phase5-architecture`
- 执行前提交：`f6313b0e docs: record online stability authorization gates`
- 最终提交：本报告随本轮最终提交一并入库，最终 hash 以 `git log -1 --oneline` 为准
- 旧前端归档标签：`archive/frontend-retired-2026-06-11`

## 结论

当前线上服务通过 IP 入口可用，`/readyz` 正常，核心容器健康；域名入口从当前外部网络访问仍返回 `Recv failure: Connection reset by peer`，属于当前最大可用性风险。最大资源瓶颈是 MySQL 内存长期贴近 `1GiB` 容器上限，其次是 runtime-worker/scheduler 在任务周期内存在高 CPU/内存波动。

本轮执行过授权写操作：线上部署、Docker builder/dangling image 清理、远端旧 `frontend/` 源码备份后删除、本地旧 `frontend/` 物理删除与脚本迁移。未执行数据库清理写入、未改线上 `.env`/nginx/MySQL 配置、未手工 `docker restart/down/up`、未改 `strategy_policy.py`、未改变 `production_score` 或 priority board 排序口径。

## 7 项状态

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 线上部署 | 完成但有域名风险 | `docs/reports/online-stability-deploy-2026-06-11.log`；部署健康通过，脚本末尾 IP HTTPS 默认验证曾超时，后续独立 IP HTTPS `/readyz` 为 200 |
| 部署后验证 | 完成 | IP HTTP/HTTPS 首页、`/readyz`、主要 `/next/*` 页面 200；受保护 API 返回 401，历史/不存在接口返回 404 |
| 稳定性观察 | 完成短窗观察，未覆盖完整交易时段 | `docs/reports/online-stability-observation-2026-06-11.log`；3 轮约 6 分钟样本，容器保持 healthy |
| 历史 paper 任务清理 | 无需写入 | `paper_ledger_reconcile_preview`、`paper_review_report` 非终态失败/排队/重试数量为 0 |
| 线上旧资源清理 | 完成 | `docs/reports/online-stability-cloud-cleanup-2026-06-11.log`；根盘从约 63% 降到 56%，未清 Docker volume |
| 旧 `frontend/` 物理删除 | 完成 | 本地 `git ls-files frontend` 为 0，目录 absent；远端 `frontend_remote=absent`，备份 `backups/legacy-frontend-retired-20260611-222238.tgz` |
| Git 提交 | 完成 | 本报告、执行日志、旧 `frontend/` 删除和脚本迁移已随最终提交入库 |

## 服务总览

| 组件 | 当前状态 | 风险 |
| --- | --- | --- |
| app / FastAPI | healthy，IP 入口可用 | 域名公网访问 reset |
| frontend-next / frontend-web | healthy，主要页面可渲染 | 无旧前端回滚入口，仅保留归档标签和远端备份 |
| MySQL | healthy，连接正常 | 内存 `1000MiB / 1GiB`，P1 |
| Redis | `PONG`，`evicted_keys=0` | 低 |
| runtime-worker | healthy | 观察到 `523-768MiB / 768MiB` 波动，外部行情源失败会放大压力 |
| runtime-scheduler | healthy | 任务周期可达高 CPU，需继续观察 |
| Go workers | healthy | market-read 日志有外部源失败告警 |

## 资源快照

| 指标 | 结果 |
| --- | --- |
| uptime/load | `up 3 days, 11:08`，load `1.37, 1.18, 1.69` |
| 内存 | `3723M total / 3071M used / 651M available` |
| swap | `1987M total / 538M used` |
| 根盘 | `/dev/vda2 59G used 32G avail 25G use 56%` |
| inode | `11%` |
| Redis | `used_memory_human=1.74M`，`connected_clients=7`，`evicted_keys=0`，`db0 keys=642` |

## 容器状态

| 容器 | 状态 | 最新资源样本 |
| --- | --- | --- |
| `tquant-app-mysql` | healthy | `0.12%`，`311.4MiB / 768MiB` |
| `tquant-frontend-web` | healthy | `0.00%`，`3.32MiB / 128MiB` |
| `tquant-go-bff-gateway` | healthy | `0.00%`，`6.738MiB / 128MiB` |
| `tquant-go-market-read-service` | healthy | `0.00%`，`6.73MiB / 128MiB` |
| `tquant-go-scan-worker` | healthy | `0.00%`，`5.688MiB / 128MiB` |
| `tquant-mysql` | healthy | `26.11%`，`1000MiB / 1GiB` |
| `tquant-redis` | healthy | `0.64%`，`8.027MiB / 128MiB` |
| `tquant-runtime-scheduler-mysql` | healthy | `0.00%`，`424.5MiB / 640MiB` |
| `tquant-runtime-worker-mysql` | healthy | `80.36%`，`523.6MiB / 768MiB` |

## HTTP / API 验证

| 入口 | 结果 |
| --- | --- |
| `http://43.143.243.97:18090/` | 200，约 0.05s |
| `https://43.143.243.97/readyz` | 200，约 0.11s |
| `https://weisilianghua.cloud/readyz` | 000，`Recv failure: Connection reset by peer` |
| `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/analysis`、`/next/backtest`、`/next/data`、`/next/settings` | IP 入口均 200；`/next/backtest` 当前按新前端退役策略重定向到行动台 |
| `/api/monitor/snapshot`、`/api/screeners/low-buy/priority-board`、`/api/settings` | 未登录外部访问为 401，符合保护预期 |
| `/api/monitor`、`/api/priority-board`、`/api/backtest` | 404，符合当前实际路由状态 |

## 数据库与任务

| 项目 | 结果 |
| --- | --- |
| RuntimeTask 状态 | `cancelled=28`，`failed=1910`，`queued=4`，`running=1`，`succeeded=43821` |
| paper 非终态任务 | `0`，因此未执行 DB 清理写入 |
| MySQL | `Threads_connected=11`，`Threads_running=3`，`Max_used_connections=16`，`Slow_queries=13`，`max_connections=120`，`innodb_buffer_pool_size=536870912` |
| 历史失败任务 | 主要为部署前历史失败记录；观察窗口内失败总数未增长 |
| 外部行情源 | 日志中仍有 EastMoney/AkShare/go-market-read 请求失败或降级告警 |

## 前端可用性

| 验证 | 结果 |
| --- | --- |
| Playwright 线上页面检查 | IP 入口主页面无白屏、无 chunk 404、无 page error |
| 本地 `frontend-next` API/type/lint/test/build | 通过：`api:check`、`lint`、`131 passed`、生产构建通过 |
| 本地 Playwright smoke | `8 passed`；无后端时 Vite proxy 出现预期 `ECONNREFUSED`，页面壳仍渲染 |
| 旧前端 | 本地与远端源码目录均已删除；发布路径只保留 `frontend-next` |

## 问题分级

### P0

无。IP 入口当前可用，核心容器 healthy，未发现数据损坏、交易策略语义变更或服务整体不可用。

### P1

1. 域名公网访问 reset
   - 证据：`https://weisilianghua.cloud/readyz` 返回 `Recv failure: Connection reset by peer`；IP HTTPS `/readyz` 为 200。
   - 影响：用户通过正式域名访问会失败或不稳定；IP 入口仍可用。
   - 根因判断：更像域名解析、CDN/安全组、TLS SNI、nginx server_name 或证书链路径问题；部署脚本远端 loopback SNI 通过，说明容器内服务本身不是唯一根因。
   - 建议：单独授权后检查 DNS、443 安全组、nginx `server_name`/证书、云厂商防护策略，并做外网多点 curl。

2. MySQL 内存贴近容器上限
   - 证据：`tquant-mysql 1000MiB / 1GiB`；稳定性样本中也多次接近 99%。
   - 影响：高峰期可能触发 OOM、连接抖动、慢查询上升，影响核心读写和任务队列。
   - 根因判断：1GiB 限制偏紧，`innodb_buffer_pool_size=512MiB`，运行期缓存和连接开销叠加。
   - 建议：单独授权后评估提高 MySQL memory limit、调整 buffer pool/连接池、慢查询索引优化。

### P2

1. runtime-worker / scheduler 任务周期资源波动
   - 证据：runtime-worker 观察到 `767.9MiB / 768MiB` 峰值，后续仍有 `523.6MiB / 768MiB` 和高 CPU 样本；scheduler 曾出现高 CPU。
   - 影响：行情刷新、低吸榜物化、推荐榜/priority board 物化可能在外部源异常时延迟。
   - 根因判断：外部行情源失败重试、批量刷新和物化任务叠加。
   - 建议：优化行情源超时/退避、批量大小、任务互斥与内存上限；需单独变更计划。

2. 外部行情源失败告警持续
   - 证据：EastMoney/AkShare/go-market-read 近期日志出现请求失败、HTML decode、batch failure。
   - 影响：实时价格/盘中市场刷新可能降级；历史低吸数据闭环当前仍通过。
   - 根因判断：第三方源稳定性和反爬/响应格式波动。
   - 建议：增强 provider fallback、缓存兜底、错误预算和可观测告警。

### P3

1. 历史 failed runtime_tasks 仍保留
   - 证据：`failed=1910`，多为历史失败；观察窗口未增长。
   - 影响：监控噪声和排障干扰。
   - 建议：另行授权后按任务类型、创建时间、终态归档策略清理或标记，不直接删除核心任务历史。

2. 完整交易时段稳定性尚未覆盖
   - 证据：本轮观察在 22 点附近完成，不覆盖 A 股盘中完整时段。
   - 影响：不能证明交易时段长时间运行无问题。
   - 建议：下一交易日执行 09:15-15:10 长窗观测，按 5-10 分钟采样 CPU/内存/任务延迟/HTTP 延迟/行情刷新。

## 已执行的写操作

- 线上部署：`./scripts/one_click_cloud_deploy.sh --scope all --full --host 43.143.243.97 --key /Users/j/Downloads/gupiao.pem`
- 线上旧资源清理：`APPLY=1 KEEP_BACKUPS=1 KEEP_REPORT_DIRS=1 PRUNE_DOCKER=1 STOP_SEPARATED_STACK=0 ./scripts/cloud_server_cleanup.sh`
- 远端旧前端删除：备份 `backups/legacy-frontend-retired-20260611-222238.tgz` 后删除 `/home/ubuntu/gupiao-upload/frontend`
- 本地旧前端删除：`git rm -r frontend`，并物理删除未跟踪 `frontend/` 产物
- 本地脚本/测试/文档迁移到 `frontend-next`

## 未执行的操作

- 未执行数据库清理写入：paper 非终态任务数量为 0。
- 未执行 `docker volume prune`、`docker image prune -a`、手工 `docker restart/down/up`。
- 未修改线上 `.env`、nginx、MySQL 配置。
- 未停止核心 runtime scheduler/worker、行情刷新、日线刷新、低吸榜/推荐榜/priority board/watchdog。
- 未改 `backend/app/services/low_buy/strategy_policy.py`。
- 未改变 `production_score`、priority board 排序和口径。
- 未恢复 `/paper`、`/next/paper` 或新增 `PAPER_RUNTIME_TASKS_ENABLED`。

## 下一步修复清单

| 优先级 | 事项 | 是否需授权 |
| --- | --- | --- |
| P1 | 修复域名公网 reset：DNS/安全组/nginx SNI/证书/云防护逐项排查 | 需要 |
| P1 | MySQL 内存与慢查询专项：提高 limit 或调参、检查慢 SQL 与索引 | 需要 |
| P2 | 行情源稳定性：超时、退避、fallback、缓存命中和告警阈值 | 需要 |
| P2 | runtime-worker/scheduler 资源治理：任务并发、批量大小、互斥、内存峰值 | 需要 |
| P3 | 历史 failed runtime_tasks 归档或降噪 | 需要 |
| P3 | 下一交易日完整时段稳定性观测 | 可只读执行 |
