# 云端资源与性能复测授权包（2026-06-10）

状态：待授权，未执行线上写操作  
适用范围：云端资源基线、资源优化执行、只读性能复测  
默认边界：不部署、不切流、不停容器、不清 Docker cache、不改 sysctl，除非用户单独授权

## 当前仓库准备状态

已确认本地配置具备以下能力：

1. `docker-compose.mysql.yml` 保持 `APP_WORKERS=${APP_WORKERS:-1}`。
2. 核心服务配置了 `mem_limit`、`memswap_limit`、`cpus` 与统一 `json-file` logging。
3. `analytics-worker` 使用 `profiles: ["analytics"]`，默认按需启动。
4. `runtime-worker` 暴露 `RUNTIME_WORKER_EMBED_SCHEDULER=${RUNTIME_WORKER_EMBED_SCHEDULER:-false}`，默认不合并 scheduler。
5. `PRODUCTION_RUNBOOK.md`、`docs/operations/deployment-topology-runbook.md`、`docs/operations/worker-runbook.md` 已记录 analytics 按需和 scheduler 灰度/回滚原则。

## 授权前只读基线

以下命令仅在用户授权连接线上后执行；本轮未执行：

```bash
free -m
df -h /
docker system df
docker stats --no-stream
curl -fsS https://weisilianghua.cloud/readyz
curl -fsS https://weisilianghua.cloud/metrics
python3 scripts/collect_platform_resource_report.py \
  --json-output docs/reports/platform-resource-baseline-$(date +%F).json \
  --markdown-output docs/reports/platform-resource-baseline-$(date +%F).md
```

需要记录：

1. Swap 已用、空闲内存、根分区。
2. 常驻容器数量和每个容器 CPU/MEM。
3. Docker build cache、slow log、binlog、journal 状态。
4. `/readyz` 全量检查结果。
5. `/metrics` 中 market-read、BFF、local quote cache 指标。

## 需单独授权的写操作

以下动作本轮未执行，必须单独确认后才能逐项做：

```bash
docker builder prune -af
sudo sysctl vm.swappiness=10
sudo docker compose -f docker-compose.separated.yml down
RUNTIME_WORKER_EMBED_SCHEDULER=true docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
```

执行限制：

1. 不把 `APP_WORKERS 2 -> 1` 计入收益，除非基线证明线上实际大于 1。
2. 不在未观察满 1 个交易日前停止独立 `runtime-scheduler`。
3. MySQL buffer pool 调整必须基于当前内存和监控，建议只在 `384M-512M` 区间评估。
4. analytics worker 默认不常驻，任务完成后按 runbook 停回按需状态。

## 性能复测命令

以下为授权后的只读复测命令；本轮未执行：

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8 --rounds 3
./scripts/quick_cloud_deploy.sh --verify-only --performance-verify --performance-rounds 3 --performance-samples 8
```

目标：

1. `monitor_bff` p95 <= 500ms。
2. `priority_board` p95 <= 500ms。
3. `bff_partial_timeout = 0`。
4. market-read unresolved misses = 0。
5. Redis 命中率 >= 90%；未达标时必须拆分 miss/fallback 原因。

## 结果记录模板

| 项目 | Before | After | 结论 | 证据 |
|---|---:|---:|---|---|
| Swap used | 待填 | 待填 | 待填 | `free -m` |
| Free memory | 待填 | 待填 | 待填 | `free -m` |
| Root disk used | 待填 | 待填 | 待填 | `df -h /` |
| Docker build cache | 待填 | 待填 | 待填 | `docker system df` |
| 常驻容器数 | 待填 | 待填 | 待填 | `docker ps` |
| `/readyz` | 待填 | 待填 | 待填 | curl raw output |
| monitor_bff p95 | 待填 | 待填 | 待填 | performance JSON |
| priority_board p95 | 待填 | 待填 | 待填 | performance JSON |
| BFF timeout | 待填 | 待填 | 待填 | `/metrics` |
| market-read unresolved | 待填 | 待填 | 待填 | `/metrics` |

## 回滚记录模板

| 动作 | 回滚命令 | 是否执行 | 证据 |
|---|---|---|---|
| swappiness | `sudo sysctl vm.swappiness=<old>` | 待填 | 待填 |
| separated 栈 | `docker compose -f docker-compose.separated.yml up -d` | 待填 | 待填 |
| embedded scheduler | `RUNTIME_WORKER_EMBED_SCHEDULER=false docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker runtime-scheduler` | 待填 | 待填 |
| analytics worker | `docker compose --profile analytics -f docker-compose.mysql.yml stop analytics-worker` | 待填 | 待填 |

## 本轮状态

本轮只准备授权包和报告模板。未执行部署、切流、服务器写操作、停容器、Docker cache 清理或 sysctl 修改。
