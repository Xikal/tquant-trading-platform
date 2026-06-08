# 前端/后端/数据库分离部署 Runbook

状态：准备完成，未执行云端部署

## 1. 适用范围

本 runbook 用于把平台从“backend app 同时托管 API 和前端静态资源”切换为：

- `frontend-web`：独立 nginx 静态服务。
- `backend-api`：FastAPI API-only。
- workers：runtime/scheduler/analytics/backtest 独立进程。
- data：MySQL/Redis 独立容器。

## 2. 硬边界

1. 不部署、不切流，除非用户单独授权。
2. 不改旧 `frontend/` 生产源码。
3. 不改 `strategy_policy.py`。
4. 不改变生产策略语义、`production_score`、`priority_board` 排序和口径。
5. 数据库 migration 需要单独备份和授权。
6. 不删除 Docker volume、MySQL 数据、binlog、备份或运行产物来伪造健康状态。

## 3. 构建工件

| 工件 | 文件 |
| --- | --- |
| frontend static image | `deploy/frontend/Dockerfile` |
| frontend nginx | `deploy/frontend/nginx.conf` |
| gateway nginx | `deploy/nginx/tquant-separated-gateway.conf.template` |
| separated compose | `docker-compose.separated.yml` |

## 4. 本地验证

配置占位环境：

```bash
export AUTH_SECRET_KEY=local-compose-check-secret-with-more-than-sixty-four-characters-2026-06-08
export TQUANT_SETTINGS_ENCRYPTION_KEY=local-encryption-key-placeholder
export MYSQL_ROOT_PASSWORD=root
export MYSQL_PASSWORD=app
```

结构校验：

```bash
docker compose -f docker-compose.separated.yml config
```

构建：

```bash
docker compose -f docker-compose.separated.yml build frontend-web backend-api
```

启动：

```bash
docker compose -f docker-compose.separated.yml up -d mysql redis migration frontend-web backend-api gateway
```

健康检查：

```bash
curl -fsS http://127.0.0.1:18080/
curl -fsS http://127.0.0.1:18080/next/
curl -fsS http://127.0.0.1:18090/readyz
curl -fsS http://127.0.0.1:18000/readyz
curl -fsS http://127.0.0.1:18000/next/
```

API-only 检查：

```bash
curl -i http://127.0.0.1:18090/monitor
curl -i http://127.0.0.1:18090/api/does-not-exist
```

期望：

- `/monitor` 返回 JSON 404，不能返回 HTML。
- `/api/does-not-exist` 返回 API 404。
- `/readyz` 正常；API-only 模式不要求 backend 镜像内存在 `frontend/dist` 或 `frontend-next/dist`。

## 5. 云端授权前只读检查

必须先获得用户明确授权。授权前只能做只读检查：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps
curl -fsS http://127.0.0.1:18090/readyz
df -h /
free -m
sudo docker system df
```

## 6. 部署 Scope

| Scope | 说明 | 不应影响 |
| --- | --- | --- |
| `frontend` | 构建/发布/重启 `frontend-web` | backend-api、workers、db |
| `api` | 构建/发布/重启 `backend-api` | frontend-web、workers、db |
| `worker` | 重启 runtime/scheduler/analytics/backtest workers | frontend-web、backend-api |
| `go` | 发布 Go BFF/market-read/scan | Python backend、frontend-web |
| `db-migration` | migration only | 必须先备份、单独授权 |
| `all` | 按 frontend/api/worker/go/db 全量发布 | 需完整回滚计划 |

## 7. Scope 健康检查

frontend：

```bash
curl -fsS http://127.0.0.1:18080/
curl -fsS http://127.0.0.1:18080/next/
curl -fsS http://127.0.0.1:18080/next/assets/
```

api：

```bash
curl -fsS http://127.0.0.1:18090/readyz
curl -fsS http://127.0.0.1:18090/api/settings
```

gateway：

```bash
curl -fsS http://127.0.0.1:18000/
curl -fsS http://127.0.0.1:18000/next/
curl -fsS http://127.0.0.1:18000/readyz
```

worker：

```bash
sudo docker compose -f docker-compose.mysql.yml ps runtime-worker runtime-scheduler analytics-worker backtest-worker
```

db：

```bash
sudo docker compose -f docker-compose.mysql.yml ps mysql redis
```

## 8. 回滚

frontend 回滚：

```bash
docker image tag tquant-frontend-web:<previous> tquant-frontend-web:local
docker compose -f docker-compose.separated.yml up -d frontend-web
```

api 回滚：

```bash
docker image tag tquant-backend-api:<previous> tquant-backend-api:local
docker compose -f docker-compose.separated.yml up -d backend-api
```

API-only 失败应急：

```bash
SERVE_FRONTEND_STATIC=true docker compose -f docker-compose.mysql.yml up -d app
```

gateway 回滚：

```bash
# 恢复旧 nginx 模板，让 / 和 /api/ 全部回到旧 backend app 端口
sudo nginx -t
sudo systemctl reload nginx
```

worker 回滚：

```bash
docker compose -f docker-compose.mysql.yml up -d runtime-worker runtime-scheduler analytics-worker backtest-worker
```

db migration 回滚：

1. 停 worker。
2. 保留当前 DB snapshot。
3. 按授权备份恢复。
4. 复跑 `/readyz` 和业务 smoke。

## 9. 禁止项

1. 禁止无授权部署云端。
2. 禁止用清数据、清 volume、清 binlog 来制造通过。
3. 禁止绕过鉴权做生产写入。
4. 禁止把 frontend-next cutover 与部署分离混成同一步。
5. 禁止让 `strategy_engine` 替代生产策略排序或打分。

## 10. 通过标准

1. frontend-web 重启不影响 backend `/readyz`。
2. backend-api 重启不影响 `/next/assets/*` 静态资源。
3. `/api/*` 只由 backend-api 服务。
4. `/` 和 `/next/*` 只由 frontend-web 服务。
5. 每个 scope 都有明确回滚命令。
6. 云端部署前再次取得用户授权。
