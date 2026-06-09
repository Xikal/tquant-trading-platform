# 生产化收尾手册

## 1. 关于 “使用本地 Navicat”

`Navicat` 是数据库管理工具，不是数据库服务本身。  
这套系统建议按下面方式落地：

- 数据库服务：本机 `MySQL 8.x` 或 `MariaDB`
- 管理工具：`Navicat`
- 应用连接：`SQLAlchemy + PyMySQL`

## 2. 在 Navicat 中准备数据库

先确保你的本机已经运行 MySQL 或 MariaDB。

在 Navicat 中新建连接后，执行：

```sql
CREATE DATABASE IF NOT EXISTS t_quant
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;
```

推荐数据库连接串：

```text
mysql+pymysql://root:<DB_PASSWORD>@127.0.0.1:3306/t_quant?charset=utf8mb4
```

`<DB_PASSWORD>` 是占位符。不要把真实密码写进脚本、提交到 Git，或粘贴到日志里。

## 3. 页面内完成切换

进入系统配置页后：

1. 在 `数据库 URL` 中填写 MySQL 连接串
2. 点击 `检测数据库连接`
3. 点击 `迁移 SQLite 到目标库`
4. 重启后端

数据库切换会写入：

```text
backend/data/runtime.env
```

重启后端后，会优先读取这里的 `DATABASE_URL`。

大模型与数据源配置保存后也会同步写入这个文件，因此正常情况下只需要配置一次。

## 4. 命令行方式

### 检测连接

```bash
cd backend
.venv/bin/python scripts/db_admin.py check \
  --url 'mysql+pymysql://root:<DB_PASSWORD>@127.0.0.1:3306/t_quant?charset=utf8mb4'
```

### 迁移 SQLite 到 MySQL

```bash
cd backend
.venv/bin/python scripts/db_admin.py migrate \
  --target-url 'mysql+pymysql://root:<DB_PASSWORD>@127.0.0.1:3306/t_quant?charset=utf8mb4' \
  --activate
```

如果目标库不是空库，可以加：

```bash
--overwrite
```

## 5. 本地启动

如果你希望统一用一个入口执行命令，也可以直接使用根目录：

```bash
make qa
make ui-smoke
make prod-preflight
make public-up
make public-down
```

### 后端

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend
npm run dev
```

### Runtime Data Fallback

Latest-data gaps, stuck `runtime_tasks`, empty priority board recovery, and runtime-worker startup checks are documented in [runtime-data-fallback-runbook.md](docs/operations/runtime-data-fallback-runbook.md).

### Deployment Topology And Workers

Independent Web, runtime-worker, scheduler, analytics-worker and backtest-worker operation is documented in [deployment-topology-runbook.md](docs/operations/deployment-topology-runbook.md) and [worker-runbook.md](docs/operations/worker-runbook.md).

## 5.1 单端口生产化运行

后端现在会直接托管 `frontend/dist`，所以构建前端后，可以只启动后端：

```bash
./scripts/run_local_prod.sh
```

访问：

```text
http://127.0.0.1:8000
```

健康检查：

```text
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/readyz
```

如需指定监听地址或端口：

```bash
HOST=0.0.0.0 PORT=18080 ./scripts/run_local_prod.sh
```

## 5.1.1 发布前预检查

上线前建议先执行：

```bash
./scripts/prod_preflight.sh
```

这套脚本会自动完成：

- 前端生产构建
- 后端编译检查
- API 冒烟测试
- 单端口生产模式验活（检查 `/`、`/api/settings`、`/readyz`）

如果要补浏览器层验证，可额外执行：

```bash
./scripts/ui_smoke.sh http://127.0.0.1:18080
```

脚本会输出四张截图到 `.runtime/ui-smoke/<host_port>/`，并在结束后自动清理临时测试自选股。
当前默认输出：

- `dashboard.png`
- `analysis.png`
- `research.png`
- `settings.png`

同时会先调用一次 `/api/backtests`，确认研究链路可用。

## 5.2 临时公网发布

项目根目录已提供：

```bash
./scripts/run_local_prod.sh
./scripts/prod_preflight.sh
./scripts/runtime_snapshot.sh
./scripts/run_public_app.sh
./scripts/stop_public_app.sh
```

这套脚本会：

- 构建前端
- 启动后端
- 建立临时公网隧道（优先 `localhost.run`，失败自动回退 `localtunnel`）
- 把公网地址写入 `.runtime/public_url.txt`
- 把隧道提供方写入 `.runtime/tunnel_provider.txt`

如需查看当前实例状态：

```bash
./scripts/runtime_snapshot.sh
```

也可以检查公网实例：

```bash
./scripts/runtime_snapshot.sh https://你的公网地址
```

## 6. 当前生产化补齐内容

- 支持 `MySQL + PyMySQL`
- 支持数据库连接检测
- 支持从 SQLite 一键迁移到外部数据库
- 支持把目标数据库写入运行时配置并在重启后自动生效
- 支持把大模型 / 数据源配置写入运行时配置并长期保留
- 保留 SQLite 作为默认开箱即用方案
- 支持 Docker 单容器 SQLite 持久部署
- 支持 Docker 双容器 MySQL 持久部署
- 支持最低目标盈利阈值配置，默认 `3%`

## 7. Docker 持久部署

### 7.0 云服务器一键部署

项目根目录已提供云端快速部署脚本：

```bash
CLOUD_HOST=<server-ip-or-domain> \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
./scripts/deploy_cloud_server.sh
```

默认行为：

- 本地执行后端编译、核心策略测试和前端构建。
- `DEPLOY_SYNC_MODE=delta-package` 时优先上传 changed/new files 与删除 manifest；缺远端 manifest、关键文件变更、变更比例过高、校验失败或删除不安全时自动回退 `package-only`。
- `DEPLOY_SYNC_MODE=package-only` 会打包当前项目，排除 `.runtime`、虚拟环境、`node_modules`、本地数据库运行配置等非发布内容。
- 远端 GitHub clone/fetch 默认不使用；只有显式设置 `DEPLOY_SYNC_MODE=git-inplace` 或 `DEPLOY_SYNC_MODE=git-clone` 才启用。
- 备份远端当前 `/home/ubuntu/gupiao-upload`。
- 使用 `docker-compose.mysql.yml` 先执行 `migration` 容器完成 Alembic 迁移，再重建 `app`、`runtime-scheduler`、`runtime-worker`、`backtest-worker`，不删除 MySQL volume。
- `analytics-worker` 默认按需，不是常驻部署验收项；只有设置 `DEPLOY_WITH_ANALYTICS_WORKER=1` 或 `scripts/quick_cloud_deploy.sh --with-analytics-worker` 时才拉起并校验。
- 自动验证 `/readyz`、默认低吸接口和前端首页。
- 部署日志输出 `sync_mode`、`changed_count`、`deleted_count`、`delta_bytes`、`full_bytes`、`upload_seconds`、`fallback_reason`，用于比较差量上传和全量包。

2026-06-08 起，云端部署还必须通过资源 gate。根分区、swap、Docker build cache、journal、MySQL volume/binlog/slow log、部署归档、MySQL 备份和 worker 连接预算都要先生成报告；blocking 时停止部署，不切流，不用删除 MySQL `.ibd`、直接删除 binlog 或 Docker volume 规避。

```bash
python3 scripts/collect_platform_resource_report.py \
  --json-output docs/reports/platform-resource-baseline-$(date +%F).json \
  --markdown-output docs/reports/platform-resource-baseline-$(date +%F).md
python3 scripts/verify_platform_budget.py \
  --json-output docs/reports/platform-budget-$(date +%F).json \
  --markdown-output docs/reports/platform-budget-$(date +%F).md
python3 scripts/verify_platform_optimization_readiness.py \
  --json-output docs/reports/platform-optimization-readiness-$(date +%F).json \
  --markdown-output docs/reports/platform-optimization-readiness-$(date +%F).md \
  --fail-on-blocking
```

资源配置、slow log 轮转、binlog 保留、BuildKit GC、manifest 导出和回滚步骤见 [mysql-maintenance-runbook.md](docs/operations/mysql-maintenance-runbook.md)。`scripts/quick_cloud_deploy.sh --verify-only` 会执行只读资源 preflight；输出 warning/blocking 后先处理资源项，再继续部署。

常用参数：

```bash
CLOUD_PROJECT_DIR=/home/ubuntu/gupiao-upload
CLOUD_COMPOSE_FILE=docker-compose.mysql.yml
CLOUD_APP_PORT=18090
CLOUD_KEEP_BACKUPS=3
RUN_FULL_TESTS=1
DEPLOY_SYNC_MODE=delta-package
```

若差量上传异常，可显式关闭：

```bash
DEPLOY_SYNC_MODE=package-only ./scripts/deploy_cloud_server.sh
```

差量删除只允许删除上一版 `.runtime/deploy-manifest.json` 中存在的文件，且禁止删除 `.env`、`.runtime`、数据库、备份、上传产物和运行时数据。

如果没有 SSH key，也可以临时使用：

```bash
CLOUD_PASSWORD='服务器密码' ./scripts/deploy_cloud_server.sh
```

不要把密码写入脚本或提交到仓库。

### 7.0.1 云服务器清理

清理脚本默认只预览，不删除：

```bash
CLOUD_HOST=<server-ip-or-domain> \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
./scripts/cloud_server_cleanup.sh
```

确认无误后执行实际清理：

```bash
CLOUD_HOST=<server-ip-or-domain> \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
APPLY=1 \
KEEP_BACKUPS=1 \
./scripts/cloud_server_cleanup.sh
```

清理范围：

- 历史上传包 `gupiao-deploy-*.tgz`。
- 临时校验脚本。
- 旧热补丁备份目录 `gupiao-upload.prev*`、`gupiao-upload-backup-*`。
- 超出保留数量的部署备份目录。
- Docker 构建缓存和 dangling image。

不会删除：

- 当前运行目录 `/home/ubuntu/gupiao-upload`。
- MySQL 数据卷。
- App runtime 数据卷。

如确认公网 nginx 仍代理到 `127.0.0.1:18090`，可在单独授权后停掉未对外服务的分离验证栈：

```bash
CLOUD_HOST=<server-ip-or-domain> \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
STOP_SEPARATED_STACK=1 \
APPLY=1 \
./scripts/cloud_server_cleanup.sh
```

脚本会先检查 nginx 中存在 `proxy_pass http://127.0.0.1:18090`；不满足则拒绝执行 separated stack stop。

### 7.1 SQLite 单容器

```bash
cp .env.docker.example .env
APP_PORT=18080 docker compose -f docker-compose.sqlite.yml up -d --build
```

说明：

- Compose 项目名固定为 `tquant-sqlite`
- 示例应用端口为 `18080`
- SQLite 数据保存在 Docker volume `sqlite_data`
- 浏览器直接访问 `http://127.0.0.1:18080`

停止：

```bash
docker compose -f docker-compose.sqlite.yml down
```

### 7.2 MySQL 双容器

```bash
cp .env.docker.example .env
APP_PORT=18090 docker compose -f docker-compose.mysql.yml up -d --build
```

说明：

- Compose 项目名固定为 `tquant-mysql`
- MySQL 数据保存在 Docker volume `mysql_data`
- 应用运行时缓存和运行配置保存在 `app_runtime_data`
- `migration` 容器会先执行 `alembic upgrade head`，成功后才启动 Web/API 与后台 worker
- `app` 容器默认关闭运行时后台任务，只负责 Web/API 响应
- `runtime-worker` 容器运行 `python -m app.workers.runtime_worker`，消费 `runtime_tasks` 持久化任务队列
- `runtime-scheduler` 容器独立运行 `python -m app.workers.runtime_scheduler`，负责周期性入队；Web 容器不打开调度循环
- `backtest-worker` 容器独立消费回测任务
- `analytics-worker` 通过 `profiles: ["analytics"]` 按需启动，消费 `strategy_24m_duckdb_report`、`analytics_export_daily_bars`、`analytics_quality_check`、`data_quality_sla_refresh`、`data_repair_run` 等分析与数据质量任务，并在镜像构建时通过 `INSTALL_ANALYTICS=1` 安装 `duckdb`、`pyarrow`
- `go-bff-gateway`、`go-market-read-service`、`go-scan-worker` 是生产主路径组件，MySQL compose 默认启动；Python 保留 fallback，但 fallback 必须通过日志或 metrics 可观测
- 默认数据库为 `t_quant`
- 默认应用用户为 `tquant_app`
- 示例应用端口为 `18090`

Go 主路径健康检查：

```bash
docker compose -f docker-compose.mysql.yml exec go-bff-gateway wget -qO- http://127.0.0.1:8091/readyz
docker compose -f docker-compose.mysql.yml exec go-market-read-service wget -qO- http://127.0.0.1:8092/readyz
docker compose -f docker-compose.mysql.yml exec go-scan-worker wget -qO- http://127.0.0.1:8093/readyz
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
docker compose --profile analytics -f docker-compose.mysql.yml exec analytics-worker python -c "import duckdb, pyarrow; from app.core.database import ping_database; ping_database(); print('analytics-ready')"
```

行情读缓存指标：

```bash
docker compose -f docker-compose.mysql.yml exec go-market-read-service wget -qO- http://127.0.0.1:8092/metrics
```

重点观察 `tquant_market_read_redis_hits_total`、`tquant_market_read_cache_miss_total`、`tquant_market_read_mysql_fallbacks_total`。

停止：

```bash
docker compose -f docker-compose.mysql.yml down
```

如需连同数据卷一起清理：

```bash
docker compose -f docker-compose.mysql.yml down -v
```

### 7.3 容器环境变量

建议先复制：

```bash
cp .env.docker.example .env
```

关键项：

- `APP_PORT`
- `APP_WORKERS`
  Web/API Gunicorn worker 数。生产如 `APP_WORKERS>1`，`GLOBAL_RATE_LIMIT_BACKEND` 必须为 `redis` 或网关限流；否则应用启动即失败。
- `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED`
  Web 容器默认 `false`，避免 Gunicorn worker 内重复跑扫描、研究和调度循环。
- `RUNTIME_BACKGROUND_JOBS_ENABLED`
  仅用于专门调度容器；MySQL Compose 中 `runtime-worker` 通过独立进程消费任务，Web 不应打开该开关。
- `PAPER_AUTO_TRADING_ENABLED`
  默认 `false`，只允许明确授权的模拟盘自动交易进程开启。
- `TQUANT_RESEARCH_JOBS_ENABLED` / `TQUANT_ML_JOBS_ENABLED` / `TQUANT_FACTOR_JOBS_ENABLED` / `TQUANT_STRATEGY_EVOLUTION_ENABLED`
  研究、ML、因子、策略自进化循环默认关闭；需要研究任务时只在 `runtime-worker`、`backtest-worker` 或专用调度容器开启，不在 Web 容器开启。
- `WEB_TQUANT_ANALYTICS_ENABLED`
  Web `/readyz` 的 Analytics 依赖检查开关，默认 `false`，避免未安装 `duckdb`/`pyarrow` 的 Web 镜像因为分析依赖缺失而降级。
- `ANALYTICS_WORKER_TQUANT_ANALYTICS_ENABLED`
  `analytics-worker` 的 Analytics 依赖检查开关，默认 `true`；该镜像通过 `INSTALL_ANALYTICS=1` 安装 `duckdb`/`pyarrow`，启动时 fail-fast。该 worker 默认按需启动，部署时只有 `DEPLOY_WITH_ANALYTICS_WORKER=1` 或 quick deploy `--with-analytics-worker` 才纳入健康检查。
- `RUNTIME_WORKER_EMBED_SCHEDULER`
  默认 `false`。仅用于小内存机器灰度验证，让 `runtime-worker` 同时启动 scheduler background jobs。开启后仍使用 leader lock，并继续记录 `runtime-scheduler` heartbeat。不要在未观察一个完整交易日前停止独立 `runtime-scheduler`。
- `RUNTIME_SCHEDULER_LEADER_LOCK_TTL_SECONDS`
  scheduler heartbeat 循环间隔下限，默认 `60` 秒；用于监控灰度期间的 scheduler 存活证据。
- `TQUANT_DUCKDB_THREADS`
  DuckDB 查询线程数，容器默认 `2`。
- `SCHEMA_COMPAT_REPAIR_ENABLED`
  默认 `false`。生产环境以 Alembic 迁移为准；只有自托管旧库应急修复时才临时设为 `true`。
- `SCHEMA_COMPAT_VERIFY_ON_STARTUP`
  默认 `false`。如需要启动期只读漂移检查才临时设为 `true`，避免常规启动扫描全表结构。
- `GLOBAL_RATE_LIMIT_BACKEND`
  MySQL/Gunicorn 生产部署不得使用 `memory`。`docker-compose.mysql.yml` 默认使用 `redis`；如改回 `memory`，应用会拒绝启动。
- `AUTH_COOKIE_SECURE`
  生产必须为 `true`。
- `AUTH_ALLOW_INSECURE_HTTP_COOKIE`
  生产必须为 `false`。公网或域名部署不得用不安全 Cookie 例外。
- `TQUANT_SETTINGS_ENCRYPTION_KEY`
  必填，长度不少于 64 字符，且必须与 `AUTH_SECRET_KEY` 不同。用于加密系统配置中的 `llm_api_key`、`database_url` 等敏感字段。
- `DECISION_CONTEXT_ENABLED` / `MARKET_GATE_PRODUCTION_ENABLED` / `HARD_RISK_FILTER_PRODUCTION_ENABLED`
  Batch A 决策上下文、市场总闸和避坑过滤器开关，默认 `true`。回滚时先关闭 `DECISION_CONTEXT_ENABLED`；关闭后 priority board 回到既有生产评分路径，市场总闸不再乘权，paper order 不再消费 Batch A hard-risk snapshot 阻断。
- `DATA_QUALITY_SLA_ENABLED`
  数据质量 SLA 开关，默认 `true`。SLA 失败必须进入 `blocked_by_data` 或显式 `unavailable`，不得静默通过。
- `DATA_REPAIR_AUTO_ENABLED`
  数据修复自动执行开关，默认且建议永久保持 `false`。线上修复默认只 dry-run；删除必须由管理员显式提交 apply，并要求 DB 备份和行级 JSON 备份已生成。
- `TRACK_RECORD_ENABLED`
  真实战绩账本开关，默认 `true`。关闭后停止生产信号落账与 realized/outcome 刷新，既有 priority board 和回测报告基础口径不变。
- `DRIFT_ALERT_ENABLED`
  漂移告警开关，默认 `false`。关闭时 `strategy_drift_refresh` 仍写入 advisory 证据，但不会推送飞书/Agent 通知；只有线上阈值稳定后才放开。
- `TQUANT_INTERNAL_SERVICE_TOKEN`
  配置 `TQUANT_*_SERVICE_URL` 微服务地址时必填。BFF 到远端服务请求必须携带该 token，远端服务会拒绝缺失或不匹配的内部请求。
- `RUNTIME_WORKER_POLL_INTERVAL_SECONDS`
  Runtime Worker 拉取数据库任务队列的间隔，默认 `5` 秒。
- `CORS_ORIGINS`
  建议保持 JSON 数组字符串格式，例如 `["http://127.0.0.1:18080","http://127.0.0.1:18090"]`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

密钥轮换：

```bash
OLD_TQUANT_SETTINGS_ENCRYPTION_KEY="$OLD_KEY" \
NEW_TQUANT_SETTINGS_ENCRYPTION_KEY="$NEW_KEY" \
python scripts/reencrypt_settings.py
```

该脚本会在单个事务中把敏感配置从旧 settings 加密密钥重加密到新密钥；成功后再更新生产环境的 `TQUANT_SETTINGS_ENCRYPTION_KEY`。

### 7.4 发布建议

- 先执行 `./scripts/prod_preflight.sh`
- 需要极简部署时使用 SQLite Compose
- 需要更稳的长期运行时使用 MySQL Compose
- 云端建议再配合反向代理、TLS 和进程监控

## 8. 数据库备份与恢复

`scripts/deploy_cloud_server.sh` 默认会在云端发布后自动安装真实备份 cron，无需人工登录服务器操作。

```bash
AUTO_INSTALL_BACKUP_CRON=1 BACKUP_TIME=02:20 ./scripts/deploy_cloud_server.sh
```

如需临时关闭自动安装：

```bash
AUTO_INSTALL_BACKUP_CRON=0 ./scripts/deploy_cloud_server.sh
```

### 8.1 安装每日备份

```bash
BACKUP_TIME=02:20 ./scripts/install_backup_cron.sh
```

默认备份到 `./backups`，保留 14 天。SQLite 会生成 `t_quant-YYYYMMDD-HHMMSS.db.gz`，MySQL 会生成 `t_quant-YYYYMMDD-HHMMSS.sql.gz`。

### 8.2 手动备份

```bash
./scripts/backup_database.sh
```

### 8.3 SQLite 恢复

```bash
gunzip -c backups/t_quant-YYYYMMDD-HHMMSS.db.gz > backend/data/t_quant.db
docker compose -f docker-compose.sqlite.yml restart
```

### 8.4 MySQL 恢复

```bash
gunzip -c backups/t_quant-YYYYMMDD-HHMMSS.sql.gz | \
  docker compose -f docker-compose.mysql.yml exec -T mysql mysql -utquant_app -p t_quant
```

恢复前先停止应用容器或确认无人写入。

## 9. HTTPS 反向代理

`scripts/deploy_cloud_server.sh` 默认会自动安装 nginx、签发 Let's Encrypt 正式证书并配置 HTTPS 反向代理。

```bash
CLOUD_DOMAIN=<your-domain> \
CLOUD_CERT_EMAIL=<ops-email> \
AUTO_CONFIGURE_HTTPS=1 \
./scripts/deploy_cloud_server.sh
```

生产默认要求 HTTPS。`HTTPS_REQUIRED=1` 时，如果 DNS、80 端口或证书服务异常，部署会直接中断，避免用不安全 Cookie 运行生产环境：

```bash
HTTPS_REQUIRED=1 ./scripts/deploy_cloud_server.sh
```

如需临时关闭自动证书配置：

```bash
AUTO_CONFIGURE_HTTPS=0 ./scripts/deploy_cloud_server.sh
```

服务器上可用脚本安装 nginx + certbot：

```bash
sudo DOMAIN=<your-domain> APP_PORT=18090 EMAIL=<ops-email> ./scripts/install_https_nginx.sh
```

脚本会读取 `deploy/nginx/weisilianghua.conf.template`，配置：

- HTTP 自动跳转 HTTPS
- `client_max_body_size 1m`
- 反向代理到 `127.0.0.1:18090`
- SSE/WebSocket 所需 Upgrade 头

## 9.1 Git 首次提交自动化

部署脚本默认执行 `scripts/ensure_initial_git_commit.sh`。如果本地还没有 Git 仓库或没有任何 commit，脚本会自动初始化仓库并创建首次提交；已有 commit 时自动跳过。

```bash
AUTO_INITIAL_GIT_COMMIT=1 ./scripts/deploy_cloud_server.sh
```

可覆盖提交信息和 Git 身份：

```bash
INITIAL_COMMIT_MESSAGE='Initial production baseline' \
GIT_USER_NAME='TQuant Automation' \
GIT_USER_EMAIL='automation@local' \
./scripts/deploy_cloud_server.sh
```

如需临时关闭：

```bash
AUTO_INITIAL_GIT_COMMIT=0 ./scripts/deploy_cloud_server.sh
```

## 10. 性能问题排查

1. 先检查健康状态：

```bash
curl -i http://127.0.0.1:18090/readyz
```

2. 查看慢请求日志。后端会记录超过 3 秒的 `slow_http_request`。
   MySQL compose 默认启用慢查询日志，可用下面命令确认：

```bash
docker compose -f docker-compose.mysql.yml exec mysql \
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW VARIABLES WHERE Variable_name IN ('slow_query_log','long_query_time','innodb_buffer_pool_size');"
```

   `MYSQL_INNODB_BUFFER_POOL_SIZE` 可按服务器内存设置，生产建议从 512M 起，根据机器内存和 MySQL 负载调到约 40%-60%。
3. 检查低吸物化状态：

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/low_buy_materialization_health.py
```

4. 如果前端报 502，优先看容器日志和 `/readyz`：

```bash
docker compose -f docker-compose.mysql.yml logs --tail=200 app
docker compose -f docker-compose.mysql.yml logs --tail=200 runtime-worker
docker compose -f docker-compose.mysql.yml logs --tail=200 backtest-worker
docker compose --profile analytics -f docker-compose.mysql.yml logs --tail=200 analytics-worker
```

5. Analytics 报告任务验证：

```bash
docker compose -f docker-compose.mysql.yml exec app python - <<'PY'
from app.core.database import SessionLocal
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
with SessionLocal() as db:
    task = RuntimeTaskQueue(db).enqueue(RuntimeTaskCreate(task_type="strategy_24m_duckdb_report", payload={"manifest": "latest"}, max_attempts=1))
    print(task.id, task.status)
PY
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
docker compose --profile analytics -f docker-compose.mysql.yml logs -f analytics-worker
```

任务成功后线上产物应包含 `backend/data/analytics/reports/strategy_24m_duckdb_report.md` 和 `backend/data/analytics/reports/strategy_24m_duckdb_report.json`；仓库跟踪的 Markdown 摘要仍由 `backend/scripts/run_duckdb_strategy_report.py` 写到 `docs/reports/strategy_24m_duckdb_report.md`。如果日线数据或验证输入缺失，任务会失败并在 `runtime_task_events` 中记录阻断原因。

6. 数据质量 SLA 与 OHLC 修复验证：

```bash
docker compose -f docker-compose.mysql.yml exec app python - <<'PY'
from app.core.database import SessionLocal
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
with SessionLocal() as db:
    queue = RuntimeTaskQueue(db)
    task = queue.enqueue(RuntimeTaskCreate(task_type="data_quality_sla_refresh", payload={"scope": "production_universe"}, max_attempts=1))
    dry = queue.enqueue(RuntimeTaskCreate(task_type="data_repair_run", payload={"dataset_key": "daily_bars", "dry_run": True}, max_attempts=1))
    print(task.id, task.task_type, task.status)
    print(dry.id, dry.task_type, dry.status)
PY
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
docker compose --profile analytics -f docker-compose.mysql.yml logs -f analytics-worker
curl -sS -H "Authorization: Bearer <TOKEN>" https://<domain>/api/data-quality/sla
```

`data_quality_sla_refresh` 必须写入 `data_quality_snapshots`，`/api/data-quality/sla` 必须可读。`data_repair_run` 默认 dry-run，不修改数据；apply 只允许管理员显式触发。若出现 `daily_bars_invalid_ohlc`，先执行 dry-run 核对待修复行数，再确认备份目录中已有 DB 备份和行级 JSON 备份，最后低峰执行 apply。`data_repair_audits.fabricated` 必须恒为 `false`。

7. Batch A 决策上下文任务验证：

```bash
docker compose -f docker-compose.mysql.yml exec app python - <<'PY'
from app.core.database import SessionLocal
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
with SessionLocal() as db:
    queue = RuntimeTaskQueue(db)
    for task_type in ("market_state_gate_refresh", "hard_risk_context_refresh"):
        task = queue.enqueue(RuntimeTaskCreate(task_type=task_type, payload={}, max_attempts=1))
        print(task.id, task.task_type, task.status)
PY
docker compose -f docker-compose.mysql.yml logs -f runtime-worker
```

`market_state_gate_refresh` 的缺数据结果应为 `reduce` + degraded 证据，不得清空生产榜；`hard_risk_context_refresh` 属 Batch A 同步快照链路提示任务，不应在 Web 容器新增后台循环。更多操作见 `docs/high-roi-platform-expansion-runbook-2026-05-30.md`。

8. 真实战绩漂移验证：

```bash
docker compose -f docker-compose.mysql.yml exec app python - <<'PY'
from app.core.database import SessionLocal
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue
with SessionLocal() as db:
    queue = RuntimeTaskQueue(db)
    capture = queue.enqueue(RuntimeTaskCreate(task_type="signal_ledger_capture", payload={"limit": 30}, max_attempts=1))
    realized = queue.enqueue(RuntimeTaskCreate(task_type="realized_outcome_refresh", payload={"horizons": [1, 3, 5, 10]}, max_attempts=1))
    drift = queue.enqueue(RuntimeTaskCreate(task_type="strategy_drift_refresh", payload={"window_days": 60, "min_sample": 20}, max_attempts=1))
    print(capture.id, capture.task_type, capture.status)
    print(realized.id, realized.task_type, realized.status)
    print(drift.id, drift.task_type, drift.status)
PY
docker compose -f docker-compose.mysql.yml logs -f runtime-worker
docker compose --profile analytics -f docker-compose.mysql.yml logs -f analytics-worker
curl -sS -H "Authorization: Bearer <TOKEN>" https://<domain>/api/track-record/drift
```

`signal_ledger_capture` 只落 `buy_now`/`soft_buy_now` 的生产信号，`realized_outcome_refresh` 缺未来行情时必须保持 `unsettled`，`strategy_drift_refresh` 只写 advisory 证据，不自动修改 `strategy_policy.py`。24M 报告应包含“真实战绩 vs 回测”段；若还没有 `strategy_drift_snapshots`，报告必须显示 `no_data`，不得造分。

## 10.1 LONGTEXT 迁移排查

- 先在 staging 执行并计时：`time docker compose -f docker-compose.mysql.yml run --rm migration`，记录开始/结束时间、表行数、MySQL 版本。
- 只在低峰期执行生产迁移；迁移期间暂停写入型后台任务和研究类 worker。
- 回滚预案：迁移前完成 `./scripts/backup_database.sh` 或 MySQL dump；失败时停止 `app`、`runtime-worker`、`backtest-worker`、`analytics-worker`，恢复备份后再启动旧镜像。
- 截断排查：迁移后抽样检查大字段长度，例如 `SELECT id, CHAR_LENGTH(payload_json) FROM runtime_tasks ORDER BY id DESC LIMIT 20;`；如果发现截断，立即回滚并保留失败 SQL、行 id、字段长度证据。

## 11. 磁盘空间清理

云端清理预览：

```bash
./scripts/cloud_server_cleanup.sh
```

确认执行：

```bash
APPLY=1 KEEP_BACKUPS=1 ./scripts/cloud_server_cleanup.sh
```

本地可清理：

- `frontend/dist`
- `.runtime/ui-smoke`
- 过期 `backups/t_quant-*.gz`
- 旧回测报告导出文件

不要删除：

- `backend/data/runtime.env`
- 当前数据库文件或 Docker volume
- 当前云端运行目录

## 12. 长期方向边界

本轮只保留两个长期演进方向：

- 自动止损实盘化：先在模拟盘记录触发原因、建议动作和误触发情况，连续验证 6 个月；完成动态止损回测和合规评估后，再评估实盘接口。
- OpenTelemetry 链路：第一阶段只做 Go BFF 接收/生成并传播 `traceparent`，Python 记录并回传同一个 trace header；暂不强制引入 Jaeger/Tempo 存储，避免 trace 存储成本提前进入生产。
