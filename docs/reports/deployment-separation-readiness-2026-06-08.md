# 前端/后端/数据库分离部署 Readiness 报告（2026-06-08）

## 结论

本轮已完成本地分离部署 readiness 工件准备，但未部署、未切流。

当前状态：

- 前端静态服务：已新增 `frontend-web` Dockerfile 和 nginx 配置。
- 后端 API-only：已新增 `SERVE_FRONTEND_STATIC` 开关，默认 `true`，分离 compose 中设为 `false`；API-only 模式下 `/readyz` 不再依赖前端 dist。
- 网关路由：已新增 separated nginx gateway 模板。
- 本地 compose：已新增 `docker-compose.separated.yml` 并通过 `docker compose config` 结构校验。
- 云端部署：未执行，需用户单独授权。

## 当前拓扑

当前生产部署为部分分离：

```text
nginx
  └─ backend app container :18090
       ├─ FastAPI API
       ├─ frontend/dist static
       └─ frontend-next/dist static

mysql / redis / workers / go services 独立容器
```

风险：

1. 前端动态 chunk 仍依附 backend app 镜像和容器。
2. 前端热修、后端 API、worker 发布边界不够清晰。
3. backend 重启可能影响静态资源访问。

## 目标拓扑

```text
gateway nginx
  ├─ /              -> frontend-web
  ├─ /assets/*      -> frontend-web
  ├─ /next/*        -> frontend-web
  ├─ /next/assets/* -> frontend-web
  ├─ /api/*         -> backend-api
  ├─ /readyz        -> backend-api
  ├─ /metrics       -> backend-api
  └─ /ws/*          -> backend-api

backend-api
  └─ FastAPI API-only, SERVE_FRONTEND_STATIC=false

workers
  ├─ runtime-worker
  ├─ scheduler
  ├─ analytics-worker
  └─ backtest-worker

data
  ├─ mysql
  └─ redis
```

## 新增工件

| 文件 | 用途 |
| --- | --- |
| `deploy/frontend/Dockerfile` | 构建旧 `frontend/` 和 `frontend-next/`，产出独立 nginx 静态服务 |
| `deploy/frontend/nginx.conf` | frontend-web 内部静态路由、SPA fallback、assets cache |
| `deploy/nginx/tquant-separated-gateway.conf.template` | 网关层 `/api`、`/readyz`、`/next`、`/assets` 路由模板 |
| `deploy/backend-api/Dockerfile` | 从现有 web runtime 镜像派生 API-only 镜像，只复制后端代码，降低云端构建内存压力 |
| `docker-compose.separated.yml` | 分离拓扑 readiness compose，复用既有 `tquant-mysql_default` 网络和 MySQL/Redis 容器 |
| `docs/operations/frontend-backend-separated-deployment-runbook.md` | 部署、健康检查、回滚手册 |

## 后端最小改动

新增配置：

```env
SERVE_FRONTEND_STATIC=true|false
```

默认：

```text
true
```

分离模式：

```text
false
```

行为：

1. `true`：保持旧行为，backend 继续托管前端静态资源。
2. `false`：backend 只服务 API/readyz/metrics/ws；非 API 页面路径返回 JSON 404，不再 fallback HTML。

验证测试：

- `backend/tests/test_frontend_next_level1_cutover.py::test_api_only_mode_disables_backend_static_fallback`
- `backend/tests/test_frontend_next_level1_cutover.py::test_api_only_readyz_does_not_require_static_frontend_dist`

本轮已执行：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_frontend_next_level1_cutover.py -q
```

结果：6 passed。

## 本地 readiness 校验

已执行：

```bash
AUTH_SECRET_KEY=local-compose-check-secret-with-more-than-sixty-four-characters-2026-06-08 \
TQUANT_SETTINGS_ENCRYPTION_KEY=local-encryption-key-placeholder \
MYSQL_ROOT_PASSWORD=root \
MYSQL_PASSWORD=app \
docker compose -f docker-compose.separated.yml config
```

结果：compose config 可解析，`backend-api` 环境包含 `SERVE_FRONTEND_STATIC=false`；`frontend-web` 挂载 `frontend/dist` 与 `frontend-next/dist`；MySQL/Redis 通过既有 Docker network 访问，不重复创建数据库容器。

建议后续本地完整启动验证：

```bash
docker compose -f docker-compose.separated.yml build backend-api
docker compose -f docker-compose.separated.yml up -d frontend-web backend-api gateway
curl -fsS http://127.0.0.1:18080/
curl -fsS http://127.0.0.1:18080/next/
curl -fsS http://127.0.0.1:18090/readyz
curl -fsS http://127.0.0.1:18000/readyz
```

## 云端部署前置条件

部署前必须再次获得用户明确授权，并执行只读健康检查：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps
curl -fsS http://127.0.0.1:18090/readyz
df -h /
free -m
sudo docker system df
```

## Scope 与回滚

| Scope | 行为 | 回滚 |
| --- | --- | --- |
| `frontend` | 只构建/发布/重启 `frontend-web` | 回滚上一版 frontend image 或静态目录 |
| `api` | 只构建/发布/重启 `backend-api` | 回滚上一版 backend image；必要时 `SERVE_FRONTEND_STATIC=true` |
| `worker` | 只重启 runtime/scheduler/analytics/backtest worker | 回滚对应 worker image |
| `go` | 只发布 Go BFF/market-read/scan | 回滚 Go service image |
| `db-migration` | 只跑 migration | 需备份和单独授权；失败时停 worker 并按备份恢复 |
| `all` | 完整发布 | 按 frontend/api/worker/go/db 顺序逐项回滚 |

## Readiness 结论

- 可申请部署授权：可以，但仍需用户单独授权。
- 是否阻塞 frontend-next 本地验收：不阻塞，frontend-next 本地门禁已全绿。
- 是否阻塞 cutover：分离部署本身不阻塞；正式 cutover 仍需线上验收、资源 gate、写操作 ready、回滚演练和用户授权。
