# 尾盘推荐榜与本地桌面壳线上部署验收报告

- 检查时间：2026-06-13 12:59:31 CST
- 服务器：ubuntu@43.143.243.97
- 默认入口：https://43.143.243.97
- 域名入口：https://weisilianghua.cloud
- 分支：codex/phase4-phase5-architecture
- 部署提交：
  - 8e5dfb1a fix: preserve frontend nginx config in deploy package
  - a130f9c4 fix: avoid empty data quality SLA deploy env
  - e8ef2f39 feat: add local desktop app shell
  - 068b143d feat: add late session recommendation board

## 结论

线上部署成功，IP 入口当前可用。`app`、`runtime-worker`、`runtime-scheduler`、Go 服务、`frontend-web`、MySQL、Redis 均为 healthy。尾盘推荐榜 API 路由、runtime task 注册、本机状态 API、前端页面入口已上线。

`weisilianghua.cloud` 在部署脚本的远端 SNI loopback 和 public domain 验证中通过，但从本机公网 curl 仍出现 `Recv failure: Connection reset by peer`，继续判定为本地到域名公网链路/TLS 入口问题，不影响 IP 入口可用性。

## 本轮执行动作

| 类型 | 命令/动作 | 结果 |
| --- | --- | --- |
| 本地门禁 | `backend/.venv/bin/python -m unittest discover -s backend/tests -p 'test_*.py'` | 435 passed |
| 前端构建 | `npm --prefix frontend-next run build` | passed |
| 部署 | `./scripts/one_click_cloud_deploy.sh --scope all --full --host 43.143.243.97 --key /Users/j/Downloads/gupiao.pem` | deploy-ok |
| 远端迁移 | Alembic migration container | exited 0 |
| HTTPS 配置刷新 | `--refresh-https-config` | nginx config test successful |

## 部署中发现并修复的问题

| 等级 | 问题 | 证据 | 修复 |
| --- | --- | --- | --- |
| P1 | `frontend-web` 启动失败，nginx 配置挂载源是目录而不是文件 | Docker 报错：`deploy/frontend/nginx.conf ... not a directory`；远端 `file deploy/frontend/nginx.conf` 显示 directory | 修复 `scripts/deploy_cloud_server.sh`：把 `deploy/frontend/nginx.conf` 加入部署包必检项、远端 release 必检项、前端容器启动前 mount 源校验；移除会误伤 `deploy/frontend` 的 tar exclude |
| P2 | 空 `DATA_QUALITY_SLA_ENABLED` 透传导致本地部署门禁 Pydantic bool 解析失败 | `data_quality_sla_enabled Input should be a valid boolean, input_value=''` | 修复 `scripts/quick_cloud_deploy.sh`：仅在非空时导出/传递该 env |

## 容器状态

| 容器 | 状态 | 备注 |
| --- | --- | --- |
| tquant-app-mysql | healthy | 18090 |
| tquant-runtime-worker-mysql | healthy | runtime task worker |
| tquant-runtime-scheduler-mysql | healthy | standalone scheduler |
| tquant-go-bff-gateway | healthy | Go BFF |
| tquant-go-market-read-service | healthy | Go 行情读服务 |
| tquant-go-scan-worker | healthy | Go scan worker |
| tquant-frontend-web | healthy | 18080，nginx 静态前端 |
| tquant-mysql | healthy | MySQL 8.4 |
| tquant-redis | healthy | Redis 7 |
| tquant-analytics-worker-mysql | exited | on-demand，部署脚本跳过 |

## 资源状态

| 项 | 当前值 | 判断 |
| --- | --- | --- |
| load average | 1.39 / 1.04 / 0.86 | 正常 |
| 内存 | 3.6Gi total, 2.5Gi used, 1.2Gi available | 可用但余量有限 |
| Swap | 1.9Gi total, 623Mi used | 有使用，需持续观察 |
| 根盘 | 59G total, 43G used, 15G available, 75% | P2 风险 |
| inode | 15% used | 正常 |
| Docker images | 18.18GB, 14.77GB reclaimable | P2 优化项 |
| Docker build cache | 12.78GB, 5.60GB reclaimable | P2 优化项 |

## HTTP/API 验证

| URL | 状态 | 耗时 | 结论 |
| --- | --- | --- | --- |
| `https://43.143.243.97/readyz` | 200 | - | readyz ok |
| `https://43.143.243.97/` | 200 | - | 新前端入口 ok |
| `https://43.143.243.97/next/monitor` | 200 | 0.085s | 页面入口 ok |
| `https://43.143.243.97/next/monitor/market` | 200 | 0.093s | 页面入口 ok |
| `https://43.143.243.97/next/local-status` | 200 | 0.129s | 本机状态页入口 ok |
| `https://43.143.243.97/next/settings` | 200 | 0.083s | 页面入口 ok |
| `https://43.143.243.97/api/local/status` | 200 | - | 本机状态 API ok |
| `https://43.143.243.97/api/screeners/low-buy/late-session-board?limit=12&refresh=cache` | 401 | - | 未登录被保护，符合认证预期 |
| `https://43.143.243.97/api/monitor/snapshot` | 401 | 0.091s | 未登录被保护 |
| `https://43.143.243.97/api/settings` | 401 | 0.096s | 未登录被保护 |
| `https://43.143.243.97/api/readyz` | 404 | 0.115s | 项目实际 readyz 在根路径 `/readyz` |
| `https://43.143.243.97/api/monitor` | 404 | 0.091s | 当前无该裸 endpoint |
| `https://weisilianghua.cloud/readyz` | 000 / TLS reset | - | 本机公网域名链路仍异常 |
| `https://weisilianghua.cloud/next/monitor` | 000 / TLS reset | - | 本机公网域名链路仍异常 |

## 功能验收

| 功能 | 验证方式 | 结果 |
| --- | --- | --- |
| 尾盘推荐榜 schema/API | 容器内 import `LateSessionBoardResponse`；路由存在 | 通过 |
| 尾盘 runtime task | 容器内检查 `late_session_recommendation_refresh in RUNTIME_TASK_TYPES` | 通过 |
| 本地桌面状态 API | `GET /api/local/status` | 200 |
| 新前端页面 | `/next/monitor`、`/next/local-status`、`/next/settings` | 200 |
| 低吸最新数据闭环 | 部署脚本 latest-data closure | ok，expected/published trade date 均为 2026-06-12 |

## 数据状态

低吸最新数据闭环：

- expected_trade_date：2026-06-12
- published_trade_date：2026-06-12
- daily_bar_count：5211
- required_strategies：`first_board`、`late_session_strong_support`、`volume_shrink`
- missing_strategies：空

策略摘要：

| 策略 | latest_trade_date | pool_size | matched_count |
| --- | --- | ---: | ---: |
| first_board | 2026-06-12 | 480 | 40 |
| late_session_strong_support | 2026-06-12 | 16 | 0 |
| volume_shrink | 2026-06-12 | 480 | 9 |

## 风险分级

| 等级 | 问题 | 影响 | 建议 |
| --- | --- | --- | --- |
| P1 | `weisilianghua.cloud` 本机公网访问仍 TLS reset | 用户通过域名访问可能失败；IP 入口可用 | 继续按域名链路方案处理：换域名/接 CDN/WAF/调整入口；用多网络来源复测 |
| P2 | 根盘 75%，Docker build cache 12.78GB | 后续全量构建、部署包上传和镜像构建可能变慢或触发磁盘风险 | 在低峰期授权执行安全清理，优先清理 build cache 和旧 deploy backup，不清 MySQL volume |
| P2 | Swap 623MiB 使用 | 高峰期仍可能出现资源争抢 | 继续推进“云端 Web-only + 本地重任务/非核心任务关闭”方案，或升级规格 |
| P3 | `/api/readyz`、`/api/monitor`、`/api/priority-board` 等裸路径为 404 | 文档/探针如果写错路径会误报 | 运维探针统一使用 `/readyz`、实际认证 API 路径和前端 BFF 路径 |

## 本轮未执行的动作

- 未修改 `backend/app/services/low_buy/strategy_policy.py`
- 未改变 `production_score`
- 未改变 priority board 默认排序和字段语义
- 未自动下单
- 未清理 Docker build cache、旧镜像、旧备份、MySQL binlog 或日志
- 未改 `.env` 业务配置
- 未手动改数据库数据

## 后续清单

1. P1：处理 `weisilianghua.cloud` 公网 TLS reset。建议先用不同网络来源验证，再决定接 CDN/WAF 或更换域名。
2. P2：在低峰期执行授权清理：Docker build cache、无用 upload package、旧 deploy backup；保留 MySQL volume 和备份。
3. P2：做一次 30-60 分钟稳定性观察：`docker stats`、`readyz`、`/next/monitor`、核心 API p95。
4. P2：继续推进资源方案：非核心 worker on-demand、本地承接重任务、云端保留 Web/API/Redis 缓存。
5. P3：更新外部监控探针路径，避免使用不存在的 `/api/readyz`。
