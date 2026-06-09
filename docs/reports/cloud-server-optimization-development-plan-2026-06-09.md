# 云服务器优化开发计划（2026-06-09）

> 来源报告：`docs/reports/cloud-server-optimization-plan-2026-06-09.md`
> 目标：把报告中的服务器资源问题整理成可落地、可验证、可回滚的开发与运维计划。
> 性质：开发计划与执行提示词；本文件不代表已经部署、不代表已经切流。
> 硬边界：不改 `strategy_policy.py`、不改变 `production_score`/priority board/低吸生产排序语义、不动 MySQL 主写数据、不停核心数据刷新发布。生产执行必须另行获得用户明确授权。

## 1. 已确认问题

### 1.1 CPU 不是瓶颈，内存和 Swap 是瓶颈

线上巡检确认服务器为 4 vCPU、约 3.7 GiB 内存、60 GiB 系统盘。CPU load 约 0.5，CPU 不紧张；内存已用约 3.1 GiB，Swap 已用约 1.7 GiB，说明当前卡顿主要来自内存过度承诺和换页。

需要解决的问题不是加 CPU，而是降低常驻内存、限制容器膨胀、减少无效常驻进程，并建立资源基线门禁。

### 1.2 当前公网入口仍走单体 app

当前 nginx 公网入口 `/` 和 `/api/` 仍代理到 `127.0.0.1:18090`，也就是 `tquant-app-mysql`。`docker-compose.separated.yml` 启动的 `frontend-web`、`backend-api`、`gateway` 也在运行，但公网主入口没有指向它们。

这说明分离栈目前属于验证栈或备用栈，继续常驻会占少量资源并增加运维复杂度。停掉分离验证栈是低风险动作，但前提是先确认 nginx 仍代理到 18090。

### 1.3 报告中 `APP_WORKERS 2 -> 1` 的收益需要修正

报告把 `APP_WORKERS 2 -> 1` 估算为约 200M 释放项，但线上进程命令实际显示 gunicorn 当前已经以 `-w 1` 运行。因此不能再把这个动作计入线上即时收益。

需要做的不是再次下调，而是：

- 统一 Dockerfile、compose、部署脚本里的 `APP_WORKERS` 默认值，避免本地配置仍显示 `${APP_WORKERS:-2}` 造成误判。
- 增加测试，确认少用户生产默认 worker 数为 1。
- 在资源报告中把 app 当前 worker 数列为证据项。

### 1.4 分离验证栈释放内存有限，但应清理运行态

分离栈实际内存大约 33 MiB，释放量不大，但它开放了 `18080/18091/18000`，并增加了容器和入口复杂度。若当前不正式切到分离栈，应停掉它；若要正式使用分离栈，应走单独 cutover 验收。

本计划默认先停冗余运行态，不做切流。

### 1.5 最大可释放项是 `runtime-scheduler`

线上 `runtime-scheduler` 约 470 MiB，是主要内存大头之一。报告提出合并 scheduler 到 worker 是正确方向，但这是代码与运行拓扑改动，不能直接用 ops 命令粗暴停掉。

必须先实现：

- feature flag 控制的嵌入式 scheduler。
- 单实例 leader/锁保护，避免重复入队。
- scheduler heartbeat 仍可被监控识别。
- 交易日、盘中刷新、收盘发布、latest data watchdog 回归验证。
- 先灰度运行一个交易日，再停止独立 scheduler。

### 1.6 `analytics-worker`/`backtest-worker` 按需化需要区分

`analytics-worker` 当前常驻但多数时候只用于低频 DuckDB/Parquet/24M 报告，适合改成 profile 或按需启动。

`backtest-worker` 虽然内存不大，但直接按需化会影响 `/backtest` 用户体验：用户提交回测后如果 worker 未运行，任务会排队但无人消费。除非先实现明确的“worker 未启用/任务排队/按需拉起”状态，否则不建议默认停 `backtest-worker`。

本计划建议：

- 第一阶段只把 `analytics-worker` 设计为可按需，并更新部署脚本和验收逻辑。
- `backtest-worker` 先保留常驻，后续再评估合并为“重任务 worker”。

### 1.7 Docker 日志与 BuildKit 已有部分治理脚本，但线上需补应用证据

仓库已有：

- `deploy/docker/daemon-resource.json`
- `deploy/buildkit/buildkitd-resource.toml`
- `deploy/systemd/journald-resource.conf`
- `scripts/install_platform_resource_limits.py`
- `scripts/collect_platform_resource_report.py`

因此不应重复造一套日志治理，而应扩展现有资源治理脚本，加入 swappiness、容器资源上限和分离栈状态采集。

## 2. 总体目标

1. 保持生产功能和策略语义不变。
2. 将 Swap 使用从约 1.7 GiB 降到接近 0，目标 `< 300 MiB`。
3. 将可用内存提升到 `> 1 GiB`。
4. 清理 Docker build cache，释放约 10 GiB 级磁盘。
5. 让所有常驻容器有明确内存/CPU边界，避免单个容器挤爆系统。
6. 停止不对外服务的分离验证栈，或在独立授权后正式切换。
7. 将 scheduler 合并改造成可灰度、可回滚的 feature flag，而不是一次性停容器。
8. 建立“基线 -> 改动 -> 对比 -> 回滚”的资源验收闭环。

## 3. 实施分期

### Phase 0：隔离与基线

执行前必须先做：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

保护已有未提交和未跟踪文件，不覆盖当前 `docs/reports/*` 瘦身报告、云资源报告和用户未跟踪文件。

本地只读检查：

```bash
rg -n "APP_WORKERS|runtime-scheduler|analytics-worker|backtest-worker|profiles|mem_limit|logging" \
  docker-compose.mysql.yml docker-compose.separated.yml scripts backend/tests docs
```

线上只读基线：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 '
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps
curl -fsS http://127.0.0.1:18090/readyz
free -m
df -h /
sudo docker system df
sudo docker stats --no-stream
sudo docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
'
```

产出：

- 新增或更新资源基线 JSON/MD。
- 明确当前 nginx 是否仍代理到 `18090`。
- 明确当前 app 实际 gunicorn worker 数。

### Phase 1：零风险运维治理规格

此阶段优先补代码化 runbook/脚本，不直接在线上执行，除非用户明确授权。

开发项：

1. 扩展 `scripts/collect_platform_resource_report.py`：
   - 采集 `vm.swappiness`。
   - 采集 Docker build cache。
   - 采集分离栈容器是否运行。
   - 采集 app gunicorn worker 数。
   - 采集常驻容器内存汇总。

2. 扩展 `scripts/install_platform_resource_limits.py`：
   - 继续保持 dry-run 默认。
   - 增加 swappiness 模板安装规格：`vm.swappiness=10`。
   - 输出明确回滚路径。
   - 不执行 `volume prune`，不动 MySQL 数据卷。

3. 更新 `scripts/cloud_server_cleanup.sh`：
   - 保持默认 dry-run。
   - `docker builder prune -f` 可作为安全清理项。
   - 禁止默认执行 `docker image prune -a`。
   - 增加“确认分离栈非公网入口后停 separated compose”的可选参数，例如 `--stop-separated-stack`。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_platform_resource_report.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_platform_optimization_readiness.py -q
```

### Phase 2：统一 app worker 默认值

问题：线上实际是 `-w 1`，但 `docker-compose.mysql.yml` 和 `docker-compose.separated.yml` 仍有 `${APP_WORKERS:-2}` 默认，容易造成错误估算或后续部署回到 2 workers。

开发项：

1. 将少用户生产默认值固化为 `APP_WORKERS: ${APP_WORKERS:-1}`。
2. 部署脚本和资源报告明确输出实际 worker 数。
3. 更新测试中对 `APP_WORKERS:-2` 的过期断言。
4. 保留通过环境变量升回 2 的能力。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_cloud_performance_script.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_platform_budget_verifier.py -q
```

### Phase 3：容器资源上限与日志上限

开发项：

1. 在 `docker-compose.mysql.yml` 中增加可配置资源边界，建议使用 Compose 兼容的 `mem_limit`、`memswap_limit`、`cpus`，并用环境变量控制：
   - app：默认 700M。
   - mysql：默认 768M。
   - runtime-worker：默认 768M。
   - runtime-scheduler：默认 640M，后续合并后移除。
   - redis：默认 128M。
   - Go 服务：默认 64M。
   - backtest-worker：默认 256M。
   - analytics-worker：默认 256M 或按需 profile 后不常驻。
2. 添加 `x-logging` 公共块或确认系统级 Docker daemon log 上限已应用。
3. 不给 MySQL 设置过低上限；先以实测峰值乘 1.3。
4. 添加 compose config 测试，防止资源限制丢失。

验收：

```bash
sudo docker compose -f docker-compose.mysql.yml config >/tmp/tquant-compose-config.yml
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_platform_resource_report.py \
  backend/tests/test_cloud_deploy_scripts.py -q
```

### Phase 4：`analytics-worker` 按需化，`backtest-worker` 暂不默认停

开发项：

1. 为 `analytics-worker` 增加 profile，例如 `profiles: ["analytics"]` 或 `["heavy"]`。
2. 更新部署脚本：
   - 默认部署不强制等待 `analytics-worker` healthy。
   - 增加参数 `--with-analytics-worker` 或 `--with-heavy-workers` 时才启动并验收 analytics。
   - 保留 analytics 依赖检查命令。
3. 更新 runbook：
   - 如何拉起 analytics-worker。
   - 如何补跑 24M 报告。
   - 跑完后如何关闭。
4. `backtest-worker` 本阶段保留常驻，避免破坏 `/backtest` 交互。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_database_url_driver.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_runtime_task_queue.py -q
scripts/run_platform_component.sh analytics-worker --print-command
```

### Phase 5：scheduler 合并灰度

这是最大收益项，也是最高风险项，必须 feature flag + 观察窗口。

开发项：

1. 新增环境变量：
   - `RUNTIME_WORKER_EMBED_SCHEDULER=false`
   - `RUNTIME_SCHEDULER_LEADER_LOCK_TTL_SECONDS=60`
2. 在 `backend/app/workers/runtime_worker.py` 中，当 flag 开启时启动 `start_runtime_background_jobs()`。
3. 增加 leader lock，避免多个 worker 或 scheduler 重复入队。
4. worker 内嵌 scheduler 时仍记录 `runtime-scheduler` heartbeat。
5. 独立 `runtime-scheduler` 容器默认仍保留，灰度时才停。
6. 监控接口必须能区分：
   - 独立 scheduler 运行。
   - worker 内嵌 scheduler 运行。
   - scheduler 缺失。

验收测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_runtime_worker_health.py -q
```

线上灰度验收需要用户另行授权，流程为：

1. 部署但默认不开启 flag。
2. 开启 `RUNTIME_WORKER_EMBED_SCHEDULER=true`。
3. 停止独立 `runtime-scheduler`。
4. 观察一个完整交易日。
5. 验证 quote cache、daily bar、materialization、latest data watchdog、收盘发布全部正常。
6. 异常时立即恢复独立 scheduler。

### Phase 6：线上执行与对比验收

只有用户明确授权“部署/执行线上优化”后才进入本阶段。

执行前：

```bash
cd /Users/j/Documents/gupiao
git status --short
npm --prefix frontend-next run build
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_platform_resource_report.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_independent_runtime_components.py -q
git diff -- frontend strategy_policy.py | wc -l
```

线上只读前后对比：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 '
free -m
df -h /
sudo docker system df
sudo docker stats --no-stream
curl -fsS http://127.0.0.1:18090/readyz
'
```

线上应用动作必须分批：

1. 只清 build cache、设置 swappiness、停非入口 separated 栈。
2. 验证 readyz、页面、资源。
3. 再部署 compose 资源上限。
4. 验证容器无 OOM、readyz 正常。
5. 再灰度 analytics profile。
6. 最后才考虑 scheduler 合并。

## 4. 回滚方案

| 改动 | 回滚 |
|---|---|
| Docker build cache 清理 | 无需回滚，后续构建自动生成 |
| 停 separated 栈 | `sudo docker compose -f docker-compose.separated.yml up -d` |
| swappiness=10 | 改回 `vm.swappiness=60` 并 `sysctl -p` |
| APP_WORKERS 默认 1 | 环境变量设置 `APP_WORKERS=2` 并重建/重启 app |
| mem_limit/cpus | 移除或上调限制后重启对应容器 |
| analytics profile | 去掉 profile 或用 `--profile analytics up -d analytics-worker` |
| scheduler 合并 | 关闭 `RUNTIME_WORKER_EMBED_SCHEDULER`，重启独立 `runtime-scheduler` |

任何回滚都不得执行：

- `docker volume prune`
- 删除 MySQL volume
- 修改 `strategy_policy.py`
- 修改生产排序/分数语义
- 清空 runtime task/策略数据

## 5. 验收标准

资源验收：

- `free -m`：Swap used `< 300 MiB`。
- `free -m`：available memory `> 1000 MiB`。
- `df -h /`：磁盘使用明显下降。
- `docker stats`：常驻内存总量下降，无容器触顶 OOM。
- `docker system df`：build cache 明显下降。

功能验收：

- `curl -fsS http://127.0.0.1:18090/readyz` 全 true。
- `/monitor`、`/playbook`、`/backtest`、`/paper`、`/settings` 可打开。
- 策略排序、`production_score`、priority board、低吸生产语义不变。
- 盘中 quote cache、daily bar、materialization、收盘发布按交易日逻辑正常。
- analytics 按需拉起后能完成依赖检查和任务消费。

边界验收：

```bash
git diff -- frontend strategy_policy.py | wc -l
git diff --check
```

## 6. 需要暂缓或需确认的事项

1. 不建议立即把 `backtest-worker` 默认停掉；它影响用户从 `/backtest` 提交任务后的消费能力。
2. 不建议把 scheduler 合并当成简单 compose 改动；必须先做 feature flag 和 leader lock。
3. 不建议执行 `docker image prune -a`；可能删除可用于快速回滚的旧镜像。
4. 不建议当前直接切到 separated 栈；它需要单独的前后端分离 cutover 验收。
5. `APP_WORKERS` 收益已不应计入当前线上优化，因为线上已经是 `-w 1`。

## 7. 可直接使用的执行提示词

```text
你在 /Users/j/Documents/gupiao 工作。请根据 docs/reports/cloud-server-optimization-plan-2026-06-09.md 和 docs/reports/cloud-server-optimization-development-plan-2026-06-09.md 落地“云服务器资源优化”开发任务。

硬边界：
1. 开始前必须执行 git status --short，保护已有未提交/未跟踪文件。
2. 不改旧 frontend/，不改 strategy_policy.py，不改变 production_score、priority_board、低吸生产排序和策略语义。
3. 不动 MySQL 主写数据，不执行 docker volume prune，不清空 runtime task/策略/模拟盘数据。
4. 本轮先做代码、脚本、runbook 和本地验证；不部署、不切流、不在线上执行清理，除非用户另行明确授权。
5. 若要操作线上，只允许按“基线 -> 单项动作 -> 验证 -> 可回滚”的顺序执行，并必须展示命令和结果。

必须先确认并修正报告假设：
- 线上 app 当前 gunicorn 已是 -w 1，因此 APP_WORKERS 2->1 不能再计入收益；需要把 compose/部署脚本/测试里的默认值统一为 1，并保留环境变量升回 2。
- separated 栈当前运行但公网 nginx 主入口仍代理 18090；默认只做停冗余栈的脚本规格，不做前后端分离 cutover。
- analytics-worker 可按需化；backtest-worker 暂不默认停，避免 /backtest 任务无人消费。
- runtime-scheduler 合并是最大收益项，但必须 feature flag + leader lock + heartbeat + 一个交易日观察，不能直接停容器。

开发任务：
1. 扩展 scripts/collect_platform_resource_report.py，采集 swappiness、Docker build cache、separated 栈状态、app worker 数、常驻容器内存汇总，并补测试。
2. 扩展 scripts/install_platform_resource_limits.py 或新增受控 ops 脚本，支持 dry-run 默认、swappiness=10 模板、Docker/BuildKit/journald 资源配置检查、明确回滚路径，不做破坏性清理。
3. 更新 scripts/cloud_server_cleanup.sh，保持 dry-run 默认，允许安全 builder prune，禁止默认 image prune -a，新增在确认 nginx 仍指向 18090 后停止 docker-compose.separated.yml 的可选参数。
4. 修改 docker-compose.mysql.yml 和 docker-compose.separated.yml：统一 APP_WORKERS 默认 1；为常驻服务增加可配置 mem_limit/cpus/logging 或复用现有资源治理模板；不要给 MySQL 设置过低上限。
5. 将 analytics-worker 改造成可选 profile/按需启动，并更新 deploy/quick deploy/build scripts 的 analytics 验收逻辑：默认不强制等待 analytics-worker，显式 --with-analytics-worker 时才启动并检查 duckdb/pyarrow/db ping。
6. 设计并实现 runtime-worker 内嵌 scheduler 的灰度能力：RUNTIME_WORKER_EMBED_SCHEDULER=false 默认关闭，开启时启动 background jobs，使用 leader lock 防重复入队，并继续记录 runtime-scheduler heartbeat。独立 scheduler 默认保留，线上灰度需用户授权。
7. 更新 runbook/报告，说明执行顺序、风险、回滚、线上验收命令和目标指标。

最低验证：
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_platform_resource_report.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_platform_optimization_readiness.py backend/tests/test_cloud_performance_script.py backend/tests/test_database_url_driver.py backend/tests/test_independent_runtime_components.py backend/tests/test_runtime_task_queue.py -q
- sudo docker compose -f docker-compose.mysql.yml config >/tmp/tquant-compose-config.yml
- git diff --check
- git diff -- frontend strategy_policy.py | wc -l 必须为 0

最终交付：
1. 修复后的脚本/compose/runbook/测试。
2. 一份 docs/reports/cloud-server-optimization-implementation-report-2026-06-09.md，包含基线、改动、验证结果、未执行的线上动作、风险和回滚。
3. 明确说明未部署、未切流、未改策略语义；如需线上执行，必须用户单独授权。
```
