# MySQL 与平台资源上限运维手册

状态：生产运维手册，默认只读/演练；执行 `--apply` 需要单独运维窗口
范围：MySQL binlog、slow log、Docker 日志、journald、BuildKit cache
边界：不删除 MySQL `.ibd`、不直接删除 binlog、不中断业务切流、不清 Docker volumes

## 目标

1. MySQL binlog 固化 3 天保留：`binlog_expire_logs_seconds=259200`。
2. MySQL slow log 单文件受控：`size 256M`、`rotate 14`、`compress`、`copytruncate`。
3. Docker json log 上限：`max-size=50m`、`max-file=3`。
4. systemd journal 上限：`SystemMaxUse=300M`、`MaxRetentionSec=7day`。
5. BuildKit cache 目标：`maxUsedSpace=2GB`。

## 执行前检查

```bash
cd /home/ubuntu/gupiao-upload
df -h /
free -h
sudo docker system df
sudo journalctl --disk-usage
sudo du -sh /var/lib/docker/volumes/tquant-mysql_mysql_data/_data
sudo du -sh /var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log || true
```

生成只读资源报告：

```bash
python3 scripts/collect_platform_resource_report.py \
  --json-output docs/reports/platform-resource-baseline-$(date +%F).json \
  --markdown-output docs/reports/platform-resource-baseline-$(date +%F).md
```

## 执行 slow log 备份

先备份当前 slow log，不直接删除：

```bash
TS=$(date +%Y%m%d%H%M%S)
sudo mkdir -p /home/ubuntu/mysql-backups/slow-log
sudo cp -a /var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log \
  /home/ubuntu/mysql-backups/slow-log/mysql-slow-${TS}.log
sudo gzip /home/ubuntu/mysql-backups/slow-log/mysql-slow-${TS}.log
```

确认备份存在：

```bash
ls -lh /home/ubuntu/mysql-backups/slow-log/mysql-slow-${TS}.log.gz
```

全库备份文件需要做只读可读性校验。该校验只读取 `.sql.gz`，验证 gzip 完整性、sha256 和 SQL dump 特征，不恢复、不写库、不删除文件：

```bash
python3 scripts/verify_mysql_backup_artifact.py \
  --json-output docs/reports/platform-mysql-backup-verification-$(date +%F).json \
  --markdown-output docs/reports/platform-mysql-backup-verification-$(date +%F).md \
  --fail-on-blocking
```

远程只读校验示例：

```bash
python3 scripts/verify_mysql_backup_artifact.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /path/to/key.pem \
  --json-output docs/reports/platform-mysql-backup-verification-$(date +%F).json \
  --markdown-output docs/reports/platform-mysql-backup-verification-$(date +%F).md \
  --fail-on-blocking
```

## 安装资源上限配置

先 dry-run：

```bash
cd /home/ubuntu/gupiao-upload
python3 scripts/install_platform_resource_limits.py
```

确认输出项后执行：

```bash
sudo python3 scripts/install_platform_resource_limits.py --apply --restart-hints
```

脚本会把旧配置备份到 `/etc/tquant-resource-backups/<timestamp>/`，再写入宿主机资源配置。MySQL 的 `binlog_expire_logs_seconds` 与 `max_binlog_size` 已内联在 `docker-compose.mysql.yml` 的 MySQL `command` 中，通过 `MYSQL_BINLOG_EXPIRE_LOGS_SECONDS=259200`、`MYSQL_MAX_BINLOG_SIZE=256M` 生效；不要再依赖宿主机 `/etc/mysql/conf.d`，该路径不会自动进入 MySQL 容器。

| 配置 | 目标路径 |
| --- | --- |
| Docker daemon log opts | `/etc/docker/daemon.json` |
| journald drop-in | `/etc/systemd/journald.conf.d/tquant-resource.conf` |
| BuildKit GC | `/etc/buildkit/buildkitd.toml` |
| MySQL binlog/max_binlog 配置 | `docker-compose.mysql.yml` 的 MySQL `command` |
| MySQL slow logrotate | `/etc/logrotate.d/tquant-mysql-slow-log` |

## 重启与验证

在低峰窗口执行：

```bash
sudo systemctl restart docker
sudo systemctl restart systemd-journald
sudo systemctl restart buildkit || true
sudo docker compose -f docker-compose.mysql.yml up -d mysql
sudo docker compose -f docker-compose.mysql.yml up -d app runtime-scheduler runtime-worker backtest-worker analytics-worker
```

验证：

```bash
curl -f http://127.0.0.1:18090/readyz
sudo docker compose -f docker-compose.mysql.yml exec -T mysql \
  mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" \
  -e "SELECT @@binlog_expire_logs_seconds; SHOW VARIABLES LIKE 'max_binlog_size'; SHOW VARIABLES LIKE 'slow_query_log';"
sudo logrotate -d /etc/logrotate.d/tquant-mysql-slow-log
python3 scripts/collect_platform_resource_report.py \
  --json-output docs/reports/platform-resource-after-limits-$(date +%F).json \
  --markdown-output docs/reports/platform-resource-after-limits-$(date +%F).md
```

## Analytics Manifest 导出与复验

该流程用于补齐 Parquet/DuckDB 分析层 manifest。它不清理 MySQL 源表，不替换 MySQL 事实源，也不改变生产策略排序。

### 1. 只读复验当前 manifest

```bash
cd /home/ubuntu/gupiao-upload
python3 scripts/verify_analytics_manifests.py \
  --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics \
  --json-output docs/reports/platform-analytics-manifests-$(date +%F).json \
  --markdown-output docs/reports/platform-analytics-manifests-$(date +%F).md
```

若报告仍有 `manifest_missing`、`artifact_file_missing`、`artifact_hash_mismatch` 或其他 blocking，不能进入 MySQL 热库保留窗口。

### 2. 生成导出计划

```bash
python3 scripts/plan_analytics_manifest_exports.py \
  --manifest-report docs/reports/platform-analytics-manifests-$(date +%F).json \
  --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics \
  --end-date $(date +%F) \
  --json-output docs/reports/platform-analytics-export-plan-$(date +%F).json \
  --markdown-output docs/reports/platform-analytics-export-plan-$(date +%F).md
```

该脚本只把缺失或损坏 manifest 转为低优先级 analytics worker 任务计划；不入队、不执行导出、不连接数据库。

### 3. 生成提交预览

```bash
python3 scripts/submit_analytics_manifest_exports.py \
  --export-plan docs/reports/platform-analytics-export-plan-$(date +%F).json \
  --json-output docs/reports/platform-analytics-export-submission-dry-run-$(date +%F).json \
  --markdown-output docs/reports/platform-analytics-export-submission-dry-run-$(date +%F).md
```

确认 `selected tasks`、`task_type`、`priority`、`idempotency_key` 均符合预期。dry-run 报告里的 `submitted tasks` 必须为 0。

### 4. 显式入队

仅在低峰/运维窗口执行。该命令只写 `runtime_tasks` 队列；不会同步执行 exporter，也不会清 MySQL 源表。

```bash
python3 scripts/submit_analytics_manifest_exports.py \
  --export-plan docs/reports/platform-analytics-export-plan-$(date +%F).json \
  --apply \
  --confirm-apply submit-analytics-manifest-exports \
  --json-output docs/reports/platform-analytics-export-submission-apply-$(date +%F).json \
  --markdown-output docs/reports/platform-analytics-export-submission-apply-$(date +%F).md
```

若只想提交单个数据集，使用：

```bash
python3 scripts/submit_analytics_manifest_exports.py \
  --export-plan docs/reports/platform-analytics-export-plan-$(date +%F).json \
  --datasets strategy_tracking_snapshots \
  --apply \
  --confirm-apply submit-analytics-manifest-exports
```

### 5. 观察 worker 与队列

```bash
curl -fsS http://127.0.0.1:18090/api/runtime-tasks/summary \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | python3 -m json.tool
curl -fsS http://127.0.0.1:18090/api/runtime-tasks/workers \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | python3 -m json.tool
curl -fsS "http://127.0.0.1:18090/api/runtime-tasks?status=queued&limit=50" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | python3 -m json.tool
curl -fsS "http://127.0.0.1:18090/api/runtime-tasks/failures?limit=20" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | python3 -m json.tool
```

如需取消尚未完成的导出任务，使用任务详情里的 `id`：

```bash
curl -fsS -X POST http://127.0.0.1:18090/api/runtime-tasks/<task_id>/cancel \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"cancel analytics manifest export during maintenance window"}'
```

### 6. 导出后复验

任务完成后必须再次执行 manifest 复验：

```bash
python3 scripts/verify_analytics_manifests.py \
  --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics \
  --json-output docs/reports/platform-analytics-manifests-after-export-$(date +%F).json \
  --markdown-output docs/reports/platform-analytics-manifests-after-export-$(date +%F).md \
  --fail-on-blocking
```

只有复验无 blocking，才允许进入热库保留窗口 dry-run。即使复验通过，也不能自动清理 MySQL 源表；清理必须另行获得用户/运维授权，并先确认备份、恢复路径和 candidate SQL。

## 回滚

找到最近备份：

```bash
sudo ls -dt /etc/tquant-resource-backups/* | head -1
```

按需恢复：

```bash
BACKUP_DIR=$(sudo ls -dt /etc/tquant-resource-backups/* | head -1)
sudo cp -a "$BACKUP_DIR/etc/docker/daemon.json" /etc/docker/daemon.json 2>/dev/null || true
sudo cp -a "$BACKUP_DIR/etc/systemd/journald.conf.d/tquant-resource.conf" /etc/systemd/journald.conf.d/tquant-resource.conf 2>/dev/null || true
sudo cp -a "$BACKUP_DIR/etc/buildkit/buildkitd.toml" /etc/buildkit/buildkitd.toml 2>/dev/null || true
sudo cp -a "$BACKUP_DIR/etc/logrotate.d/tquant-mysql-slow-log" /etc/logrotate.d/tquant-mysql-slow-log 2>/dev/null || true
```

如需回滚 MySQL binlog/max_binlog 参数，恢复上一版 `docker-compose.mysql.yml` 或环境变量后执行 `sudo docker compose -f docker-compose.mysql.yml up -d mysql`，再复验 `@@binlog_expire_logs_seconds` 和 `@@max_binlog_size`。其他重启同“重启与验证”步骤。

## 禁止项

```bash
# 禁止
rm -f /var/lib/docker/volumes/tquant-mysql_mysql_data/_data/*.ibd
rm -f /var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-bin.*
docker volume prune
docker image prune -a
```

binlog 清理只能使用 MySQL 语义命令，并且必须先备份和确认复制/恢复要求：

```sql
PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY;
```
