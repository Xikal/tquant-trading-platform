# 线上资源与性能复测授权包（2026-06-11）

## 结论

本文件只准备线上授权材料，不执行任何线上动作。

当前仓库已具备资源收口和只读复测所需入口：`RUNTIME_WORKER_EMBED_SCHEDULER` 默认关闭、Go BFF/market-read/scan-worker internal token 配置已存在、`/readyz` 与 `/metrics` 可作为复测事实源、Docker builder prune 与 `vm.swappiness` 已有独立运维入口。所有线上资源、性能复测、Docker/sysctl/容器动作必须等用户单独授权。

## 授权边界

| 动作 | 本轮状态 | 是否需要单独授权 |
| --- | --- | --- |
| 拉取线上 `/readyz`、`/metrics` | 未执行 | 是 |
| 运行云性能脚本 | 未执行 | 是 |
| `RUNTIME_WORKER_EMBED_SCHEDULER=true` 灰度 | 未执行 | 是 |
| 停独立 scheduler 容器 | 未执行 | 是 |
| Docker builder prune / system prune | 未执行 | 是 |
| 修改 `vm.swappiness` | 未执行 | 是 |
| 容器重启、重建、切流、部署 | 未执行 | 是 |
| 线上写接口、模拟盘订单、策略发布 | 未执行 | 是 |

## 资源收口授权清单

授权前必须记录：

1. 当前 `git rev-parse --short HEAD`、`git status --short`。
2. `docker compose -f docker-compose.mysql.yml ps`。
3. `docker stats --no-stream`。
4. `free -m`、`df -h /`。
5. `curl -fsS http://127.0.0.1:18090/readyz`。
6. 受保护 `/metrics` 中 runtime、BFF、market-read、local quote cache 指标。

可授权动作模板：

```bash
# 只读基线
curl -fsS http://127.0.0.1:18090/readyz
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" http://127.0.0.1:18090/metrics \
  | rg "bff|market_read|local_quote_cache|runtime|provider"

# 资源收口灰度，需单独授权后执行
RUNTIME_WORKER_EMBED_SCHEDULER=true docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker

# sysctl 与 Docker 清理，需单独授权后执行
sudo sysctl vm.swappiness=10
sudo docker builder prune -af
```

回滚模板：

```bash
RUNTIME_WORKER_EMBED_SCHEDULER=false docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker runtime-scheduler
sudo sysctl vm.swappiness=<previous_value>
curl -fsS http://127.0.0.1:18090/readyz
```

## 只读性能复测模板

授权只读复测后，建议按固定三轮记录：

| 项 | 命令/来源 | 目标 |
| --- | --- | --- |
| readiness | `/readyz` | 全 true |
| app metrics | `/metrics` | 无异常 fallback/timeout 激增 |
| local quote cache | `tquant_local_quote_cache_*` | 覆盖率和命中率可解释 |
| market-read | Go market-read `/metrics` | unresolved miss 为 0 或有明确缺口原因 |
| BFF | BFF timeout/cache/partial 指标 | `bff_partial_timeout=0` |
| monitor BFF | 云性能脚本 | p95 <= 500ms |
| priority board | 云性能脚本 | p95 <= 500ms 且排序语义不变 |
| scan-worker | `/api/scan-worker/v1/status` 只读状态 | `strategy_engine=python_reference` |

建议产物：

- `docs/reports/cloud-performance-recheck-YYYY-MM-DD.md`
- `docs/reports/cloud-performance-recheck-YYYY-MM-DD.json`

机器 JSON 若较大，应放到 `backend/data/reports/` 或既有 artifact 目录。

## Internal Token 运维说明

`TQUANT_INTERNAL_SERVICE_TOKEN` 用于 Python backend 与 Go BFF/market-read/scan-worker 的内部服务认证。业务读/触发接口使用 `X-Internal-Service-Token` header，健康检查 `/healthz`、`/readyz`、`/metrics` 可按服务设计不要求该 header。

要求：

1. 生产环境配置 Go 微服务 URL 时必须设置 `TQUANT_INTERNAL_SERVICE_TOKEN`。
2. Token 应使用强随机值，建议不少于 32 字节随机熵；不要复用 `AUTH_SECRET_KEY` 或 `TQUANT_SETTINGS_ENCRYPTION_KEY`。
3. `docker-compose.separated.yml` 已把 `TQUANT_INTERNAL_SERVICE_TOKEN` 设为必填；MySQL compose 中各服务均透传该变量。
4. 轮换时先同步更新 backend、go-bff-gateway、go-market-read-service、go-scan-worker，再重启相关服务并复验。

403 排查顺序：

1. 确认调用方是否带 `X-Internal-Service-Token`。
2. 确认 backend 与 Go 服务环境变量一致。
3. 确认请求没有被 gateway/nginx 去掉 header。
4. 对 scan-worker 状态接口，先看 `/readyz`，再带 token 请求 `/api/scan-worker/v1/status`。
5. 对 BFF remote client，查看 backend `/metrics` 和日志中的 remote failure/circuit/open 信息。
6. 对 separated deploy，确认 `.env` 或部署环境中 `TQUANT_INTERNAL_SERVICE_TOKEN` 非空，且 compose config 展开后存在。

## 本轮未执行事项

- 未连接线上服务器。
- 未拉取线上 `/readyz` 或 `/metrics`。
- 未运行云性能脚本。
- 未执行 Docker prune。
- 未修改 `vm.swappiness`。
- 未重启、停止或重建容器。
- 未部署、未切流、未执行线上写操作。
