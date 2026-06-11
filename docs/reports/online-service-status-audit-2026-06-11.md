# 线上服务状态审计报告（2026-06-11）

## 0. 检查边界

- 检查时间：2026-06-11 20:13-20:36 +08:00
- 服务器：`VM-0-17-ubuntu`，`ubuntu@43.143.243.97`
- 域名：`https://weisilianghua.cloud`、`https://www.weisilianghua.cloud`
- 直连入口：`http://43.143.243.97:18090`
- 远端项目目录：`/home/ubuntu/gupiao-upload`
- 本地项目：`/Users/j/Documents/gupiao`
- 本地 git 状态：开始前 `git status --short` 有 4 个既有未提交文件；结束前再次执行为 clean（未改代码）。既有脏文件在部署过程中已由用户侧流程处理，本轮没有回滚、清理或覆盖。
- 参考资料：`AGENTS.md`、`docs/engineering-conventions.md`、`PRODUCTION_RUNBOOK.md`、`docs/operations/deployment-topology-runbook.md`、`docs/operations/worker-runbook.md`、近期资源/部署/性能报告。

本轮只执行只读检查和本地报告写入。未执行部署、切流、重启、清理、配置修改、数据库写入或策略语义变更。

## 1. 总体结论

| 项 | 结论 | 证据 |
|---|---|---|
| 当前线上是否可用 | 部分可用，但不稳定 | 最终 `/healthz`、`/readyz` 本机探针恢复 200；但验证期间 `/readyz` 连续 12s 超时，MySQL/runtime-worker 发生 OOM 重启 |
| 影响功能的问题 | 有 | 后台低吸物化任务持续失败；市场外部行情源失败；BFF/策略 workspace 出现 timeout；公网域名在本地验证端持续 `ECONNRESET` |
| 最大资源瓶颈 | 内存和 MySQL/runtime-worker 容器内存上限 | MySQL 多次 cgroup OOM；runtime-worker 多轮接近 768MiB 上限；Swap 仍 626-885MiB |
| P0/P1 | 有 P1，暂未证实 P0 | 20:29 MySQL OOM 重启导致 DB 连接丢失、worker 任务失败；最终自动恢复但长稳风险高 |
| 本轮是否执行写操作 | 未执行线上写操作 | 未运行 restart/up/down/prune/配置修改/DB 写；仅新增本地报告文件 |

## 2. 服务总览

| 服务/入口 | 状态 | 风险 |
|---|---|---|
| `app` / `tquant-app-mysql` | 最终 running healthy | 稳定性采样早期 unhealthy，曾因 DB/连接池压力导致 `/readyz` 超时 |
| `mysql` / `tquant-mysql` | 最终 running healthy | P1：验证期间 cgroup OOM kill，restart count 7 -> 8 |
| `redis` | running healthy | Redis 自身正常，无 eviction |
| `runtime-worker` | 最终 running healthy | P1：restart count 7 -> 8；内存最高 99.18%-99.97% |
| `runtime-scheduler` | 最终 running healthy | 采样期间曾 unhealthy，行情源失败日志持续出现 |
| Go BFF / market-read / scan-worker | running healthy | BFF remote circuit short-circuit=1，partial source timeout 有累计 |
| `frontend-web` 分离栈 | running healthy | 公网 nginx 主入口仍代理 18090，分离栈属于冗余验证栈 |
| `analytics-worker` | exited | 符合“按需”预期，但 heartbeat stale；历史 Exited(137) 需留意 |

## 3. 线上容器状态表

最终状态（20:35:58 +08:00）：

| 容器 | 服务 | 状态 |
|---|---|---|
| `tquant-app-mysql` | `app` | Up 22 minutes healthy |
| `tquant-mysql` | `mysql` | Up 6 minutes healthy |
| `tquant-redis` | `redis` | Up 2 days healthy |
| `tquant-runtime-worker-mysql` | `runtime-worker` | Up about 1 minute healthy |
| `tquant-runtime-scheduler-mysql` | `runtime-scheduler` | Up 6 hours healthy |
| `tquant-go-bff-gateway` | `go-bff-gateway` | Up 22 hours healthy |
| `tquant-go-market-read-service` | `go-market-read-service` | Up 22 hours healthy |
| `tquant-go-scan-worker` | `go-scan-worker` | Up 22 hours healthy |
| `tquant-frontend-web` | `frontend-web` | running healthy, separated stack only |
| `tquant-analytics-worker-mysql` | `analytics-worker` | exited, on-demand/stale |

重启计数重点：

- `tquant-mysql restart=8`，20:29:03/20:29:06 发生 cgroup OOM kill。
- `tquant-runtime-worker-mysql restart=8`，20:29 后跟随重启。
- `tquant-app-mysql restart=0`，但采样期间 healthcheck 曾 unhealthy。

## 4. 资源占用

| 指标 | 结果 | 判断 |
|---|---:|---|
| CPU | 4 vCPU | 采样期间 load 最高 9.61，后降至 1.82 |
| 内存 | 3723MiB total | 低余量，最终 available 906MiB；验证中最低 available 360MiB |
| Swap | 最终 626MiB / 1987MiB | 仍偏高；验证中 371MiB -> 627MiB 后又回到 626MiB |
| 根分区 | 35G / 59G，62% | 暂无磁盘满风险 |
| inode | 500K / 3.8M，14% | 正常 |
| Docker images | 14.71GB，11.86GB reclaimable | 可优化但需授权清理 |
| Docker build cache | 8.955GB，3.404GB reclaimable | 可优化但需授权清理 |
| MySQL 数据库 | `t_quant` 约 1452.06MiB | 正常量级 |
| MySQL binlog | 多个 256MiB 级 binlog | 磁盘暂可承受，继续按 3 天保留观察 |

关键容器资源：

| 容器 | 观测峰值/最终 | 风险 |
|---|---|---|
| `tquant-mysql` | 多轮 99%+，最终 863MiB/1GiB | OOM 已发生，P1 |
| `tquant-runtime-worker-mysql` | 最高 99.18%-99.97%，最终 767.8MiB/768MiB | 极高 OOM 风险 |
| `tquant-app-mysql` | 约 440-491MiB/768MiB | 中等 |
| `runtime-scheduler` | 约 313-365MiB/640MiB | 中等 |

## 5. HTTP/API 验证结果

| 路径 | 结果 | 说明 |
|---|---|---|
| `http://127.0.0.1:18090/healthz` | 200，约 3-5ms | 应用进程活着 |
| `http://127.0.0.1:18090/readyz` | 初期连续 12s 超时，后恢复 200/3-6ms | 稳定性不达标，和 MySQL OOM/连接池压力吻合 |
| `https://43.143.243.97/readyz` | 200，约 90-107ms | IP HTTPS 可达 |
| `https://weisilianghua.cloud/readyz` | 服务器内测 200，本地外部 3/3 `ECONNRESET` | 域名公网可达性异常，疑似网络/CDN/SNI/安全策略差异 |
| `/`、`/next/*` | 内网/远端 curl 200 | 新前端入口存在 |
| `/api/monitor/snapshot` | 401 | 需要登录，符合保护预期 |
| `/api/bff/v1/workspace/monitor` | 401 | 需要登录，符合保护预期 |
| `/api/screeners/low-buy/priority-board` | 401 未登录；登录态访问日志显示 200 | 实际 priority board 路径正常 |
| `/api/priority-board` | 404 | 该路径不是当前实际接口 |
| `/api/paper/summary` | 404 | 该路径不是当前实际接口 |
| `/api/runtime-tasks/summary` | 管理 token 下 200 | 队列可读，显示失败堆积 |
| `/metrics` | 管理 token 下 200 | 暴露 runtime/BFF/provider/cache 指标 |

## 6. 数据库与 Redis

MySQL：

- `Threads_connected=12`、`Threads_running=4`、`Max_used_connections=15`，连接数本身未打满。
- `Slow_queries=1129`，慢查询累计较多。
- `innodb_buffer_pool_size=512MiB`，容器内存限制 1GiB。
- 20:29:03 `mysqld` 被 cgroup OOM kill；日志显示后续 worker 出现 `Lost connection to server during query` 和 `Can't connect to server on 'mysql' (115)`。

Redis：

- `PONG`
- `used_memory_human=1.28M`，`used_memory_peak_human=14.37M`
- `connected_clients=4`
- `evicted_keys=0`
- `db0:keys=8`

Redis 不是本轮瓶颈。

## 7. 后台任务状态

管理接口最终结果：

- `queued=4`
- `running=1`
- `failed=1908`
- `succeeded_recent=2479`
- `longest_wait_seconds=106375`
- `oldest_queued_at=2026-06-10T07:01:31`

失败任务集中：

| 类型 | 数量 | 说明 |
|---|---:|---|
| `low_buy_materialization_refresh` | 851 | 当前仍有失败重试，影响低吸/推荐榜物化完整性 |
| `monitor_snapshot_refresh` | 584 | 可能影响 monitor 快照新鲜度 |
| `a_key_level_materialization_refresh` | 457 | 历史失败，需清理/归因 |

近期明确错误：

- `low_buy_materialization_refresh incomplete: missing_strategies=[...]`，缺少 `breakout_support`、`classic_retrace`、`deep_pullback`、`ma_support` 等多策略结果。
- `EastMoney first spot page failed`、`AkShare stock spot fallback failed: Can not decode value starting with character '<'` 持续出现，说明外部行情源当前不稳定。
- `market provider call timed out: operation=fetch_quote latency_ms=4611`
- `bff workspace timed out source=strategy_tracking_items/strategy_meta/presets/recent_runs/verdict_thresholds`

## 8. 前端页面可用性

Playwright 未登录态检查：

- `/next/analysis`、`/next/backtest`、`/next/data`、`/next/settings` 能加载登录页并拉取 `/next/assets/*`，核心 chunk/CSS 返回 200。
- `/api/auth/me` 返回 401，符合未登录预期。
- 不稳定窗口内 `/`、`/next/monitor`、`/next/monitor/market`、`/next/paper`、`/next/strategy-tracking` 出现 `net::ERR_CONNECTION_CLOSED`，与 MySQL/runtime-worker 重启和公网 `ECONNRESET` 时间重合。
- 未执行登录/注册，不创建线上 smoke 用户，不写业务数据。

Nginx：

- `nginx -t` 成功，服务 active。
- 错误日志有 `conflicting server name "weisilianghua.cloud"` warning，存在重复 server block 风险。
- 本地外部访问域名 `https://weisilianghua.cloud` 连续 reset，但直接 IP HTTPS 正常；需要单独检查域名 server block/证书/SNI/安全策略。

## 9. 问题分级

### P1-1：MySQL cgroup OOM 导致数据库重启，进而造成服务不稳定

- 证据：20:29:03/20:29:06 kernel 日志 `Memory cgroup out of memory: Killed process ... mysqld`；`tquant-mysql restart=7 -> 8`。
- 影响：验证期间 `/readyz` 连续 12s 超时，worker 报 `Lost connection to server during query`，公网页面请求出现连接关闭。
- 根因判断：MySQL 1GiB 容器上限偏紧，运行时内存接近上限；同时 runtime-worker/调度任务和行情刷新造成数据库与内存压力。
- 建议修复：需要授权后评估 MySQL 内存上限与 buffer pool 配比，或降低并发/后台任务压力；先不要直接重启或调配置。

### P1-2：runtime-worker 内存贴近 768MiB 上限并发生重启

- 证据：稳定性采样中 runtime-worker 最高 99.18%-99.97%，restart count 7 -> 8。
- 影响：后台任务中断、队列运行任务失败或重试，低吸物化/行情刷新新鲜度受影响。
- 根因判断：盘后/部署后任务集中执行，Python worker 基线和任务峰值超过当前内存预算。
- 建议修复：需要授权后拆分/限流高内存任务，评估 worker memory limit，必要时暂停低优先级任务或按需化重任务。

### P1-3：公网域名 `weisilianghua.cloud` 外部访问 reset

- 证据：本地 3 次 `curl https://weisilianghua.cloud/readyz` 均 `Recv failure: Connection reset by peer`；同一 IP `https://43.143.243.97/readyz` 200；服务器内测域名 200。
- 影响：部分外部用户可能无法通过域名访问，虽然 IP HTTPS 可达。
- 根因判断：疑似 nginx 重复 server_name、SNI/证书或云安全策略/线路问题；需结合外部网络和 nginx server block 排查。
- 建议修复：需要授权后审查 nginx 站点文件，去重 server block，复核证书和云安全组/CDN/WAF；本轮未改 nginx。

### P1-4：低吸物化任务持续失败，影响推荐榜/低吸榜完整性

- 证据：`failed=1908`，其中 `low_buy_materialization_refresh=851`；日志显示 `missing_strategies=[...]`。
- 影响：低吸/推荐榜物化不完整，可能依赖缓存旧数据或缺少部分策略候选。
- 根因判断：多策略物化产出不全后被 worker 判定失败；外部行情失败和 DB 重启会放大失败率。
- 建议修复：先只读提取最近失败任务 payload/error，再定位是策略禁用、数据缺失还是外部源失败；修复需单独授权。

### P2-1：外部行情源连续失败和超时

- 证据：`EastMoney first spot page failed`、`AkShare stock spot fallback failed`、provider metrics `tquant_provider_failures_total=52/52`。
- 影响：实时价格、quote overlay、市场快照可能退化为缓存/历史数据。
- 建议：继续观察 provider 失败窗口；必要时授权后调整 provider fallback、限频或缓存策略。

### P2-2：BFF/策略 workspace 出现 partial timeout

- 证据：`bff workspace timed out source=strategy_tracking_items/strategy_meta/...`；metrics 中 `tquant_bff_partial_source_failures_total` 多项 timeout。
- 影响：登录态策略页或监控聚合可能部分数据缺失/加载慢。
- 建议：先压低后台压力后复测；若仍存在，再拆慢源。

### P2-3：Docker 镜像和 build cache 可回收空间较大

- 证据：Images 14.71GB，11.86GB reclaimable；Build Cache 8.955GB，3.404GB reclaimable。
- 影响：当前磁盘 62%，不是立刻故障；后续会增加部署风险。
- 建议：需要授权后执行受控 prune；本轮未清理。

### P3-1：分离 `frontend-web` 验证栈仍常驻

- 证据：`tquant-frontend-web` running，nginx 主入口仍代理 18090。
- 影响：资源占用很小，但增加拓扑复杂度。
- 建议：确认无用后按 runbook 授权停用；本轮未停。

## 10. 本轮未执行的写操作

- 未执行 `docker restart/down/up/stop/start`。
- 未执行 `systemctl restart`。
- 未执行 Docker prune、日志清理、磁盘清理。
- 未修改 `.env`、nginx、compose、数据库配置。
- 未写数据库、未创建用户、未登录造数据。
- 未部署、未切流。
- 未修改 `strategy_policy.py`。
- 未改变 `production_score`、priority board 排序或策略语义。

## 11. 下一步修复清单

需要用户授权后才能执行：

1. P1：进入维护窗口处理 MySQL/runtime-worker OOM。建议先做只读峰值复核，再评估 MySQL memory limit/buffer pool、runtime-worker limit、后台任务并发和低优先级任务暂停。
2. P1：排查域名 reset。检查 nginx enabled sites、重复 `server_name`、证书/SNI、云安全策略；修复前不要改 nginx。
3. P1：提取最近 `low_buy_materialization_refresh` 失败任务详情，定位缺失策略物化原因，避免直接重跑造成更大压力。
4. P2：在资源稳定后复测 monitor BFF / priority board p95，对比历史目标 `<=500ms`。
5. P2：授权后清理 Docker build cache/images，或先导出资源报告后按 runbook prune。
6. P3：确认 `frontend-web` 分离栈无对外流量后，按授权停用验证栈。

建议继续观察：

- 至少 2 小时：`docker inspect restart`、`free -m`、`/readyz`、`runtime_tasks`。
- 一个交易日：scheduler enqueue、quote cache refresh、priority board materialization、收盘发布。
- 24 小时：MySQL OOM 是否复发、Swap 是否持续上升、外部行情源失败率是否恢复。

