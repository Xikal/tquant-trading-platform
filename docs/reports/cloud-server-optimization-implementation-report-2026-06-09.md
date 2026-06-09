# 云服务器资源优化实施报告（2026-06-09）

> 本报告对应 `docs/reports/cloud-server-optimization-plan-2026-06-09.md` 与 `docs/reports/cloud-server-optimization-development-plan-2026-06-09.md`。
> 本轮只完成代码、脚本、compose、测试和 runbook 加固；未部署、未切流、未在线上清理。

## 硬边界执行情况

- 未修改旧前端 `frontend/`。
- 未修改 `strategy_policy.py`。
- 未改变 `production_score`、priority board、低吸生产排序和策略语义。
- 未触碰 MySQL 主写数据、Docker volume、线上任务数据或模拟盘数据。
- 未执行线上 deploy、cutover、cleanup、scheduler 停容器或 separated 栈停用。

## 已完成改动

### 1. 资源报告与受控清理

- `scripts/collect_platform_resource_report.py` 增加：
  - `vm.swappiness` 采集与告警。
  - `docker stats --no-stream` 常驻容器内存汇总。
  - separated 验证栈运行状态采集。
  - `tquant-app-mysql` Gunicorn worker 数解析。
- `scripts/install_platform_resource_limits.py` 增加 `deploy/sysctl/tquant-swappiness.conf` 安装规格，目标 `vm.swappiness=10`。
- `scripts/cloud_server_cleanup.sh` 仍 dry-run 默认，新增 `STOP_SEPARATED_STACK=1` 受控路径：
  - 先检查 nginx 仍代理 `proxy_pass http://127.0.0.1:18090`。
  - 满足后才允许 `docker-compose.separated.yml down`。
  - 继续禁止 `docker volume prune` 与 `image prune -a` 默认执行。

### 2. Compose 资源边界

- `docker-compose.mysql.yml` 与 `docker-compose.separated.yml` 增加统一日志上限：
  - `DOCKER_LOG_MAX_SIZE=50m`
  - `DOCKER_LOG_MAX_FILE=3`
- MySQL、app、runtime-worker、runtime-scheduler、backtest-worker、analytics-worker、Go 服务、migration、backup 等服务增加可配置 `mem_limit`、`memswap_limit`、`cpus`。
- `APP_WORKERS` 默认统一为 `1`；保留环境变量回升能力。
- `runtime-scheduler` DB pool 默认收敛到 `2/2`，降低单机连接预算。

### 3. analytics-worker 按需化

- `analytics-worker` 增加 `profiles: ["analytics"]`。
- `scripts/deploy_cloud_server.sh` 新增 `DEPLOY_WITH_ANALYTICS_WORKER=0` 默认：
  - 默认部署不 build/up/等待 analytics-worker。
  - 显式开启时使用 `--profile analytics` 启动，并执行 DuckDB/PyArrow/DB ping readyz。
  - prebuilt 镜像模式下，analytics 镜像只在显式开启时成为必需。
- `scripts/quick_cloud_deploy.sh` 新增 `--with-analytics-worker`，并同步默认跳过 analytics 验收。
- `scripts/build_prebuilt_images.sh` 默认只构建 web app 镜像；显式 `--with-analytics-worker` 才构建可选 analytics 镜像并输出 `DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF`。
- 默认验收输出 `analytics_worker:skipped_on_demand` 或 `analytics_worker_readyz:skipped_on_demand`，避免误判为缺失。

### 4. runtime-worker 内嵌 scheduler 灰度

- `backend/app/core/config.py` 新增：
  - `runtime_worker_embed_scheduler: bool = False`
  - `runtime_scheduler_leader_lock_ttl_seconds: int = 60`
- `backend/app/workers/runtime_worker.py` 在开关开启时启动现有 `start_runtime_background_jobs()`，退出时关闭。
- `backend/app/runtime/background_jobs.py`：
  - worker 嵌入模式可绕过普通 `runtime_background_jobs_enabled=false` 默认。
  - 继续复用文件 leader lock 防重复入队。
  - 增加 `runtime_scheduler_heartbeat` 循环，组件仍记录为 `runtime-scheduler`，worker id 为 `runtime-worker-embedded-scheduler`。
- `docker-compose.mysql.yml` 将灰度开关传入 runtime-worker；独立 `runtime-scheduler` 默认仍保留。

### 5. Runbook 更新

- `docs/operations/deployment-topology-runbook.md`：
  - 说明 analytics-worker 为按需 profile。
  - 增加 `DEPLOY_WITH_ANALYTICS_WORKER=1` 与 `--with-analytics-worker` 用法。
  - 增加 scheduler grey flag 操作与回滚边界。
- `docs/operations/worker-runbook.md`：
  - 增加 runtime-worker 内嵌 scheduler 灰度说明。
  - analytics 命令统一改为 `docker compose --profile analytics ...`。
- `PRODUCTION_RUNBOOK.md`：
  - 更新默认部署角色、analytics 按需语义、资源清理、separated 栈停用保护和灰度配置项。

## 验证结果

已通过：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_platform_resource_report.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_platform_optimization_readiness.py \
  backend/tests/test_cloud_performance_script.py \
  backend/tests/test_database_url_driver.py \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_ml_online_learning_schedule.py -q
```

结果：

```text
111 passed, 1 warning
```

最终门禁已通过：

```bash
MYSQL_PASSWORD=compose_check_app \
MYSQL_ROOT_PASSWORD=compose_check_root \
AUTH_SECRET_KEY=compose_check_auth_secret_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
TQUANT_SETTINGS_ENCRYPTION_KEY=compose_check_settings_secret_bbbbbbbbbbbbbbbbbbbbbbbbbbbb \
docker compose -f docker-compose.mysql.yml config >/tmp/tquant-compose-config.yml

git diff --check
git diff -- frontend strategy_policy.py | wc -l
git diff -- frontend-next | wc -l
```

结果：

```text
compose config ok
git diff --check ok
frontend + strategy_policy.py diff lines: 0
frontend-next diff lines: 0
```

## 线上执行建议

本轮没有执行线上动作。后续如用户单独授权，按下面顺序执行：

1. 只读基线：
   - `free -m`
   - `df -h /`
   - `sudo docker system df`
   - `sudo docker stats --no-stream`
   - `python3 scripts/collect_platform_resource_report.py --remote ...`
2. 安装资源配置：
   - `scripts/install_platform_resource_limits.py --dry-run`
   - 审核后再 `--apply`
3. 安全清理：
   - `scripts/cloud_server_cleanup.sh`
   - 审核 dry-run 输出后再 `APPLY=1`
4. separated 验证栈停用：
   - 仅在 nginx 仍指向 `18090` 时使用 `STOP_SEPARATED_STACK=1 APPLY=1`。
5. analytics-worker：
   - 正常部署保持默认不启动。
   - 需要 24M 报告或导出时使用 `DEPLOY_WITH_ANALYTICS_WORKER=1` 或 `--with-analytics-worker`。
6. scheduler 合并：
   - 先设置 `RUNTIME_WORKER_EMBED_SCHEDULER=true` 灰度。
   - 观察一个完整交易日。
   - 确认定时刷新、latest data watchdog、收盘发布和 priority materialization 正常后，再单独授权停止独立 scheduler。

## 剩余风险

- `runtime-worker` 内嵌 scheduler 是灰度能力，默认关闭；没有线上交易日观察前不应停止独立 `runtime-scheduler`。
- `analytics-worker` 默认不常驻后，低频分析任务必须显式拉起 profile，否则任务会排队等待。
- 本轮只验证了脚本和本地测试，没有执行线上资源前后对比，因此内存释放数字仍需在线上授权后重新测量确认。
