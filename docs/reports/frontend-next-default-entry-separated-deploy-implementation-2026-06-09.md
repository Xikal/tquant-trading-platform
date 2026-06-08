# frontend-next 默认入口与分离部署准备实施报告 - 2026-06-09

状态：本地代码、测试、dry-run 已完成；未部署、未切流

适用范围：`frontend-next` 默认入口契约、前后端分离部署准备、部署脚本独立 scope 重构、资源稳定性加固建议。

## 结论

1. 本地已具备将 `/` 和旧业务路由切到 `frontend-next` 的后端 cutover 契约，`FRONTEND_NEXT_CUTOVER_PATHS=all` 包含根入口和已支持页面。
2. 分离部署配置已改为 `frontend-web` 默认服务 `frontend-next`，旧 `frontend/dist` 保留在回滚资源路径，不删除。
3. 部署脚本已支持 `frontend-next`、`frontend-legacy`、`backend-api`、`db-migration`、`worker`、`go`、`ops`、`all` 独立 scope；`strategy_policy.py` 自动部署会阻断。
4. `frontend-next` scope 只发布新前端静态产物或重建 `frontend-web`，不重启后端、MySQL、worker，不跑 migration。
5. `db-migration` scope 和 `all` scope 在 migration 前强制执行数据库备份，备份或 migration 失败会阻断后续动作。
6. 当前线上仍未切流：`https://43.143.243.97/` 仍返回旧 React/AntD 产物，`/next/monitor` 返回 `frontend-next` 产物。
7. 本轮没有部署、没有切流、没有生产写操作。

## 改动摘要

| 模块 | 改动 |
|---|---|
| `backend/app/main.py` | 根入口 `/` 支持按 cutover 配置服务 `frontend-next`；`SERVE_FRONTEND_STATIC=false` 保持 API-only 健康响应。 |
| `backend/app/services/frontend_next_cutover.py` | `FRONTEND_NEXT_CUTOVER_PATHS=all` 显式包含根入口和旧业务路由；支持 `/` allowlist。 |
| `deploy/frontend/nginx.conf` | `frontend-web` root 改为 `/usr/share/nginx/html-next`；旧资源保留在 `/__legacy/assets/`。 |
| `deploy/frontend/Dockerfile` | 同时构建并复制旧前端和新前端 dist 到 `html-root`、`html-next`。 |
| `docker-compose.separated.yml` | `backend-api` 为 API-only：`SERVE_FRONTEND_STATIC=false`；`frontend-web` 和 `gateway` 保持独立健康检查。 |
| `scripts/deploy_scope.py` | 新增统一 scope 解析器；CI 和部署脚本复用；阻断 `strategy_policy.py`。 |
| `scripts/deploy_cloud_server.sh` | 拆分前端、API、migration、worker、Go、ops 部署路径；支持组合 scope；scope-aware 远端验证。 |
| `scripts/quick_cloud_deploy.sh` / `scripts/one_click_cloud_deploy.sh` | 支持新 scope、changed-files、compose topology、service-specific compose 文件、frontend-next required 和 dry-run 透传。 |
| `.github/workflows/ci.yml` | frontend-next artifact 独立上传/下载；changed files 调用 `scripts/deploy_scope.py`。 |
| `Makefile` | 新增 `deploy-cloud-next`、`deploy-cloud-api`、`deploy-cloud-db` 等独立入口。 |
| `.env.deploy.local.example` | 增加 separated topology 和各服务 compose 文件默认值。 |
| `backend/tests/*` | 增加 cutover、scope resolver、部署脚本反向断言测试。 |
| `docs/engineering-conventions.md` | 增加 `frontend-next` 默认基线，沉淀本轮踩坑经验。 |

## 当前线上只读基线

命令：

```bash
curl -k -fsS https://43.143.243.97/ | grep -E 'react-vendor|antd-|/assets/index-|solid-vendor|tanstack-router|/next/assets/index-' | head -5
curl -k -fsS https://43.143.243.97/next/monitor | grep -E 'react-vendor|antd-|/assets/index-|solid-vendor|tanstack-router|/next/assets/index-' | head -8
```

结果：

```text
https://43.143.243.97/:
  /assets/index-CadCWL8J.js
  /assets/react-vendor-CHkn0jt9.js
  /assets/antd-core-BzAQGpzi.js

https://43.143.243.97/next/monitor:
  /next/assets/index-CTh_lI5o.js
  /next/assets/solid-vendor-Ch9Uoa8e.js
  /next/assets/tanstack-router-BLsFFlgG.js
```

判定：线上默认入口仍是旧前端；`/next/*` 是新前端。

服务器只读资源检查：

```text
readyz: ok
root disk: 59G total, 34G used, 23G available, 60%
memory: 3723MB total, 282MB available
swap: 1987MB used, 0MB free
docker stats sample:
  tquant-frontend-web: 1.4MiB
  tquant-backend-api: 307MiB
  tquant-app-mysql: 567MiB
  tquant-runtime-worker-mysql: 682MiB
  tquant-runtime-scheduler-mysql: 410MiB
  tquant-analytics-worker-mysql: 62.6% CPU, 85MiB
vmstat sample:
  swpd 2034840 -> 2035680
  si/so first sample 578/769, later samples still有少量 swap in
  CPU idle recovered from 71% to 99% in sample window, but swap remains full
```

判定：分离容器已经存在，但公网默认入口仍未切到 separated frontend；swap 打满仍是稳定性风险。

## 关键部署行为

| Scope | 当前脚本行为 |
|---|---|
| `frontend-next` | 要求 `frontend-next/dist/index.html`；上传新前端 dist；separated 下 recreate `frontend-web`；monolith 兼容路径只更新 `/app/frontend-next/dist`。 |
| `frontend-next,ops` | full package 包含 `frontend-next/dist` 和旧 `frontend/dist` 回滚资源，发布新前端并允许刷新 ops 配置。 |
| `backend-api` | separated 下只 build/recreate `backend-api`；monolith 下只更新 `app`；不触碰 `frontend-next/dist`。 |
| `db-migration` | 先 `bash ./scripts/backup_database.sh`，再运行 migration；失败阻断。 |
| `worker` | 只更新 runtime/backtest/analytics worker 相关服务。 |
| `go` | 只更新 Go BFF/market-read/scan worker。 |
| `all` | 禁用 git-sync，使用 package path 保证本地 frontend dist 产物可带到远端；migration 前先备份；separated 下按 API、worker、frontend-web、gateway 分组。 |

执行顺序说明：组合 scope 和 `all` scope 按 `db-migration -> backend-api -> worker -> go -> frontend-next -> gateway` 顺序执行；含 `frontend-next` 的 full package 强制保留 `frontend-next/dist` 和 `frontend/dist`，避免 separated `frontend-web` 挂载旧前端回滚目录时变成空目录；含 `frontend-next` 的 scope 强制走 package path，避免 git-sync/delta 路径丢失本地构建出的 `frontend-next/dist`。`scripts/deploy_delta_package.py` 保持现有安全删除规则：`.env`、`.runtime/`、`backend/data/`、备份、数据库文件和归档文件不能被 delta 删除。

## Dry-run 与本地验证

通过命令：

```bash
backend/.venv/bin/pytest backend/tests/test_frontend_next_cutover_service.py backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py -q
bash -n scripts/deploy_cloud_server.sh scripts/quick_cloud_deploy.sh scripts/one_click_cloud_deploy.sh
AUTH_SECRET_KEY=... TQUANT_SETTINGS_ENCRYPTION_KEY=... MYSQL_ROOT_PASSWORD=root MYSQL_PASSWORD=app TQUANT_INTERNAL_SERVICE_TOKEN=... docker compose -f docker-compose.separated.yml config
ONE_CLICK_DEPLOY_DRY_RUN=1 bash scripts/one_click_cloud_deploy.sh --host 43.143.243.97 --key /Users/j/Downloads/gupiao.pem --scope frontend-next --frontend-next-required --compose-topology separated --backend-api-compose-file docker-compose.separated.yml --frontend-compose-file docker-compose.separated.yml --db-migration-compose-file docker-compose.mysql.yml --runtime-compose-file docker-compose.mysql.yml --go-compose-file docker-compose.mysql.yml --dry-run
python3 scripts/deploy_scope.py --changed-files-from <frontend-next-only-file>
python3 scripts/deploy_scope.py --changed-files-from <strategy-policy-file>
git diff -- frontend strategy_policy.py | wc -l
```

结果：

```text
pytest: 64 passed, 1 warning
bash -n: passed
docker compose separated config: passed
one-click dry-run: printed frontend-next separated args; no deploy
frontend-next-only scope: frontend-next
frontend-next + deploy/frontend/nginx.conf scope: frontend-next,ops
strategy_policy.py scope: blocked, exit_code=2
git diff -- frontend strategy_policy.py | wc -l: 0
```

frontend-next 门禁：

```bash
cd frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run chunk:profile
npm run css:budget
```

结果：

```text
api:check: passed
typecheck: passed
lint: passed
vitest: 26 files, 113 tests passed
build: passed
e2e: 60 passed
chunk:profile: ok; initial JS raw 284749 bytes; initial ECharts assets 0
css:budget: ok; dist CSS raw 181080 bytes; gzip 37708 bytes; !important 25
```

说明：`npm run e2e` 运行时本地后端未启动，Vite proxy 出现 `ECONNREFUSED 127.0.0.1:8000`，但测试覆盖了失败态/降级路径，最终 60 个用例全部通过。

## 资源稳定性加固方案

当前线上资源风险主要不在旧前端静态文件，而在 swap 打满、worker/analytics CPU、DB/cache 冷读和 monolith 静态/API 混合服务。

建议执行顺序：

1. 切换前先保持 `RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED=true`、`RUNTIME_STARTUP_CACHE_PREWARM_ENABLED=false`、`RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED=false`，避免部署或重启期间抢占交互查询资源。
2. 市场开盘或验收期间可临时设置 `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`，暂停低优先级 analytics/backtest/data-repair 任务领取；只暂停低优先任务，不改变策略排序。
3. 分离拓扑正式启用后，公网静态资源由 `frontend-web` 服务，`backend-api` 设置 `SERVE_FRONTEND_STATIC=false`，减少 Python app worker 静态 fallback 压力。
4. 保留 BFF stale-while-revalidate：冷读时优先返回缓存并异步刷新，避免 `/next/monitor/market` 和 `/next/strategy-tracking` 因源超时拖慢整页。
5. 部署前 preflight 继续检查 swap、磁盘、Docker build cache、MySQL slow log、binlog、备份数量；清理只允许安全 prune，不做 `image prune -a`、不做 `volume prune`。
6. 对当前 swap 打满状态，建议在获得运维授权后先降频/暂停低优先 worker，再清理 build cache 和临时上传包，最后评估是否扩容内存或调整 worker 并发。

## 回滚步骤

未部署状态无需回滚。若后续获得授权并切换：

1. `frontend-next` 静态热发布会在远端 `.runtime/frontend-next-dist-backup-<ts>` 备份旧新前端 dist，可恢复该目录到 `frontend-next/dist`。
2. separated `frontend-web` 仍挂载旧 `frontend/dist` 到 `html-root`，旧资源可通过 `/__legacy/assets/` 回滚验证。
3. 若需要恢复旧默认入口，必须单独授权修改 gateway/nginx/backend cutover env，不删除新前端产物。
4. migration 失败时脚本在 app/API 重启前阻断；成功 migration 的回滚必须走 Alembic 降级或数据恢复，不允许脚本自动清库。

## 剩余风险

1. 当前线上尚未部署这些代码，默认入口仍是旧前端。
2. 分离容器存在但公网默认入口仍未切到 separated frontend；正式切流需要单独授权。
3. 线上 swap 仍为 0 free，analytics-worker 有 CPU 高占用样本，切流前建议先处理低优先任务和缓存冷读。
4. `frontend-next` CSS source raw 仍超过解释阈值，但 dist gzip、`!important` 和首屏 chunk 预算通过；后续仍应继续 CSS 路由级拆分。
5. 本轮未做真实写操作，因此没有生产写入 rollback 证据；这是符合本轮“不部署、不切流、不写生产”的边界。

## 边界确认

| 项 | 结论 |
|---|---|
| 是否改旧 `frontend/` | 否 |
| 是否改 `strategy_policy.py` | 否 |
| 是否改变生产策略语义、`production_score`、`priority_board` | 否 |
| 是否做自动交易变更 | 否 |
| 是否删除 `frontend/dist` | 否 |
| 是否部署 | 否 |
| 是否切流 | 否 |
| 是否有生产写入 | 否 |

## 最终状态

本地代码已满足“停旧前端默认入口 + frontend-next 默认入口 + 前后端分离部署准备 + 部署脚本独立部署重构 + 资源稳定性加固”的实施准备状态；线上仍保持原状态，未部署未切流。若要让云服务器正式使用 `frontend-next` 默认入口，还需要用户单独授权执行部署和切流验证。
