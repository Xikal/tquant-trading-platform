# TQuant Phase 4 / Phase 5 落地说明

本文档覆盖当前已去除“实盘接入”后的架构演进和量化能力升级范围。

## 已落地能力

- Nginx 网关限流模板：`deploy/nginx/tquant-rate-limit.conf.template`
- 生产 Nginx server 模板已按接口类型接入 `limit_req` / `limit_conn`
- Prometheus scrape 配置：`deploy/prometheus/prometheus.yml`
- Prometheus 告警规则：`deploy/prometheus/tquant-alerts.yml`
- Grafana dashboard 初始模板：`deploy/prometheus/grafana-dashboard.json`
- Agent 结果质量评分接口：`POST /api/agent/quality/score`
- 行情数据源健康检查：`GET /api/market/data-sources/health`
- 量化参数版本接口：`GET /api/quant/parameters/current`
- DB-backed Runtime Worker 任务接口：`/api/runtime-tasks`
- Runtime Worker 启动入口：`python -m app.workers.runtime_worker`
- ML 信号样本与研究型推理接口：`/api/ml/signals`
- 回测 vs 模拟盘偏差对比接口：`POST /api/paper/backtest-comparison`

## Nginx 限流部署

1. 将 `deploy/nginx/tquant-rate-limit.conf.template` 渲染后放入 Nginx `http {}` 块。
2. 将 `deploy/nginx/weisilianghua.conf.template` 渲染为站点配置。
3. 执行 `nginx -t`。
4. 执行 `systemctl reload nginx`。

推荐限流责任边界：

- Nginx：全局 IP 级限流、连接数限制、高风险接口限流。
- 应用层：登录、Agent 工具、模拟交易等业务级兜底保护。
- Agent 工具层：provider/tool 级调用频率限制和权限控制。

## Prometheus / Grafana

`/metrics` 当前受 admin token 保护。Prometheus 使用：

```yaml
bearer_token_file: /etc/prometheus/secrets/tquant_admin_token
```

监控容器默认只绑定宿主机本地回环地址，避免无鉴权的 Prometheus 直接暴露公网：

```bash
PROMETHEUS_BIND_ADDR=127.0.0.1
GRAFANA_BIND_ADDR=127.0.0.1
```

如需外部访问 Grafana，应优先通过 Nginx HTTPS、登录鉴权和安全组放行实现；不要直接公网暴露 Prometheus。

Grafana 建议面板：

- API p95 延迟：`tquant_http_p95_ms`
- 慢请求数量：`tquant_http_slow_requests`
- Runtime Worker 队列：`tquant_runtime_tasks_queued`
- Runtime Worker 失败：`tquant_runtime_tasks_failed`
- Agent 工具成功/失败：`tquant_agent_tool_success_total` / `tquant_agent_tool_failure_total`
- Agent 质量拦截：`tquant_agent_quality_blocked_total`

## Worker

第一阶段使用数据库任务队列，避免云服务器必须额外部署 Redis。

启动命令：

```bash
cd /path/to/backend
python -m app.workers.runtime_worker
```

可提交的基础任务：

- `noop`
- `agent_daily_report_push`

后续如果任务量上升，再将 `RuntimeTaskQueue` 适配到 Celery/RQ，不改变 API。

## 量化参数版本

当前默认版本由 `QUANT_PARAMETER_DEFAULT_VERSION` 控制，默认 `quant-params-v1`。

使用原则：

- 回测、模拟盘、Agent 分析应记录参数版本。
- 参数变更新增版本，不覆盖历史版本。
- ML 输出默认 `research_only=true`，不能直接进入生产交易建议。
- XGBoost 是可选重型研究依赖，只在需要时安装 `backend/requirements-ml-extra.txt`；默认生产依赖使用轻量模型链路。

## 不包含内容

- 不实现真实券商实盘交易。
- 不默认启用 ML 生产策略。
- 不绕过后端风控。
