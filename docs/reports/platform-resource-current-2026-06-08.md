# 平台资源巡检报告

- 生成时间：`2026-06-08T04:59:51.770131+00:00`
- 状态：`warning`
- 阻断项：无
- 警告项：swap_used_pct=65.27, mysql_slow_log_bytes=3328599654, docker_build_cache_bytes=7447473291, resource_config_missing=docker_daemon, resource_config_missing=journald_dropin, resource_config_missing=buildkit, resource_config_missing=mysql_slow_logrotate

## 核心指标

| 指标 | 当前值 |
| --- | ---: |
| 根分区使用率 | 57% |
| Swap 使用率 | 65.27% |
| Docker build cache | 6.936GB |
| Journal | 1.2G |
| MySQL slow log | 3.1G |
| binlog 保留秒数 | 259200 |
| binlog 单文件上限 | 268435456 bytes |
| binlog 数量 | 7 |
| binlog 总体积 | 4784169501 bytes |
| 部署归档数量 | 0 |
| 部署归档总体积 | 0 bytes |
| MySQL 备份数量 | 1 |
| MySQL 备份总体积 | 140674550 bytes |
| 最新 MySQL 备份 | /home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz |

## 资源配置状态

| 配置 | 状态 | 路径 |
| --- | --- | --- |
| `buildkit` | missing | `/etc/buildkit/buildkitd.toml` |
| `docker_daemon` | missing | `/etc/docker/daemon.json` |
| `journald` | present | `/etc/systemd/journald.conf` |
| `journald_dropin` | missing | `/etc/systemd/journald.conf.d/tquant-resource.conf` |
| `mysql_compose_resource_config` | present | `/home/ubuntu/gupiao-upload/docker-compose.mysql.yml` |
| `mysql_slow_logrotate` | missing | `/etc/logrotate.d/tquant-mysql-slow-log` |

## 结论

当前无 blocking 项，但存在 warning 项，需要进入资源治理队列。
