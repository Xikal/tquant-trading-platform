# Frontend Next Default Entry And Separated Deployment Plan - 2026-06-09

状态：开发计划，未授权执行部署或切流

适用范围：将线上默认入口从旧 `frontend/` 切换到 `frontend-next/`，并推进前端静态资源、后端 API、数据库/Worker 的部署职责分离。

## 一句话结论

当前线上旧前端仍作为默认入口部署：`/`、`/monitor`、`/paper`、`/strategy-tracking`、`/backtest` 返回旧 React/AntD 产物；`/next/*` 返回 `frontend-next` Solid 产物。

停止旧前端入口可以减少误入旧 UI 和静态路由复杂度，但旧前端本身只是静态文件，不能明显释放 CPU/内存。真正改善卡顿需要同时完成：

1. 根入口和旧业务路由切到 `frontend-next`。
2. 静态资源由独立 nginx `frontend-web` 服务，后端 `backend-api` 只服务 API。
3. 限流或降频高占用 `runtime-worker`、BFF 冷读、MySQL/swap 压力。

## 已确认现状

### 线上入口

公网验证结果：

| URL | 当前返回 | 判定 |
|---|---|---|
| `https://43.143.243.97/` | `/assets/index-*.js`、`react-vendor`、`antd-*` | 旧前端默认入口 |
| `https://43.143.243.97/monitor` | `/assets/index-*.js`、`react-vendor`、`antd-*` | 旧前端 |
| `https://43.143.243.97/paper` | `/assets/index-*.js`、`react-vendor`、`antd-*` | 旧前端 |
| `https://43.143.243.97/strategy-tracking` | `/assets/index-*.js`、`react-vendor`、`antd-*` | 旧前端 |
| `https://43.143.243.97/backtest` | `/assets/index-*.js`、`react-vendor`、`antd-*` | 旧前端 |
| `https://43.143.243.97/next/monitor` | `/next/assets/index-*.js`、`solid-vendor`、`tanstack-router/query` | 新前端 |

容器目录验证结果：

| 目录 | 文件数 | 用途 |
|---|---:|---|
| `/app/frontend/dist` | 85 | 旧前端静态产物 |
| `/app/frontend-next/dist` | 42 | 新前端静态产物 |

### 线上卡顿主因

线上浏览器采样显示：

| 页面 | 点击到 URL | 内容可见 | 主要慢点 |
|---|---:|---:|---|
| `/next/monitor` | 约 447ms | 约 1303ms | 初次加载和 monitor workspace |
| `/next/monitor/market` | 约 94ms | 约 4907ms | `/api/bff/v1/workspace/monitor?view=market` 约 4321ms |
| `/next/paper` | 约 34ms | 约 822ms | `/api/bff/v1/workspace/paper` 约 562ms |
| `/next/strategy-tracking` | 约 33ms | 可能超时 | `/api/bff/v1/workspace/strategy` 慢读和 source timeout |

服务器资源证据：

| 指标 | 观察值 | 影响 |
|---|---:|---|
| load average | `32.37 / 22.38 / 12.92` | CPU/IO 排队明显 |
| Mem available | 约 `496MB` | 容器内存压力高 |
| Swap | `1981/1987MB` | 几乎打满，容易造成全站抖动 |
| app worker | 出现 `WORKER TIMEOUT` / `SIGKILL Perhaps out of memory?` | API 和静态资源都会被拖慢 |
| Redis | 出现 socket timeout | BFF/cache 读路径受影响 |

## 硬边界

1. 不改 `strategy_policy.py`。
2. 不改变生产策略语义、`production_score`、`priority_board` 排序和口径。
3. 不做自动交易改动。
4. 不删除旧 `frontend/dist` 回滚产物，除非已经完成冷却期并获得单独授权。
5. 未获得用户明确授权前，不部署、不切流。
6. 写操作必须隔离写入、rollback、读回一致、403 权限断言。
7. 旧前端入口停用是展示/路由变更，不得把 shadow-only、research-only 或 `strategy_engine` 结果接入生产排序。

## 目标状态

### 入口状态

| 路由 | 目标 |
|---|---|
| `/` | 返回 `frontend-next` 默认入口，建议进入实时行动台 |
| `/monitor` | 返回或重定向到 `frontend-next` 实时行动台 |
| `/monitor/market` | 返回或重定向到 `frontend-next` 市场环境 |
| `/paper` | 返回或重定向到 `frontend-next` 模拟盘 |
| `/strategy-tracking` | 返回或重定向到 `frontend-next` 策略跟踪 |
| `/analysis` | 返回或重定向到 `frontend-next` 量化分析 |
| `/playbook` | 返回或重定向到 `frontend-next` 选股宝典 |
| `/backtest` | 返回或重定向到 `frontend-next` 回测 |
| `/data` | 返回或重定向到 `frontend-next` 数据中心 |
| `/settings` | 返回或重定向到 `frontend-next` 设置 |
| `/next/*` | 保持可访问，作为兼容入口 |
| `/api/*` | 只走后端 API |
| `/readyz`、`/metrics`、`/ws/*` | 只走后端 |
| `/assets/*` | 短期保留旧资源，回滚窗口后再移除 |
| `/next/assets/*` | 新前端长期强缓存资源 |

### 部署职责

| 组件 | 目标职责 |
|---|---|
| `frontend-web` | 只服务前端静态 HTML/CSS/JS |
| `backend-api` | 只服务 API、鉴权、WebSocket、readyz、metrics |
| `mysql` | 事实数据库 |
| `redis` | 缓存、pubsub、限流 |
| `runtime-worker` | Runtime task，按优先级和资源预算执行 |
| `runtime-scheduler` | 定时任务调度 |
| `go-bff-gateway` / `go-market-read-service` | 热读加速和可选聚合 |

## 代码锚点

| 文件 | 当前职责 | 本计划关注点 |
|---|---|---|
| `backend/app/main.py` | 后端静态兜底、`/readyz`、`SERVE_FRONTEND_STATIC`、`frontend_next_cutover_paths` | 保留 API-only 行为；必要时扩展根入口 cutover 测试 |
| `backend/app/services/frontend_next_cutover.py` | legacy path allowlist cutover | 支持 `all` 和页面 allowlist；确认 `/` 是否需要单独处理 |
| `backend/tests/test_frontend_next_level1_cutover.py` | cutover 和 API-only 回归测试 | 补根入口、新旧资产、API-only 健康检查测试 |
| `docker-compose.mysql.yml` | 当前线上主 compose，app 同时服务 API 与静态资源 | 阶段一可用 env cutover；不作为长期分离终态 |
| `docker-compose.separated.yml` | 已有分离部署雏形 | 阶段二升级为正式前后端分离部署 |
| `deploy/frontend/nginx.conf` | 静态前端 nginx，当前 root 服务旧前端、`/next` 服务新前端 | 改为 root 服务新前端，旧前端只做可选回滚 |
| `deploy/nginx/tquant-separated-gateway.conf.template` | gateway 转发 `/api` 到后端、静态到 frontend-web | 保持 API/static 分离，补健康和缓存规则 |
| `scripts/one_click_cloud_deploy.sh` | 一键部署入口，向 quick deploy 透传 scope/env | 新增分离部署 scope、dry-run 和 verify-only 摘要 |
| `scripts/quick_cloud_deploy.sh` | 部署参数解析、本地 gate、远端 preflight、验证 | 扩展 `--scope`、按 scope 控制本地构建和远端验证 |
| `scripts/deploy_cloud_server.sh` | 打包、上传、远端 build/up/restart 主脚本 | 拆分 frontend-next/backend-api/db/worker/go/ops 独立部署路径 |
| `scripts/deploy_delta_package.py` | delta package 构建和删除清单 | 保证按 scope 包含必要产物并避免删除运行时目录 |
| `backend/tests/test_cloud_deploy_scripts.py` | 部署脚本契约测试 | 新增分离部署、frontend-next-only、backend-only、migration-only 回归 |
| `.github/workflows/ci.yml` | CI scope 选择和部署入口 | 下载 frontend-next dist artifact，按变更文件选择独立 scope |
| `.env.deploy.local.example` | 部署默认配置说明 | 新增分离部署、scope、compose、artifact、prebuilt refs 配置说明 |
| `docs/frontend-next-cutover-runbook-2026-06-05.md` | 既有 cutover runbook | 本计划必须遵守其授权和回滚要求 |
| `docs/operations/legacy-route-removal.md` | 历史旧路由 `/backtests`、`/research` 退役 | 不与本次业务入口 cutover 混淆 |

## 阶段计划

### P0：保护现场与基线

目标：明确当前状态，不覆盖已有改动。

执行要求：

1. 运行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

2. 保护当前已知脏改动：

```text
docs/reports/frontend-next-chunk-profile-2026-06-08.json
docs/reports/frontend-next-chunk-profile-2026-06-08.md
docs/reports/frontend-next-css-budget-2026-06-07.json
docs/reports/frontend-next-css-optimization-2026-06-07.md
```

3. 记录线上入口：

```bash
curl -k -fsS https://43.143.243.97/ | grep -E 'react-vendor|antd-|/assets/index-'
curl -k -fsS https://43.143.243.97/next/monitor | grep -E 'solid-vendor|tanstack-router|/next/assets/index-'
```

4. 记录线上资源：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps
sudo docker stats --no-stream
free -m
vmstat 1 5
df -h /
```

验收：

- 能明确旧前端默认入口和新前端 `/next/*` 入口。
- 能明确资源基线和主要高占用容器。
- 无代码改动。

### P1：本地 cutover 契约补强

目标：先在代码和测试里把“默认入口切到 frontend-next”定义清楚，不直接部署。

实现项：

1. 扩展 `frontend_next_cutover_paths` 或后端静态路由逻辑，支持根入口 `/` 切换到 `frontend-next`。
2. 明确 `FRONTEND_NEXT_CUTOVER_PATHS=all` 的语义：
   - 包含所有受支持旧业务路由。
   - 是否包含 `/` 需要显式测试覆盖。
3. 保持 `/next/*` 永远走 `frontend-next`。
4. 保持 `/assets/*` 在回滚窗口内仍可读旧资源。
5. 保持 `/api/*` 未命中返回 JSON 404，而不是 SPA HTML。
6. 保持 `SERVE_FRONTEND_STATIC=false` 时：
   - `/` 返回健康 JSON 或网关接管。
   - 业务页面不再由后端静态兜底。
   - `/readyz` 不要求本地静态 dist。

测试项：

- 更新 `backend/tests/test_frontend_next_level1_cutover.py`：
  - `FRONTEND_NEXT_CUTOVER_PATHS=all` 时 `/`、`/monitor`、`/paper`、`/strategy-tracking` 返回 next marker。
  - `/assets/legacy.js` 在回滚窗口仍可访问。
  - `/next/assets/next.js` 正常访问。
  - API-only 模式不返回静态 HTML。
  - `readyz` 在 API-only 模式不依赖静态前端。

验收命令：

```bash
cd /Users/j/Documents/gupiao
backend/.venv/bin/pytest backend/tests/test_frontend_next_level1_cutover.py -q
git diff -- frontend strategy_policy.py | wc -l
```

通过标准：

- 测试通过。
- 未改旧 `frontend/`。
- 未改 `strategy_policy.py`。
- 未改变任何策略排序和生产语义。

### P2：短期线上切入口方案

目标：在不删除旧 dist 的情况下，让线上用户默认进入新前端。

推荐优先级：

1. 若当前仍由 `tquant-app-mysql` 服务静态资源，则优先用后端 cutover env/setting：

```env
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=true
FRONTEND_NEXT_CUTOVER_PATHS=all
```

2. 如果根入口 `/` 无法由现有 cutover 支持，则补 P1 代码后再部署。
3. 不删除 `frontend/dist`，仅让它不再作为默认入口。

切换后验证：

```bash
curl -k -fsS https://43.143.243.97/ | grep -E 'solid-vendor|tanstack-router|/next/assets|frontend-next'
curl -k -fsS https://43.143.243.97/monitor | grep -E 'solid-vendor|tanstack-router|/next/assets|frontend-next'
curl -k -fsS https://43.143.243.97/paper | grep -E 'solid-vendor|tanstack-router|/next/assets|frontend-next'
curl -k -fsS https://43.143.243.97/next/monitor | grep -E 'solid-vendor|tanstack-router|/next/assets'
curl -k -fsS https://43.143.243.97/readyz
```

页面验收：

- `/`
- `/monitor`
- `/monitor/market`
- `/paper`
- `/strategy-tracking`
- `/analysis`
- `/playbook`
- `/backtest`
- `/data`
- `/settings`
- `/next/monitor`

通过标准：

- 默认入口不再返回 `react-vendor`、`antd-*`。
- 默认入口返回 `frontend-next` 资产。
- `/next/*` 仍可访问。
- 旧 dist 未删除，回滚可用。

### P3：前后端分离部署正式化

目标：静态资源不再由后端 app worker 服务，降低 app 容器压力。

改造 `deploy/frontend/nginx.conf`：

1. root 默认指向 `frontend-next`：

```nginx
root /usr/share/nginx/html-next;
```

2. `/next/assets/` 继续强缓存：

```nginx
location /next/assets/ {
    add_header Cache-Control "public, max-age=31536000, immutable";
    alias /usr/share/nginx/html-next/assets/;
    try_files $uri =404;
}
```

3. `/next/` 返回 next index：

```nginx
location /next/ {
    add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
    alias /usr/share/nginx/html-next/;
    try_files $uri $uri/ /next/index.html;
}
```

4. `/` 和旧业务路由返回 next index：

```nginx
location / {
    add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
    try_files $uri $uri/ /index.html;
}
```

5. 旧前端回滚资源短期挂在只读路径，例如：

```nginx
location /__legacy/assets/ {
    add_header Cache-Control "public, max-age=31536000, immutable";
    alias /usr/share/nginx/html-root/assets/;
    try_files $uri =404;
}
```

说明：是否保留 `/assets/*` 给旧资源要按回滚窗口决定。若 `frontend-next` 构建产物仍引用 `/next/assets/*`，则 `/assets/*` 可以暂时保留旧资源，不影响新入口。

改造 `deploy/nginx/tquant-separated-gateway.conf.template`：

1. `/api/*`、`/readyz`、`/metrics`、`/ws/*` 只代理到 `backend-api:8000`。
2. `/next/*`、`/next/assets/*`、`/assets/*`、`/` 只代理到 `frontend-web:80`。
3. 静态资源不要再经过 Python app worker。

改造 `docker-compose.separated.yml`：

1. 保留 `frontend-web`。
2. 保留 `backend-api` 且设置：

```env
SERVE_FRONTEND_STATIC=false
```

3. `gateway` 作为统一入口。
4. 补健康检查：

```yaml
frontend-web:
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null && wget -qO- http://127.0.0.1/next/ >/dev/null"]
```

5. `backend-api` 健康检查只检查 API readiness。

验收命令：

```bash
cd /Users/j/Documents/gupiao
sudo docker compose -f docker-compose.mysql.yml ps
sudo docker compose -f docker-compose.separated.yml config
```

线上验证：

```bash
curl -k -fsS https://43.143.243.97/ | grep -E 'solid-vendor|tanstack-router|/next/assets'
curl -k -fsS https://43.143.243.97/next/monitor | grep -E 'solid-vendor|tanstack-router|/next/assets'
curl -k -fsS https://43.143.243.97/api/bff/v1/manifest
curl -k -fsS https://43.143.243.97/readyz
```

通过标准：

- 静态资源请求日志不再出现在 `tquant-app-mysql` 的 slow HTTP 日志中。
- `backend-api` 不再服务 SPA fallback。
- `frontend-web` 独立健康。
- `gateway` 统一公网入口。

### P3.5：部署脚本重构与独立部署单元

目标：部署脚本符合前端、后端、数据库、Worker 分离后的拓扑。只有 `frontend-next/` 改动时，只构建和发布前端静态产物，不重建后端镜像、不重启 MySQL、不跑 migration、不重启 worker。

#### 当前缺口

| 缺口 | 当前行为 | 风险 |
|---|---|---|
| scope 粒度太粗 | `resolve_deploy_scope` 只支持 `all`、`frontend-hot`、`go`、`ops` | `frontend-next/*` 改动会落到 `all`，触发全量部署 |
| 热前端只识别旧前端 | `frontend-hot` 只要求 `frontend/dist/index.html` | 新前端独立变更无法走热部署 |
| app 镜像同时承载 API 和静态资源 | `tquant-web:mysql` 同时跑后端和静态 fallback | 只改前端也可能重建 app 镜像 |
| 验证逻辑绑定单体容器 | `verify_remote` 默认等待 `tquant-app-mysql` 并要求 `frontend_dist=true` | API-only / separated compose 会被误判失败 |
| CI scope 只识别 `frontend/*` | workflow 未识别 `frontend-next/*` | 新前端提交无法自动选择前端 scope |
| 迁移与后端部署未拆开 | `all` 总是跑 migration 和 app/worker recreate | 纯 API 代码、纯 migration、纯 worker 改动不能按风险分层 |
| 数据库缺少只读保护 | scope 无法表达 `db-migration`、`db-backup`、`db-config` | 容易把 DB 变更混入普通部署 |

#### 目标部署单元

| Scope | 触发文件 | 本地 gate | 远端动作 | 不允许动作 |
|---|---|---|---|---|
| `frontend-next` | `frontend-next/**`、`deploy/frontend/nginx.conf` 中仅静态规则 | `cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build` | 上传 `frontend-next/dist`；更新 `frontend-web` 挂载目录或重建 `frontend-web` 静态镜像；reload/recreate `frontend-web` 与可选 `gateway` | 不 build/restart `backend-api`、不跑 migration、不动 MySQL、不重启 worker |
| `frontend-legacy` | `frontend/**`，仅回滚窗口内使用 | `cd frontend && npm run lint && npm test -- --run && npm run build && npm run analyze` | 上传 `frontend/dist` 到回滚目录；默认不作为公网入口 | 不切回旧入口，除非显式授权 |
| `backend-api` | `backend/app/**` 中 API/服务代码，非 migration/worker 专属 | `python compileall`、相关 pytest、API contract 测试 | build/restart `backend-api`；必要时 reload `gateway` | 不 rebuild `frontend-web`、不跑 migration，除非检测到 migration 文件 |
| `db-migration` | `backend/alembic/**`、`backend/app/models/**`、schema 变更 | migration smoke、备份检查、dry-run 或 heads 检查 | 先备份，再运行 `migration` 一次性容器；读回 schema version | 不自动部署前端；不清库；失败必须停止后续 app 重启 |
| `worker` | `backend/app/services/runtime/**`、`backend/scripts/*worker*`、`analytics/backtest` worker 专属 | worker 相关 pytest、compileall | build/restart `runtime-scheduler`、`runtime-worker`、`backtest-worker`、`analytics-worker` 中受影响服务 | 不重启前端；不跑 migration，除非同批含 schema 变更 |
| `go` | `go-services/**` | Go build/test | build/restart Go BFF/market-read/scan worker | 不重启 Python API 和前端 |
| `ops` | deploy scripts、nginx、compose、runbook、CI | shellcheck 或 bash dry-run、compose config、script contract pytest | 刷新配置、reload nginx/gateway、必要时重启目标 infra 容器 | 不部署业务代码，除非 scope 显式组合 |
| `all` | 多域混合或无法安全分类 | 全量 gate | 按 DB -> backend -> worker -> go -> frontend -> gateway 顺序执行 | 必须完整验证和保留回滚 |

说明：`auto` 只做 scope 解析，不是一个部署动作。解析结果必须打印到日志，例如 `resolved_deploy_units=frontend-next`。

#### Scope 解析规则

新增一个小型、可测试的解析器，优先放在 `scripts/deploy_scope.py`，由 shell 脚本和 CI 调用，避免 `quick_cloud_deploy.sh`、`deploy_cloud_server.sh`、`.github/workflows/ci.yml` 三处复制 case 逻辑。

建议输出 JSON：

```json
{
  "scope": "frontend-next",
  "units": ["frontend-next"],
  "requires_migration": false,
  "requires_backend_restart": false,
  "requires_frontend_next_build": true,
  "requires_legacy_frontend_build": false,
  "requires_worker_restart": false,
  "requires_go_restart": false,
  "requires_ops_reload": false,
  "reason": "only frontend-next files changed"
}
```

解析原则：

1. 仅 `frontend-next/**` 改动 -> `frontend-next`。
2. 仅 `frontend/**` 改动 -> `frontend-legacy`，并要求显式 `DEPLOY_ALLOW_LEGACY_FRONTEND=1` 才允许上线旧入口相关变更。
3. `backend/alembic/**` 或 schema model 变更 -> 至少包含 `db-migration`。
4. `backend/app/api/**`、`backend/app/services/**` 非 worker 专属 -> `backend-api`。
5. worker 专属路径 -> `worker`。
6. `go-services/**` -> `go`。
7. compose/nginx/deploy script -> `ops`，若影响具体服务，再组合对应 unit。
8. 多 unit 混合 -> 组合 scope，例如 `backend-api,worker`；若无法安全判断 -> `all`。
9. 文档-only -> `ops-docs` 或 `verify-only`，不得触发业务部署。
10. `strategy_policy.py` 改动 -> 阻断部署，要求人工复核。

示例：

| changed files | 解析结果 |
|---|---|
| `frontend-next/src/features/paper/PaperPage.tsx` | `frontend-next` |
| `frontend-next/src/**` + `deploy/frontend/nginx.conf` | `frontend-next,ops` |
| `backend/app/api/routes/paper.py` | `backend-api` |
| `backend/alembic/versions/20260609_x.py` | `db-migration,backend-api` |
| `backend/app/services/runtime/task_scheduler.py` | `worker` |
| `go-services/bff/**` | `go` |
| `frontend-next/**` + `backend/app/api/**` | `frontend-next,backend-api` |
| `strategy_policy.py` | `blocked: strategy_policy requires explicit approval` |

#### 脚本接口设计

`scripts/one_click_cloud_deploy.sh`：

```bash
scripts/one_click_cloud_deploy.sh --scope auto
scripts/one_click_cloud_deploy.sh --scope frontend-next
scripts/one_click_cloud_deploy.sh --scope backend-api
scripts/one_click_cloud_deploy.sh --scope db-migration
scripts/one_click_cloud_deploy.sh --scope worker
scripts/one_click_cloud_deploy.sh --scope go
scripts/one_click_cloud_deploy.sh --scope all
```

新增参数：

| 参数 | 默认 | 用途 |
|---|---|---|
| `--compose-topology <monolith|separated>` | `monolith`，正式切换后改 `separated` | 选择 `docker-compose.mysql.yml` 或 `docker-compose.separated.yml` |
| `--scope <auto|frontend-next|frontend-legacy|backend-api|db-migration|worker|go|ops|all>` | `auto` | 指定部署单元 |
| `--changed-files-from <file>` | 空 | CI 或人工传入 changed file 清单 |
| `--frontend-next-required` | false | `frontend-next` scope 缺少 dist 时失败，不回退全量 |
| `--api-only` | false | 后端以 `SERVE_FRONTEND_STATIC=false` 验证 |
| `--plan-only` | false | 只输出解析结果、将执行的命令和风险，不上传 |

环境变量：

```env
DEPLOY_COMPOSE_TOPOLOGY=separated
CLOUD_COMPOSE_FILE=docker-compose.separated.yml
DEPLOY_TARGET_SCOPE=auto
DEPLOY_FRONTEND_NEXT_REQUIRED=1
DEPLOY_ALLOW_LEGACY_FRONTEND=0
SERVE_FRONTEND_STATIC=false
FRONTEND_WEB_SERVICE=frontend-web
BACKEND_API_SERVICE=backend-api
GATEWAY_SERVICE=gateway
```

#### 打包策略

| Scope | package 内容 |
|---|---|
| `frontend-next` | `frontend-next/dist/**`、`deploy/frontend/nginx.conf`、可选 `docker-compose.separated.yml` |
| `frontend-legacy` | `frontend/dist/**`，默认只上传到回滚目录 |
| `backend-api` | `backend/**`、`deploy/backend-api/**`、compose 中 backend 相关配置 |
| `db-migration` | `backend/alembic/**`、`backend/app/models/**`、migration runner 所需代码 |
| `worker` | `backend/**` 中 worker 依赖、worker Dockerfile/compose |
| `go` | `go-services/**` |
| `ops` | `deploy/**`、`scripts/**`、compose、runbook |
| `all` | 当前完整包 |

`delta-package` 要按 unit 计算删除清单：

1. `frontend-next` 删除只允许发生在远端 `frontend-next/dist` 发布目录。
2. 禁止 delta 删除 `.env`、`.runtime`、`backend/data`、MySQL volume、Redis volume、日志、备份。
3. `db-migration` scope 禁止应用自动删除；migration 只允许通过 Alembic 升级/降级脚本改变 schema。

#### 远端执行顺序

`frontend-next`：

```bash
cd /home/ubuntu/gupiao-upload
test -f frontend-next/dist/index.html
sudo docker compose -f docker-compose.separated.yml up -d --no-deps --force-recreate frontend-web
sudo docker compose -f docker-compose.separated.yml exec -T frontend-web wget -qO- http://127.0.0.1/ >/tmp/frontend-web-home.html
```

若尚未正式启用 separated compose，短期兼容路径：

```bash
sudo docker exec -u root tquant-app-mysql sh -c 'rm -rf /app/frontend-next/dist && mkdir -p /app/frontend-next/dist'
sudo docker cp frontend-next/dist/. tquant-app-mysql:/app/frontend-next/dist/
sudo docker exec -u root tquant-app-mysql sh -c 'chmod -R a+rX /app/frontend-next/dist'
```

但兼容路径只能作为过渡，日志必须输出 `frontend_next_hot:monolith_compat`，避免误认为已经前后端分离。

`backend-api`：

```bash
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.separated.yml build backend-api
sudo docker compose -f docker-compose.separated.yml up -d --no-deps --force-recreate backend-api
curl -fsS http://127.0.0.1:${BACKEND_API_PORT:-18091}/readyz
```

`db-migration`：

```bash
cd /home/ubuntu/gupiao-upload
./scripts/backup_database.sh
sudo docker compose -f docker-compose.mysql.yml up --no-build --force-recreate --abort-on-container-exit --exit-code-from migration migration
sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e 'SELECT 1;'
```

`worker`：

```bash
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml build runtime-scheduler runtime-worker backtest-worker analytics-worker
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-scheduler runtime-worker backtest-worker analytics-worker
```

`go`：

```bash
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml build go-bff-gateway go-market-read-service go-scan-worker
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate go-bff-gateway go-market-read-service go-scan-worker
```

组合 scope 的顺序固定为：

```text
ops preflight -> db-migration -> backend-api -> worker -> go -> frontend-next -> gateway reload -> verify
```

#### 验证策略

按 scope 验证，不再所有部署都跑全量容器检查。

| Scope | 必须验证 |
|---|---|
| `frontend-next` | `/` 或 `/next/monitor` 返回 new frontend marker；`/next/assets/*` 200；浏览器 smoke 无 chunk 缺失；`backend-api` 容器镜像 ID 未变 |
| `backend-api` | `/readyz` ok；`/api/__missing_smoke__` JSON 404；受保护 API 401/403；`frontend-web` 容器镜像 ID 未变 |
| `db-migration` | backup 成功；migration exit code 0；schema version 读回；`SELECT 1` 成功 |
| `worker` | worker 容器 healthy/running；无 `WORKER TIMEOUT`、`SIGKILL` 新增；低优先暂停配置保持 |
| `go` | Go 服务 `/readyz` ok；BFF manifest 或 monitor 热读 smoke 通过 |
| `ops` | `docker compose config` 通过；nginx reload 成功；API/static 路由 smoke 通过 |
| `all` | 以上全部 |

新增反向断言：

1. `frontend-next` scope 不允许出现 `docker compose build backend-api`、`build app`、`migration`。
2. `backend-api` scope 不允许上传或删除 `frontend-next/dist`。
3. `db-migration` scope 必须先备份，且 migration 失败不得继续重启 app。
4. `ops-docs` 或 docs-only 不允许上传业务包。
5. `strategy_policy.py` 出现在 changed files 时，脚本直接失败并打印人工审批要求。

#### 测试计划

更新 `backend/tests/test_cloud_deploy_scripts.py`：

1. `test_scope_resolver_routes_frontend_next_only_to_frontend_next`：
   - 输入 `frontend-next/src/App.tsx`
   - 期望 `scope=frontend-next`
   - 期望不包含 `backend-api`、`db-migration`
2. `test_frontend_next_scope_does_not_build_backend_or_run_migration`：
   - 读取 `scripts/deploy_cloud_server.sh`
   - 断言 `frontend-next` 分支只更新 `frontend-web` 或兼容更新 `/app/frontend-next/dist`
   - 断言该分支没有 `migration`、`build app`、`build backend-api`
3. `test_backend_api_scope_restarts_api_only`：
   - 断言 `backend-api` scope build/up `backend-api`
   - 断言不 touch `frontend-next/dist`
4. `test_db_migration_scope_requires_backup_before_migration`：
   - 断言 `backup_database.sh` 在 migration 前执行
   - 断言 migration 失败阻断后续重启
5. `test_ci_scope_selector_recognizes_frontend_next`：
   - 读取 `.github/workflows/ci.yml`
   - 断言 `frontend-next/*` 映射 `frontend-next`
6. `test_verify_remote_is_scope_aware_for_separated_topology`：
   - 断言 `verify_remote` 不再对每个 scope 都等待 `tquant-app-mysql`
   - 断言 separated topology 验证 `tquant-frontend-web`、`tquant-backend-api`

新增 `scripts/deploy_scope.py` 单测可放在 `backend/tests/test_deploy_scope.py`，覆盖：

```text
frontend-next only -> frontend-next
frontend only -> frontend-legacy
backend api only -> backend-api
migration only -> db-migration,backend-api
worker only -> worker
go only -> go
docs only -> ops-docs/verify-only
strategy_policy.py -> blocked
mixed frontend-next + backend -> frontend-next,backend-api
unknown file -> all
```

#### CI/CD 调整

`.github/workflows/ci.yml`：

1. 新增 `frontend-next-dist` artifact：

```text
cd frontend-next
npm ci
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
upload-artifact: frontend-next-dist -> frontend-next/dist
```

2. 部署 job 下载：

```text
frontend-dist -> frontend/dist
frontend-next-dist -> frontend-next/dist
```

3. 用 `scripts/deploy_scope.py` 取代内联 shell case。
4. 将 `DEPLOY_CHANGED_FILES` 传给脚本。
5. 对 `frontend-next` scope 设置：

```env
DEPLOY_FRONTEND_NEXT_REQUIRED=1
RUN_COMPILE=0
RUN_FRONTEND_BUILD=0
RUN_STRATEGY_TEST=0
RUN_FULL_TESTS=0
RUN_LATEST_DATA_ACCEPTANCE=0
```

6. 对 `db-migration` scope 强制：

```env
RUN_REMOTE_PREFLIGHT=1
LATEST_DATA_ACCEPTANCE_REQUIRED=0
```

#### 回滚策略

`frontend-next` 独立回滚：

1. 发布前远端保留上一份：

```bash
cp -a frontend-next/dist ".runtime/frontend-next-dist-backup-$(date +%Y%m%d%H%M%S)"
```

2. 回滚只恢复静态目录并重启 `frontend-web`：

```bash
rm -rf frontend-next/dist
cp -a .runtime/frontend-next-dist-backup-<ts> frontend-next/dist
sudo docker compose -f docker-compose.separated.yml up -d --no-deps --force-recreate frontend-web
```

3. 不重启 `backend-api`、MySQL、worker。

`backend-api` 回滚：

1. 用上一镜像 tag 或上一 release 代码重建 `backend-api`。
2. 不改 `frontend-web`。
3. 若同批没有 migration，则不碰数据库。
4. 若已执行 migration，按 Alembic downgrade/forward-fix 单独处理，不允许脚本自动清库。

`db-migration` 回滚：

1. 首选 forward-fix migration。
2. downgrade 需人工确认。
3. 数据库备份只作为灾难恢复，不作为普通回滚首选。

#### 开发执行顺序

1. 写 `scripts/deploy_scope.py` 和单测，先让 scope 解析脱离 shell。
2. 改 `quick_cloud_deploy.sh` 参数和 summary，兼容旧 scope 名称：
   - `frontend-hot` 作为 `frontend-legacy` 别名。
   - 新增 `frontend-next`。
3. 改 `deploy_cloud_server.sh`：
   - 分出 `remote_deploy_frontend_next`。
   - 分出 `remote_deploy_backend_api`。
   - 分出 `remote_deploy_db_migration`。
   - 分出 `remote_deploy_workers`。
   - 分出 `remote_deploy_go_services`。
   - `remote_deploy_all` 按固定顺序组合调用。
4. 改 `verify_remote` 为 scope-aware：
   - `verify_frontend_next_remote`
   - `verify_backend_api_remote`
   - `verify_db_remote`
   - `verify_worker_remote`
   - `verify_go_remote`
5. 改 `.github/workflows/ci.yml`，使用统一 resolver。
6. 更新 `.env.deploy.local.example` 和 Makefile 快捷入口：

```make
deploy-cloud-next:
	./scripts/one_click_cloud_deploy.sh --scope frontend-next --frontend-next-required

deploy-cloud-api:
	./scripts/one_click_cloud_deploy.sh --scope backend-api

deploy-cloud-db:
	./scripts/one_click_cloud_deploy.sh --scope db-migration
```

7. 更新部署 runbook 和本计划文档。
8. 本地验证全绿后再等待用户单独授权部署。

#### 最低验证命令

```bash
cd /Users/j/Documents/gupiao
backend/.venv/bin/pytest backend/tests/test_cloud_deploy_scripts.py backend/tests/test_deploy_scope.py -q
bash scripts/one_click_cloud_deploy.sh --dry-run --scope frontend-next --frontend-next-required
bash scripts/one_click_cloud_deploy.sh --dry-run --scope backend-api
bash scripts/one_click_cloud_deploy.sh --dry-run --scope db-migration
DEPLOY_CHANGED_FILES='frontend-next/src/index.tsx' bash scripts/one_click_cloud_deploy.sh --dry-run --scope auto
sudo docker compose -f docker-compose.separated.yml config
git diff -- frontend strategy_policy.py | wc -l
```

通过标准：

- `frontend-next` only 改动解析为 `frontend-next`。
- `frontend-next` 部署路径不 build/restart backend、MySQL、worker。
- `backend-api` 部署路径不上传/删除前端 dist。
- `db-migration` 部署路径强制备份并阻断失败后的后续步骤。
- `strategy_policy.py` 改动被脚本阻断。
- `git diff -- frontend strategy_policy.py | wc -l` 为 `0`，除非用户明确要求改旧前端。

### P4：资源释放和稳定性治理

目标：真正解决卡顿主因。

短期止血：

```env
RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true
RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED=true
RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED=false
```

检查并限制：

1. `runtime-worker` 高占用任务。
2. 24 个月回测、data_backfill、analytics export、ML/factor mining 等低优先任务。
3. MySQL buffer 和连接数。
4. app worker 数量和内存。
5. Redis timeout。

线上确认命令：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sudo docker stats --no-stream
free -m
vmstat 1 5
sudo docker compose -f docker-compose.mysql.yml logs --tail=200 app | egrep 'WORKER TIMEOUT|SIGKILL|slow_http_request|redis.exceptions.TimeoutError|bff workspace timed out'
```

目标：

- swap 使用率低于 30%。
- 无 app worker OOM/SIGKILL。
- `/api/bff/v1/workspace/monitor?view=market` p95 < 800ms。
- `/api/bff/v1/workspace/strategy` p95 < 1000ms。
- 静态资源无 3s 以上 slow HTTP。

### P5：全量验证

本地验证：

```bash
cd /Users/j/Documents/gupiao
backend/.venv/bin/pytest backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_bff_routes.py backend/tests/test_bff_monitor_workspace.py -q

cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run chunk:profile
npm run css:budget
```

线上只读验证：

```bash
curl -k -fsS https://43.143.243.97/readyz
curl -k -fsS https://43.143.243.97/ | grep -E 'solid-vendor|tanstack-router|/next/assets'
curl -k -fsS https://43.143.243.97/monitor | grep -E 'solid-vendor|tanstack-router|/next/assets'
curl -k -fsS https://43.143.243.97/paper | grep -E 'solid-vendor|tanstack-router|/next/assets'
curl -k -fsS https://43.143.243.97/api/bff/v1/manifest
```

Playwright 页面验收：

1. 使用正式账号 `915927066` 登录。
2. 逐页打开：
   - `/`
   - `/monitor`
   - `/monitor/market`
   - `/paper`
   - `/strategy-tracking`
   - `/analysis`
   - `/playbook`
   - `/backtest`
   - `/data`
   - `/settings`
   - `/next/monitor`
3. 记录：
   - 页面是否打开。
   - 控制台错误。
   - 关键 API。
   - 内容可见时间。
   - 慢 API。
   - 是否仍引用旧 `react-vendor` / `antd-*`。

### P6：冷却期与旧 dist 退役

冷却期建议至少 3 个交易日。

冷却期内：

1. 保留 `frontend/dist`。
2. 保留旧路由回滚开关。
3. 每日记录：
   - `/` 是否为新前端。
   - BFF p95。
   - swap 使用。
   - worker timeout。
   - 用户反馈。

冷却期后再决定是否删除或不再上传旧 `frontend/dist`。

删除前必须满足：

- 3 个交易日无 P0/P1 问题。
- 所有业务入口已由 `frontend-next` 覆盖。
- 回滚方式从旧 dist 回滚改为上一版本新前端回滚。
- 用户明确授权删除旧前端回滚产物。

## 回滚方案

### 快速回滚

若使用后端 cutover：

```env
FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED=false
FRONTEND_NEXT_CUTOVER_PATHS=
```

重启或刷新配置后验证：

```bash
curl -k -fsS https://43.143.243.97/ | grep -E 'react-vendor|antd-|/assets/index-'
curl -k -fsS https://43.143.243.97/monitor | grep -E 'react-vendor|antd-|/assets/index-'
```

### 分离部署回滚

若使用 `frontend-web`：

1. 将 `deploy/frontend/nginx.conf` root 或 fallback 恢复到旧 `html-root`。
2. reload `frontend-web` 或 `gateway`。
3. 不改数据库。
4. 不改策略服务。
5. 验证旧入口、API、readyz。

### 回滚保护

回滚时禁止：

- 删除 `frontend-next/dist`。
- 改生产策略排序。
- 改 `strategy_policy.py`。
- 清空数据库或缓存。
- 执行非隔离写操作。

## 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 根入口切到新前端后用户发现页面缺功能 | 影响自用 | 保留旧 dist 和快速回滚开关 |
| 新前端依赖 `/next/assets`，根入口路径不一致 | 白屏或动态 import 失败 | 验证 HTML asset path；构建 base 必须稳定 |
| 后端 API-only 后 `readyz` 错误要求 frontend dist | 健康检查失败 | 保持 `SERVE_FRONTEND_STATIC=false` 测试 |
| 静态资源仍由 app 容器服务 | 无法释放 app 压力 | 上分离部署，静态由 `frontend-web` 服务 |
| worker/swap 不处理 | 页面仍偶发卡顿 | P4 必须作为 cutover 后稳定性 gate |
| 旧 `/assets/*` 与新 `/next/assets/*` 混用 | 缓存或 hash 混乱 | 新前端统一 `/next/assets`，旧资源只回滚窗口保留 |

## 验收矩阵

| 模块 | 验收点 | 通过标准 |
|---|---|---|
| 默认入口 | `/` | 返回 `frontend-next` HTML，不含旧 `react-vendor` / `antd-*` |
| 旧业务路由 | `/monitor` 等 | 返回 `frontend-next` 或 301 到 `/next/*` |
| 新业务路由 | `/next/*` | 保持可访问 |
| 静态资源 | `/next/assets/*` | 200，强缓存 |
| API | `/api/*` | 不被 SPA fallback 吞掉 |
| 后端 API-only | `SERVE_FRONTEND_STATIC=false` | 后端不服务前端静态 |
| 部署 scope | `frontend-next` only | 只上传/重建 `frontend-web`，不重启 API、MySQL、worker |
| 部署 scope | `backend-api` only | 只 build/restart `backend-api`，不 touch frontend dist |
| 部署 scope | `db-migration` | 先备份，再 migration，失败阻断后续服务重启 |
| 部署 scope | `worker` / `go` | 只重启对应 worker 或 Go 服务 |
| 部署保护 | `strategy_policy.py` changed | 脚本阻断并要求人工授权 |
| 资源 | swap、load、worker timeout | 降到目标范围 |
| 回滚 | 旧 dist | 保留并可恢复 |
| 策略 | `priority_board`、`production_score` | 完全不变 |

## 最终交付物

1. 代码改动：
   - cutover 根入口和业务路由支持。
   - nginx/frontend-web 分离配置。
   - API-only 健康检查和测试。
   - 部署脚本 scope-aware 重构。
   - `frontend-next`、`backend-api`、`db-migration`、`worker`、`go` 独立部署路径。
   - CI 变更文件解析和 artifact 下载更新。
2. 测试：
   - 后端 cutover 单测。
   - 部署 scope 解析和部署脚本契约测试。
   - frontend-next 全量本地检查。
   - Playwright 线上只读验收。
3. 报告：
   - 入口切换验证结果。
   - 分离部署验证结果。
   - 独立部署 dry-run 和反向断言结果。
   - 资源基线/对比报告。
4. 明确结论：
   - 旧前端是否仍作为默认入口。
   - 是否已释放后端静态资源压力。
   - 只改前端是否已做到只部署前端。
   - 前端、后端、数据库、Worker 是否已可独立部署。
   - 是否仍有 worker/swap/BFF 慢读 blocker。

## 可直接执行的提示词

```text
你在 /Users/j/Documents/gupiao 工作。目标：按 docs/frontend-next-default-entry-and-separated-deployment-plan-2026-06-09.md 实施“停旧前端默认入口 + frontend-next 默认入口 + 前后端分离部署准备 + 部署脚本独立部署重构 + 资源稳定性加固”。开始前先运行 git status --short，保护已有脏改动，尤其不要覆盖 docs/reports/frontend-next-chunk-profile-2026-06-08.* 和 docs/reports/frontend-next-css-* 报告副产物。

硬边界：
1. 不改 strategy_policy.py。
2. 不改变生产策略语义、production_score、priority_board 排序和口径。
3. 不做自动交易变更。
4. 不删除 frontend/dist，旧前端仅从默认入口停用，保留回滚。
5. 未获明确授权前不部署、不切流；本轮只做代码、测试、dry-run 和文档。
6. 后端只做入口/健康检查/契约所需最小改动；不碰策略公式。
7. 真实写操作必须隔离写入、rollback、读回一致、403 权限断言。

实施范围：
- backend/app/main.py
- backend/app/services/frontend_next_cutover.py
- backend/tests/test_frontend_next_level1_cutover.py
- docker-compose.separated.yml
- deploy/frontend/nginx.conf
- deploy/nginx/tquant-separated-gateway.conf.template
- scripts/deploy_scope.py
- scripts/one_click_cloud_deploy.sh
- scripts/quick_cloud_deploy.sh
- scripts/deploy_cloud_server.sh
- scripts/deploy_delta_package.py
- backend/tests/test_cloud_deploy_scripts.py
- backend/tests/test_deploy_scope.py
- .github/workflows/ci.yml
- .env.deploy.local.example
- Makefile
- 必要的 docs/operations 或报告

任务：
1. 建立当前入口和资源基线：确认 / 返回旧 React/AntD，/next/monitor 返回 frontend-next；记录 docker stats、free -m、vmstat。
2. 补本地 cutover 契约：支持根入口 / 和旧业务路由在 FRONTEND_NEXT_CUTOVER_PATHS=all 时走 frontend-next；/next/* 保持；/api/* 不被 SPA fallback 吞掉；SERVE_FRONTEND_STATIC=false 时后端为 API-only。
3. 补/更新测试：覆盖 /、/monitor、/paper、/strategy-tracking、/next/assets、/assets 旧资源回滚、API-only readyz。
4. 调整分离部署配置：frontend-web 默认服务 frontend-next，backend-api 设置 SERVE_FRONTEND_STATIC=false，gateway 将 /api、/readyz、/metrics、/ws 转后端，其余静态转 frontend-web；旧 frontend/dist 只保留回滚窗口。
5. 重构部署脚本：新增统一 scripts/deploy_scope.py，把 auto scope 从 shell/CI 内联 case 抽成可测试解析器；支持 frontend-next、frontend-legacy、backend-api、db-migration、worker、go、ops、all；strategy_policy.py 改动必须阻断。
6. 实现独立部署路径：frontend-next scope 只上传/重建 frontend-web，不重启 backend-api、MySQL、worker；backend-api scope 只 build/restart API；db-migration scope 先备份再 migration 且失败阻断；worker/go scope 只重启对应服务；all 按 db -> api -> worker -> go -> frontend -> gateway 顺序。
7. 改 CI：frontend-next 产物单独 artifact；changed files 调用 deploy_scope.py；frontend-next only 自动选择 frontend-next scope。
8. 补部署脚本测试：覆盖 scope 解析、frontend-next 不 build backend、不跑 migration、backend-api 不 touch dist、db-migration 必须备份、strategy_policy 阻断、separated topology scope-aware verify。
9. 给出资源释放加固方案：暂停/降频低优先 runtime-worker，降低 swap，避免 app worker 继续服务静态资源，BFF 冷读返回缓存并异步刷新。
10. 本地验证：backend pytest cutover 和 deploy script 测试；frontend-next api:check/typecheck/lint/test/build/e2e/chunk/css；docker compose separated config；deploy dry-run；git diff -- frontend strategy_policy.py | wc -l 必须为 0。
11. 输出报告：记录改动、验证命令、dry-run 结果、风险、回滚步骤、是否仍需用户授权部署。

最终交付：
- 修复代码和测试。
- 更新/新增报告。
- 不部署、不切流，除非用户单独授权。
- 明确说明旧前端是否仍默认入口、frontend-next 是否可作为默认入口、前后端分离是否完成、只改前端是否只部署前端、数据库/后端/Worker 是否可独立部署、资源问题是否缓解。
```
