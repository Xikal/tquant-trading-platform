# TQuant Agent OS 验收清单

日期：2026-05-04

本文只记录 Agent OS 测试、CI 与验收口径。业务能力是否可用于生产交易，仍以人工联调、数据源配置和策略验收为准。

## 已完成

- pytest 兼容入口已补齐：根目录 `pytest.ini` 将 `backend` 加入 `pythonpath`，并稳定发现 `backend/tests/test_*.py`，现有 unittest 用例可由 pytest 收集运行。
- CI 已设置 Agent OS scoped coverage 门禁：仅统计 `app.agent_providers`、`app.agent_tools`、Agent API routes/auth/helpers、Agent report/research/daily workflow 等 Agent OS 范围，门槛为 `>=70%`。
- CI 日志已明确 coverage 不是全项目覆盖率，避免把 Agent OS scoped coverage 误读为 whole-project coverage。
- Agent OS 工具注册验收覆盖 21 个工具存在性，包括新增 backtest、策略对比、模拟盘下单、市场情绪、板块热力、持仓 T 信号和 5 个 research context 工具。
- Provider status 验收覆盖默认配置下的工具可见性：read 工具可用，write/notify 工具在未开启配置时列入 disabled。
- 审计验收覆盖结构化脱敏日志、agent 维度汇总、成功/失败计数和 tool_top 聚合。
- 每日报告手动触发验收覆盖 `GET /api/agent/reports/daily`；可通过 monkeypatch 验证不会依赖真实外部服务。
- 每日报告推送入口已有 admin-only 路由测试覆盖；未授权时返回服务未配置/未授权类错误，授权后可触发 stub workflow。
- Research context 路由验收覆盖市场状态、板块主线、策略交叉验证、风控检查和综合分析。
- Research 离线脚本烟测覆盖 parquet 摘要函数和 `tquant_to_qlib.py --help`，验证不连接数据库时也可加载帮助信息。

## 骨架完成

- Hermes 编排配置已落在 `docs/hermes_orchestration.yaml`，定义 daily research workflow、角色、工具和输出章节；仍需要外部 Hermes 实例实际接入。
- Agent role prompts 已落在 `docs/agent-role-prompts.md`，可作为 Hermes prompt 模板；仍需要真实编排端按模板调用。
- Agent Skills 已落在 `skills/tquant-*` 目录，属于可加载文本规范；仍需要在目标 Agent 运行环境中安装/引用。
- qlib/offline research 目录已落地 `research/`，包含数据同步、因子摘要、策略验证和 benchmark 脚本；当前验收只覆盖脚本不崩，不代表 qlib 全链路已完成。
- OpenBB、Prometheus、JWT 标准化等 Phase 3 能力不属于本轮测试实现范围；如已有骨架，需要单独联调验收。
- 四项真实验收入口已落在 `scripts/agent_os_acceptance.py`：
  - Hermes：配置 `HERMES_API_URL` 后，对全策略榜前 10 只标的调用外部 workflow。
  - 飞书：配置 `NOTIFICATION_FEISHU_WEBHOOK_URL` 后，使用项目日报服务真实推送并写通知账本。
  - qlib：从本地 `low_buy_result_snapshots` + `daily_bar_snapshots` 导出策略样本，生成 IC/IR/Sharpe/MaxDD 报告。
  - OpenBB：真实探测 Yahoo/FRED 免费源，并验证失败时只返回 degraded，不阻断 A 股核心链路。

## 未配置时行为

- `agent_provider=none` 时，provider status 仍可返回本地可用状态，read 工具可通过 TQuant Safe API 本地执行。
- Hermes/custom HTTP provider 缺少 URL/API key 时，应返回 `PROVIDER_NOT_CONFIGURED`，不应尝试外部调用。
- `agent_enable_write_tools=false` 时，`recommend_orders`、`create_paper_order` 等 write 工具默认拒绝。
- `agent_enable_notify_tools=false` 时，`send_signal_notification`、`scan_priority_board_notifications` 等 notify 工具默认拒绝。
- 未配置 admin token 时，admin-only 入口按当前项目约定返回不可用/拒绝状态，不暴露敏感操作。
- 未配置飞书 webhook/secret 时，只能完成本地报告生成或 stub 测试，不应假定消息已送达。
- 未提供 research 数据库 URL 时，离线导出脚本只能查看帮助或被导入，不能产出真实 qlib/parquet 数据。

## 人工配置项

- 配置 `AGENT_API_TOKEN` 或 `AGENT_TOKENS`，并按 `read`、`write_paper`、`notify` 等 scope 分配最小权限。
- 配置 `ADMIN_API_TOKEN` 后再验证 `/api/agent/provider/invoke`、`/api/agent/audit`、`/api/agent/audit/summary` 和日报推送入口。
- 配置 `HERMES_API_URL`、`HERMES_API_KEY` 与外部 Hermes workflow，确认 `docs/hermes_orchestration.yaml` 中的工具路径和鉴权头一致。
- 如需通知，配置飞书 webhook/secret，并人工验证日报推送与信号去重账本。
- 如需离线研究，配置 research Python 环境、数据库只读连接、pyarrow/qlib/lightgbm 等依赖，并确认输出目录不提交大型产物。
- 如需部署，配置 CI/CD secrets，包括云服务器、SSH、域名、证书邮箱和备份时间。

## 未完成项

- 未验证真实 Hermes 编排对 10 只标的生成完整报告；当前只覆盖 TQuant 端 API 与配置骨架。
- 未验证真实飞书日报推送送达；当前测试使用 stub/monkeypatch。
- 未运行 qlib 完整回测、IC/IR/Sharpe/MaxDD 报告产出；当前只做 research 脚本烟测。
- 未把 coverage 门禁扩展为全项目覆盖率；当前明确只对 Agent OS scoped coverage 负责。

## 真实验收命令

默认执行四项，缺配置会输出 `not_configured`：

```bash
PYTHONPATH=/Users/j/Documents/gupiao/backend \
  backend/.venv/bin/python scripts/agent_os_acceptance.py \
  --lookback-days 504 \
  --output research/reports/agent_os_acceptance.json
```

只验收 qlib 实盘样本报告：

```bash
PYTHONPATH=/Users/j/Documents/gupiao/backend \
  backend/.venv/bin/python scripts/agent_os_acceptance.py \
  --skip-hermes --skip-feishu --skip-openbb \
  --lookback-days 504
```

输出文件：

- `research/reports/agent_os_acceptance.json`
- `research/reports/datasets/agent_strategy_samples.csv`
- `research/reports/agent_strategy_validation.json`
- `research/reports/agent_benchmark.json`
