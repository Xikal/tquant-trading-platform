# TQuant 后端 Go/Rust 重构运行手册

日期：2026-05-22

## 当前边界

本轮 Go/Rust 重构落地受控生产增强路径，不改变 Python 策略写入真源：

- Python FastAPI 仍是唯一生产写入源。
- 低吸策略、全策略优先榜、模拟盘自动交易、回测策略语义不迁移。
- Go BFF、Go 行情读服务、Go 扫描 Worker 可按 profile 与服务 URL 受控启用；未启用或异常时保留 Python 回退。
- Rust `tquant_rs` 可通过 `RUST_FINANCE_MATH_ENABLED=true` 受控启用；导入失败或计算异常时保留 Python 回退。
- 生产 compose 的 `app` 服务默认开启 `RUNTIME_BACKGROUND_JOBS_ENABLED=true`，由主应用进程在 leader lock 下执行小时全市场快照、午盘复盘和收盘复盘；`qa_smoke.sh` / `prod_preflight.sh` 仍显式关闭背景任务，避免重复调度。

## Python 生产配置

MySQL 连接池通过环境变量控制：

```bash
DB_POOL_SIZE=12
DB_MAX_OVERFLOW=24
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

BFF 聚合缓存通过环境变量控制：

```bash
BFF_WORKSPACE_CACHE_ENABLED=true
BFF_MONITOR_CACHE_TTL_SECONDS=5
BFF_PAPER_CACHE_TTL_SECONDS=3
BFF_STRATEGY_CACHE_TTL_SECONDS=30
BFF_SETTINGS_CACHE_TTL_SECONDS=30
```

启用微服务远端适配器前必须配置内部服务令牌：

```bash
TQUANT_INTERNAL_SERVICE_TOKEN=<strong-random-token>
```

Python 行情批量读取可接入 Go market-read 本地快照读服务。启用时配置：

```bash
TQUANT_MARKET_READ_SERVICE_URL=http://go-market-read-service:8092
```

未配置、Go 服务不可用或返回结构不兼容时，Python 会回退现有 Provider Router / Quote Router 路径。

## 受控 Go BFF Gateway

启动：

```bash
docker compose -f docker-compose.mysql.yml --profile go-bff up -d go-bff-gateway
```

默认只代理 `/api/bff/v1/workspace/*` 和 `/bff/v1/workspace/*` 到 Python BFF。
同时代理 `/api/bff/v1/manifest` 和 `/bff/v1/manifest`，用于前端或运维侧校验 BFF 契约版本。

Go BFF 会透传：

- `Authorization`
- `X-Admin-Token`
- `X-Request-ID`

同时会向 Python BFF 添加：

- `X-TQuant-Bff-Hop: 1`
- `X-Internal-Service-Token`，仅当已配置 `TQUANT_INTERNAL_SERVICE_TOKEN`

生产接流前必须满足：

- `/healthz`、`/readyz` 正常。
- `/metrics` 输出 `tquant_bff_gateway_up 1`。
- Python BFF 仍可直接访问，Go BFF 失败时能回退。
- Nginx 只对内转发 Go BFF，不公网暴露未保护端口。

## 受控 Go Market Read Service

启动：

```bash
docker compose -f docker-compose.mysql.yml --profile go-market up -d go-market-read-service
```

当前提供健康检查、metrics，以及三类 Redis 本地行情快照读接口：

- `/api/market-read/v1/quote-batch`：批量报价。
- `/api/market-read/v1/sector-relative-strength`：按调用方传入的板块股票列表计算板块内相对强度。
- `/api/market-read/v1/intraday-key-levels`：基于本地报价快照计算开盘价、昨收、整数关口、买点区等关键位。

这些接口优先读取 Python 已写入 Redis 的本地行情缓存键 `tquant:market:quote:{symbol}`，批量报价使用 Redis `MGET`。Redis 未命中时，可只读 MySQL `daily_bar_snapshots + instruments` 最新日线快照作为 `stale` 兜底。该服务不访问外部行情源，不写 MySQL/Redis。
业务读接口受 `X-Internal-Service-Token` 保护；`/healthz`、`/readyz`、`/metrics` 不要求该 header，便于容器健康检查。

调用示例：

```bash
curl -H "X-Internal-Service-Token: $TQUANT_INTERNAL_SERVICE_TOKEN" \
  "http://go-market-read-service:8092/api/market-read/v1/quote-batch?symbols=000001,600000"
```

板块相对强度示例：

```bash
curl -H "X-Internal-Service-Token: $TQUANT_INTERNAL_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sector":"银行","symbols":["000001","600000"],"limit":10}' \
  "http://go-market-read-service:8092/api/market-read/v1/sector-relative-strength"
```

分时关键位示例：

```bash
curl -H "X-Internal-Service-Token: $TQUANT_INTERNAL_SERVICE_TOKEN" \
  "http://go-market-read-service:8092/api/market-read/v1/intraday-key-levels?symbol=000001&entry_zone_low=10.10&entry_zone_high=10.30"
```

响应状态：

- `fresh`：请求标的均命中缓存且缓存新鲜。
- `partial`：部分标的未命中或解析失败。
- `unavailable`：全部标的未命中或 Redis 不可用。

生产接流验收要求：

- 与 Python Provider Router 输出契约做 contract parity。
- `python3 scripts/verify_go_rust_performance_acceptance.py` 通过。
- 云端压测与降级验收通过后再扩大流量。

## 受控 Go Scan Worker

启动：

```bash
docker compose -f docker-compose.mysql.yml --profile go-scan up -d go-scan-worker
```

当前仅支持影子状态查询，`production_write_enabled=false` 固定关闭。
影子状态接口受 `X-Internal-Service-Token` 保护；健康检查不要求该 header。

如需仅做占位式影子触发，可调用：

```bash
curl -H "X-Internal-Service-Token: $TQUANT_INTERNAL_SERVICE_TOKEN" \
  "http://go-scan-worker:8093/api/scan-worker/v1/shadow/run?strategy=default&limit=72"
```

生产接流前必须补齐：

- 影子扫描结果与 Python 扫描结果逐日 diff。
- 不写生产快照。
- 连续 20 个交易日差异在阈值内后再评估是否灰度。

## 受控 Rust 金融数学扩展

受控启用：

```bash
RUST_FINANCE_MATH_ENABLED=true
```

当前 Python 可选包装函数：

- `rust_max_drawdown`
- `rust_rolling_mean`
- `rust_atr_wilder`

启用前必须安装并验证 Python 扩展：

```bash
cd rust/tquant-rs
cargo test
maturin develop
```

启用后仍需确认 Python fallback：

- 扩展导入失败不影响服务启动。
- 计算结果与 Python 实现误差在测试阈值内。
- 云端部署镜像包含 Rust wheel，而不是运行时编译。

## 验证命令

```bash
scripts/verify_backend_refactor_foundation.sh
python3 scripts/verify_go_rust_performance_acceptance.py
```

脚本行为：

- 始终执行 Python 编译和关键 pytest。
- Docker 不存在时跳过 Compose 配置校验。
- Go 不存在时跳过 Go 单测。
- Cargo 不存在时跳过 Rust 单测。
- Go market-read benchmark 受固定预算约束。
- Rust release 基准需同时满足 Python 对比速度比 `>= 5x`、误差与回退要求。

## 回滚方式

- 不启用任何 `go-*` profile，即完全回到 Python 单体路径。
- 保持 `RUST_FINANCE_MATH_ENABLED=false`，禁用 Rust 扩展。
- 清空微服务 URL 环境变量，Python BFF 不会走远端适配器。
