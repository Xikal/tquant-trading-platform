# 平台资源巡检报告

- 生成时间：`2026-06-08T05:05:37.479342+00:00`
- 状态：`warning`
- 阻断项：无
- 警告项：swap_used_pct=94.61

## 核心指标

| 指标 | 当前值 |
| --- | ---: |
| 根分区使用率 | 41% |
| Swap 使用率 | 94.61% |
| Docker build cache | 0B |
| Journal | 284.3M |
| MySQL slow log | 4.0K |
| binlog 保留秒数 | 259200 |
| binlog 单文件上限 | 268435456 bytes |
| binlog 数量 | 7 |
| binlog 总体积 | 4784661957 bytes |
| 部署归档数量 | 0 |
| 部署归档总体积 | 0 bytes |
| MySQL 备份数量 | 1 |
| MySQL 备份总体积 | 140674550 bytes |
| 最新 MySQL 备份 | /home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz |

## 资源配置状态

| 配置 | 状态 | 路径 |
| --- | --- | --- |
| `buildkit` | present | `/etc/buildkit/buildkitd.toml` |
| `docker_daemon` | present | `/etc/docker/daemon.json` |
| `journald` | present | `/etc/systemd/journald.conf` |
| `journald_dropin` | present | `/etc/systemd/journald.conf.d/tquant-resource.conf` |
| `mysql_compose_resource_config` | present | `/home/ubuntu/gupiao-upload/docker-compose.mysql.yml` |
| `mysql_slow_logrotate` | present | `/etc/logrotate.d/tquant-mysql-slow-log` |

## 结论

当前无 blocking 项，但存在 warning 项，需要进入资源治理队列。
