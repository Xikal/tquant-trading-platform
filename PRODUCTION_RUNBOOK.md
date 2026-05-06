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
mysql+pymysql://root:你的密码@127.0.0.1:3306/t_quant?charset=utf8mb4
```

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
  --url 'mysql+pymysql://root:你的密码@127.0.0.1:3306/t_quant?charset=utf8mb4'
```

### 迁移 SQLite 到 MySQL

```bash
cd backend
.venv/bin/python scripts/db_admin.py migrate \
  --target-url 'mysql+pymysql://root:你的密码@127.0.0.1:3306/t_quant?charset=utf8mb4' \
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
CLOUD_HOST=43.143.243.97 \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
./scripts/deploy_cloud_server.sh
```

默认行为：

- 本地执行后端编译、核心策略测试和前端构建。
- 打包当前项目，排除 `.runtime`、虚拟环境、`node_modules`、本地数据库运行配置等非发布内容。
- 上传到云服务器。
- 备份远端当前 `/home/ubuntu/gupiao-upload`。
- 使用 `docker-compose.mysql.yml` 重建 `app` 容器，不删除 MySQL volume。
- 自动验证 `/readyz`、默认低吸接口和前端首页。

常用参数：

```bash
CLOUD_PROJECT_DIR=/home/ubuntu/gupiao-upload
CLOUD_COMPOSE_FILE=docker-compose.mysql.yml
CLOUD_APP_PORT=18090
CLOUD_KEEP_BACKUPS=3
RUN_FULL_TESTS=1
```

如果没有 SSH key，也可以临时使用：

```bash
CLOUD_PASSWORD='服务器密码' ./scripts/deploy_cloud_server.sh
```

不要把密码写入脚本或提交到仓库。

### 7.0.1 云服务器清理

清理脚本默认只预览，不删除：

```bash
CLOUD_HOST=43.143.243.97 \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
./scripts/cloud_server_cleanup.sh
```

确认无误后执行实际清理：

```bash
CLOUD_HOST=43.143.243.97 \
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
- `app` 容器默认关闭运行时后台任务，只负责 Web/API 响应
- `runtime-worker` 容器单 worker 执行预热、低吸扫描、归档、通知扫描和模拟盘自动交易
- `backtest-worker` 容器独立消费回测任务
- 默认数据库为 `t_quant`
- 默认应用用户为 `tquant_app`
- 示例应用端口为 `18090`

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
- `CORS_ORIGINS`
  建议保持 JSON 数组字符串格式，例如 `["http://127.0.0.1:18080","http://127.0.0.1:18090"]`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

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
CLOUD_DOMAIN=weisilianghua.cloud \
CLOUD_CERT_EMAIL=admin@weisilianghua.cloud \
AUTO_CONFIGURE_HTTPS=1 \
./scripts/deploy_cloud_server.sh
```

默认 `HTTPS_REQUIRED=0`：如果 DNS、80 端口或证书服务临时异常，部署会继续并输出告警。若希望证书签发失败时直接中断部署：

```bash
HTTPS_REQUIRED=1 ./scripts/deploy_cloud_server.sh
```

如需临时关闭自动证书配置：

```bash
AUTO_CONFIGURE_HTTPS=0 ./scripts/deploy_cloud_server.sh
```

服务器上可用脚本安装 nginx + certbot：

```bash
sudo DOMAIN=weisilianghua.cloud APP_PORT=18090 EMAIL=你的邮箱 ./scripts/install_https_nginx.sh
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
```

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
