# TQuant 上线前审查报告采纳评估与执行文档（2026-05-26）

## 1. 评估范围

来源报告：

- `/Users/j/Library/Application Support/com.tencent.mac.marvis/MarvisData/User/oAN1i2YHHnA2ZrJVlZh_IyuJ8AiA/workspace/conv_19e62bc4b81_993dfd5c6fbe/output/TQuant_上线前审查报告_2026-05-26.md`

评估仓库：

- `/Users/j/Documents/gupiao`

本次评估方式：

- 通读报告全文，提取 P1/P2/P3、已修复项、强化方向、上线建议。
- 对照当前仓库抽查 Go scan-worker、Go BFF、Rust PyO3、CI、前端路由、复盘链路、限速配置、日期字段等关键代码。
- 按当前产品约束重新校准：复盘必须作为“实时监控”的主展示入口；Go/Rust 应按生产主路径治理，不使用长期 shadow/optional 作为终态表述。

## 2. 总体采纳结论

报告的总体判断“无 P0、有条件灰度上线”可以采纳，但报告中的部分表述需要修正后再进入执行计划。

采纳分类：

- 直接采纳：Go scan-worker 状态语义修正、Rust 性能基准量化、路由模式文档化与测试、Go BFF 覆盖面扩展、BFF cache 指标、agent benchmark 样本扩充。
- 调整后采纳：Rust wheel/默认启用建议、复盘前端入口建议、小时快照末段 slot 建议、trade_date 迁移建议。
- 已部分完成，仅保留验收：RL 可选依赖注释、Rust wheel 构建 smoke、Go/Python 内部 token、实时监控复盘展示、全市场复盘服务。
- 暂不按原文采纳：把复盘主入口放到模拟盘、在生产路径要求下把 Rust 默认改回关闭、未验证就把 15:00 slot 直接改成 14:57。

上线口径：

- 可以继续按灰度上线推进。
- 正式灰度前必须补齐两个“容易误导验收/运维”的点：Go scan-worker 策略引擎来源说明、Rust 性能目标与可复现 benchmark 证据。
- 复盘相关文档、报告、页面都必须统一为“全市场复盘在实时监控主展示；模拟盘只保留历史入口或跳转入口”。

## 3. P1 项采纳决策

### P1-01 Go scan-worker 状态语义误导

结论：直接采纳，作为正式灰度前必做项。

当前核验：

- `go-services/scan-worker/cmd/scan-worker/main.go` 的 `/status` 返回 `production_scan_enabled=true`、`production_write_enabled=true`、`production_readiness=mainline_ready`。
- `runHandler` 实际调用 Python `/api/internal/scan-worker/v1/run`。
- `backend/app/api/routes/internal_scan_worker.py` 的 `ranking_consistency.status` 已写明 `python_reference_order`。

为什么采纳：

- 当前 Go scan-worker 已经是生产入口编排层，但策略计算仍由 Python reference 执行。
- “mainline_ready + production_write_enabled=true”容易让运维误判为 Go 已独立执行策略公式和写入。

执行要求：

- health/status 增加或改名字段：
  - `strategy_engine=python_reference`
  - `scan_worker_role=go_orchestrated_reference`
  - `production_readiness=python_reference_orchestrator`
- `production_write_enabled` 只表达“本次链路允许写入”，不要表达“Go 独立写入能力”。
- runbook 增加故障判断：Go 不可用时 Python fallback；Python reference 不可用时 Go scan-worker 不应声称扫描可独立完成。

验收：

- Go 单元测试覆盖 Python reference 502 时返回 `production_write_enabled=false`。
- status/readyz 测试断言 `strategy_engine` 字段存在。
- 运维文档中必须出现 “Python reference strategy engine” 或等价中文说明。

### P1-02 Rust benchmark 缺少数值性能目标

结论：直接采纳性能目标，但调整“不装 wheel 就默认关闭 Rust”的建议。

当前核验：

- `rust/tquant-rs/src/lib.rs` 已实现 `max_drawdown`、`rolling_mean`、`atr_wilder`、`rsi_wilder`、`vwap`、`rank_ic`。
- `.github/workflows/ci.yml` 已有 `cargo test`、`maturin build`、wheel install、import smoke。
- `scripts/verify_go_rust_performance_acceptance.py` 已有 Python/Rust timeit 对比和 `RUST_BENCHMARK_MIN_SPEEDUP=5.0`。
- 仍缺少标准化 Rust bench 文件、CI artifact 和 Makefile 本地入口。

为什么采纳：

- 生产主路径不能只用“已接入”作为性能验收，必须有可复跑的阈值。
- Rust fallback 必须可观测，否则运行时退回 Python 后性能风险不明显。

执行要求：

- 新增 `rust/tquant-rs/benches/finance.rs`，优先用 `criterion` 覆盖 ATR、RSI、VWAP、rolling、max drawdown、RankIC。
- CI 增加 bench 输出保存；即使不把 benchmark 作为每次 PR 的硬门禁，也要保留 nightly/manual workflow 或 artifact。
- Makefile 增加 `rust-bench` 和 `go-rust-acceptance` 入口。
- `rust_math.py` 的 hit/fallback/error metrics 要进入 Prometheus 或日志。

调整项：

- 不采纳“wheel 未预装就把 `rust_finance_math_enabled` 默认改为 False”作为生产默认。
- 正确做法是：生产镜像必须预装 wheel；启动/健康检查发现 wheel 不可导入时 fail-fast 或进入明确 degraded 状态；Python fallback 保留但必须计数告警。

验收：

- Rust wheel import smoke 继续保留。
- benchmark 至少给出 Python/Rust speedup、输入规模、运行机器或 CI 环境。
- 已迁移指标路径能观察到 Rust hit > 0，fallback/error 可查。

### P1-03 React Router 与 TradingWorkspace 壳层仍耦合

结论：调整后采纳。

当前核验：

- `frontend/src/app/router/webRouteDefinitions.tsx` 已有 `MonitorRoute`、`EmotionRoute`、`PaperRoute` 等 lazy route。
- 但 `frontend/src/app/router/MonitorRoute.tsx`、`PaperRoute.tsx` 仍返回 `WorkspaceRoute page="..."`。
- `frontend/src/app/router/WorkspaceRoute.tsx` 通过 `setPage(page)` 后渲染 `TradingWorkspace`。

为什么采纳：

- 当前已经不是旧的纯 pushState，但也不是完全组件级路由。
- 报告中“React Router 真实路由已实现”的表述应改为“URL-to-page-state 同步已实现，高频入口保留工作台壳层”。

执行要求：

- 文档修正路由现状，不夸大为完全组件级拆分。
- 前端路由测试补充 cold navigate 后 `workspaceStore.page` 一致性断言。
- 开发环境增加 page 不一致 warning。
- 后续再逐页把高频页面从 `TradingWorkspace` 壳层剥离，优先级：MonitorPage、MarketEmotionPage、PaperTradingPage、StrategyPage。

验收：

- `/monitor`、`/emotion`、`/paper`、`/strategy` 冷启动页面状态正确。
- `/backtest` 仍可达，不被重定向覆盖。
- 路由错误边界和 Suspense 的限制在文档中说明清楚。

## 4. P2 项采纳决策

### P2-01 stable_baselines3 可选依赖说明

结论：已部分完成，保留验收。

当前核验：

- `backend/requirements-rl-extra.txt` 已明确写明这是 optional RL research dependencies。
- `backend/requirements.txt` 也说明 RL shadow research dependencies 不在默认生产依赖中。

后续动作：

- 不删除 `stable-baselines3`，因为它仍属于独立研究环境可选依赖。
- 在生产运行手册中补一句：默认生产镜像不得安装 `backend/requirements-rl-extra.txt`。

验收：

- Docker 默认构建不安装 PyTorch/stable-baselines3。
- RL import site 保留 try/except guard。

### P2-03 Go BFF 聚合覆盖面不足

结论：采纳，作为 Go 生产主路径扩展。

当前核验：

- `go-services/bff-gateway/cmd/bff-gateway/workspace_aggregate.go` 仅对 `monitor`、`paper` 做并发聚合。
- `strategy`、`settings`、`factor` 在 manifest 中出现，但 `aggregateWorkspace()` default 会触发 proxy fallback。

执行要求：

- 为 strategy workspace 增加并发聚合：策略摘要、回测列表、模型/因子健康、关键配置。
- 为 settings workspace 增加只读聚合：配置摘要、运行时状态、数据源健康、权限边界。
- 为 factor workspace 增加聚合：因子健康、实验状态、激活状态。
- metrics 增加 workspace 维度的 aggregate/proxy/fallback 比例。

验收：

- 生产启用 Go BFF 后，高频 workspace 默认优先命中 Go aggregate。
- partial response 不白屏，partial_errors 可观测。

### P2-04 global_rate_limit_backend 默认 memory

结论：采纳文档和 QA 强化，不要求改开发默认值。

当前核验：

- `backend/app/core/security_config.py` 已对生产 memory backend 和多 worker memory backend fail-fast。
- `backend/app/core/config.py` 默认仍为 `memory`，适合本地单进程开发。

执行要求：

- `.env.docker.example`、运行手册明确生产必须配置 `GLOBAL_RATE_LIMIT_BACKEND=redis` 或网关限流。
- QA smoke 在 Redis 或 mock Redis 场景验证限速行为。

验收：

- production/profile 下 memory backend 启动失败。
- Redis 限速 smoke 通过。

### P2-05 非 DailyBarSnapshot 表 trade_date 仍为 String(16)

结论：采纳，但必须单独设计迁移，不能仓促改字段。

当前核验：

- `backend/app/models/market_entities.py`、`backend/app/models/backtest_entities.py`、`backend/app/models/low_buy_entities.py` 等仍有多处 `trade_date` / `latest_trade_date` 为 `String(16)`。

执行要求：

- 先列出受影响表、索引、唯一约束、历史数据格式。
- 已新增审计入口：`python scripts/audit_trade_date_fields.py`，输出仍为 `String` 的日期字段、索引和唯一约束范围。
- 新增 Alembic 迁移时必须兼容 SQLite/MySQL。
- 对低吸、回测、策略结果口径做回归测试。

验收：

- 日期比较、按日查询、分区规划可用。
- 老字符串输入仍可兼容。
- 回测与低吸候选结果不因迁移改变排序口径。

## 5. P3 项采纳决策

### P3-02 Go BFF cache metrics 不完整

结论：采纳。

当前核验：

- `/metrics` 只有 `tquant_bff_gateway_cache_hits_total`，没有 cache size、ttl、hit rate。

执行要求：

- 增加 `tquant_bff_gateway_cache_items`、`tquant_bff_gateway_cache_ttl_seconds`。
- 增加请求总数或 cache lookup 总数，计算 hit rate。

验收：

- Grafana/Prometheus 能看到缓存命中率和缓存规模。

### P3-03 agent_benchmark 样本量不足

结论：采纳，但只作为研究质量提醒，不作为上线阻塞。

当前核验：

- `research/reports/agent_benchmark.json` 中 `sample_count=2`，`win_rate=0.0`，`ic=-1.0`。

执行要求：

- 样本数至少 30 后再把胜率、IC、IR 用作策略有效性判断。
- 当前 benchmark 只能作为流水线可运行证据，不能作为策略结论。

### P3-04 MarketEmotionPage 单文件维护成本

结论：采纳为后续重构。

当前核验：

- `frontend/src/features/market-emotion/MarketEmotionPage.tsx` 当前规模不大，但继续加情绪时序、龙头强度、data_quality 后应拆分。

执行要求：

- 后续拆成 `EmotionGauge`、`LeaderStrengthPanel`、`SectorStrengthPanel`、`DataQualityBadge` 等子组件。

### P3-05 hourly snapshot 最后一个 slot 从 15:00 调整为 14:57/14:55

结论：暂不直接采纳，先评估后调整。

当前核验：

- `backend/app/services/market/hourly_snapshot.py` 当前 slot 为 9:30、10:30、11:30、13:00、14:00、15:00。

为什么不直接改：

- 15:00 表达正式收盘后全市场快照，适合收盘复盘。
- 14:55/14:57 更适合作为尾盘预警，不等价于收盘复盘基准。

建议：

- 保留 15:00 收盘快照。
- 如需尾盘信号，新增 `late_session` slot（14:55 或 14:57），不要替换 15:00。

验收：

- 午盘、尾盘、收盘三个概念在 UI 和调度中区分清楚。

## 6. 报告中“已修复项”的使用方式

报告列出的 24 个已修复项可以作为上线回归清单，但不能全部原样写入发布说明。

可直接保留为已修复证据：

- DailyBarSnapshot 精度和 FlexibleDate 迁移。
- CSP data URI 清理。
- ML approve operator 从 JWT 获取。
- N+1 关键路径 selectinload。
- 多 worker memory 限速 fail-fast。
- 设置加密密钥与 AUTH_SECRET_KEY 解耦。
- Go BFF monitor/paper 并发聚合。
- Rust 6 个函数和 wheel smoke。
- 内部 token 生产校验。

需要修正文案后再引用：

- “午盘/收盘复盘”：必须写成“全市场午盘/收盘复盘，主入口在实时监控”，不要写成模拟盘复盘主入口。
- “React Router 真实路由”：应写成“URL 路由和页面状态同步已完成，高频页面仍逐步拆组件级路由”。
- “Go scan-worker 生产路径”：应写成“Go 生产入口编排 Python reference 策略引擎，具备 fallback 和观测；Go 独立策略内核仍是后续方向”。
- “Rust 默认启用”：应同时写明 wheel 预装、fallback metrics、启动/健康检查要求。

## 7. 强化方向采纳排序

优先级 1：实时监控首屏增强

- 增加盘中强弱折线或迷你趋势图，复用 hourly snapshot history。
- 连续两个 slot 下降时在实时监控顶部给风险提示。
- 保持复盘主入口在实时监控，不转移到模拟盘。

优先级 2：Rust 热路径覆盖

- 回测批量 ATR/RSI、因子 RankIC、风险归因 max drawdown 优先走 Rust wrapper。
- 对 fallback 做 metrics 和日志。

优先级 3：Go BFF 扩展

- 从 monitor/paper 扩到 strategy/settings/factor。
- 指标维度从总量扩到 workspace/source 维度。

优先级 4：因子实验室闭环

- 因子激活必须经过 production gate、回测验证、健康监控。
- 策略工作台展示当前生效因子权重，但不能绕过风险约束。

优先级 5：未来架构方向

- Level2 数据、OpenTelemetry、MySQL 分区、自动止损可以进入路线图，不作为当前上线阻塞。

## 8. 灰度前执行清单

必须完成：

1. 修正 Go scan-worker status/health 字段语义，并补 Go 测试。
2. 补 Rust benchmark 标准入口和可复跑性能结果。
3. 修正文档中复盘口径：全市场复盘、实时监控主入口。
4. 修正文档中路由口径：URL-to-page-state 同步，不夸大为完全组件级路由。
5. 生产运行手册明确 Redis 限速、内部 token、Rust wheel、Go fallback 指标。

建议同步完成：

1. BFF cache metrics 增加 cache size/ttl/hit rate。
2. `agent_benchmark` 标注样本不足，不用于策略收益结论。

灰度观察指标：

- `tquant_bff_gateway_aggregate_hits_total`
- `tquant_bff_gateway_proxy_fallbacks_total`
- `tquant_bff_gateway_partial_source_failures_total`
- `tquant_bff_gateway_cache_hits_total`
- scan-worker runs/failures/fallbacks/writes
- Rust hits/fallbacks/errors
- 复盘生成成功率、最后生成时间、空状态数量

## 9. 不按原文采纳的点

1. 不把复盘主入口放到模拟盘。
   - 原因：产品要求已明确，复盘是全市场复盘，应在实时监控主展示。
   - 模拟盘只保留历史入口、跳转入口或辅助引用。

2. 不因 wheel 风险把 Rust 生产默认改回关闭。
   - 原因：当前目标是 Rust 进入生产计算主路径。
   - 正确治理方式是镜像预装 wheel、启动/健康检查、metrics 告警和 Python fallback。

3. 不直接把 15:00 快照替换为 14:57。
   - 原因：15:00 代表收盘快照，14:55/14:57 是尾盘预警。
   - 可以新增 late-session slot，而不是替换收盘口径。

4. 不把 Go scan-worker 描述成已独立实现完整策略内核。
   - 原因：当前 Go 入口是生产编排层，策略公式仍由 Python reference 执行。
   - 后续如要独立 Go/Rust 策略内核，必须做连续交易日 parity 验证。

5. 不把 `agent_benchmark sample_count=2` 作为策略有效性证据。
   - 原因：样本量过小，只能证明流程可跑，不能证明收益或 IC 稳定。

## 10. 建议验证命令

前端：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run lint
npm test -- --run
npm run build
npm run smoke:responsive
```

后端：

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend pytest backend/tests
```

Go：

```bash
cd /Users/j/Documents/gupiao/go-services/bff-gateway && go test ./...
cd /Users/j/Documents/gupiao/go-services/market-read-service && go test ./...
cd /Users/j/Documents/gupiao/go-services/scan-worker && go test ./...
```

Rust：

```bash
cd /Users/j/Documents/gupiao/rust/tquant-rs
cargo test
cargo bench --features extension-module --bench finance
```

Go/Rust 接受度脚本：

```bash
cd /Users/j/Documents/gupiao
python scripts/verify_go_rust_performance_acceptance.py
```

云端灰度 smoke：

```bash
curl -fsS http://43.143.243.97:18090/api/health
curl -fsS http://43.143.243.97:18090/api/bff/v1/manifest
curl -fsS http://43.143.243.97:18090/api/market/review-summary
```

## 11. 最终建议

可以采用报告的主体判断和多数工程建议，但应把报告转化为“灰度前必做 + 下一迭代债务 + 长期方向”的三层执行计划。

正式发布说明中建议使用以下口径：

- 平台当前无 P0 阻塞，具备有条件灰度上线基础。
- 全市场午盘/收盘复盘已进入实时监控页主展示，模拟盘只作为辅助入口。
- Go 已进入生产读聚合和扫描编排主路径，但 scan-worker 策略公式来源需明确标注为 Python reference。
- Rust 已进入生产计算路径，必须用 wheel 预装、benchmark、metrics、fallback 共同验收。
- 前端路由仍有结构性债务，但不阻塞当前灰度。
