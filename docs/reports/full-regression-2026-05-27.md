# Full Regression QA Report 2026-05-27

## 结论

本次全量回归、发布预检、云端健康与在线性能验证均通过。新增统一回归入口后，后续版本可以持续运行同一套检查，覆盖后端、前端、移动端响应式、API、策略/风控/模拟盘/回测、Go/Rust、部署健康与可观测性。

## 回归入口

- `python scripts/full_regression_runner.py --profile core`
- `python scripts/full_regression_runner.py --profile full`
- `python scripts/full_regression_runner.py --profile release`
- `python scripts/full_regression_runner.py --profile release --only cloud_verify --cloud-verify`
- `make full-regression`
- `make full-regression-release`
- `make full-regression-cloud`

## 本次执行结果

- `python scripts/full_regression_runner.py --profile full --fail-fast`
  - 结果：13 passed / 0 failed / 0 skipped
  - 耗时：110217 ms
  - 运行明细：临时报告已汇总到本文，`.runtime/full-regression/` 仅作为本地运行缓存，不作为持久审计文件保留。
  - 覆盖维度：backend、backend_api、strategy_logic、risk、paper、backtest、ml、security、persistence、frontend、ui、mobile、usability、performance、bundle、go、bff、market_data、cache、concurrency、scan_worker、rust、finance_math、parity、production_path、deployment-adjacent API smoke。

- `python scripts/full_regression_runner.py --profile release --only prod_preflight --fail-fast`
  - 结果：1 passed / 0 failed / 0 skipped
  - 耗时：27078 ms
  - 运行明细：临时报告已汇总到本文，`.runtime/full-regression/` 仅作为本地运行缓存，不作为持久审计文件保留。
  - 覆盖：native release build/sync、前端生产构建、后端 compile、QA smoke、单端口前后端服务、`/readyz`、settings 持久化读取。

- `python scripts/full_regression_runner.py --profile release --only cloud_verify --cloud-verify --fail-fast`
  - 结果：1 passed / 0 failed / 0 skipped
  - 耗时：25498 ms
  - 运行明细：临时报告已汇总到本文，`.runtime/full-regression/` 仅作为本地运行缓存，不作为持久审计文件保留。
  - 覆盖：云端容器健康、`/readyz`、受保护 API 401、前端静态入口、MySQL 调优检查、Go bff/market/scan readyz、在线 Go/Rust 性能验收。

- `python scripts/full_regression_runner.py --profile full --only frontend_responsive_smoke --frontend-port 4175 --fail-fast`
  - 结果：1 passed / 0 failed / 0 skipped
  - 耗时：24222 ms
  - 运行明细：临时报告已汇总到本文，`.runtime/full-regression/` 仅作为本地运行缓存，不作为持久审计文件保留。
  - 说明：响应式 smoke 文件格式修正后复跑通过。

## 关键证据摘要

- 后端：`backend/.venv/bin/python -m pytest backend/tests` 通过，`716 passed, 47 warnings in 44.41s`。
- 前端：`npm run lint`、`npm test -- --run`、`npm run build` 均通过；Vitest `15 passed (15)`，测试项 `50 passed (50)`。
- 响应式 UI：`frontend/scripts/smoke-responsive.mjs` 覆盖 `/monitor`、`/emotion`、`/analysis`、`/playbook`、`/strategy`、`/backtest`、`/paper`、`/settings`，校验 3 类 viewport、页面错误、横向溢出、可见内容、主区域渲染与认证守卫。
- API smoke：`scripts/app_api_smoke.sh` 现在显式配置强认证环境，注册/登录获取 Bearer token，并覆盖 app bootstrap、watchlist、home、low-buy 与空候选详情兼容。
- QA deep smoke：`scripts/qa_smoke.sh` 现在对 backtest/replay 使用认证头，并校验当前异步回测任务响应契约。
- Go/Rust：`scripts/verify_go_rust_performance_acceptance.py` 通过；Go 三个服务测试通过，market-read-service batch cache benchmark 低于阈值；Rust `tquant-rs` ATR/RSI/VWAP/RankIC/max drawdown/rolling 测试通过，Python seam 无 fallback/error。
- 云端性能：`docs/reports/gupiao-cloud-performance-2026-05-27-120241.json` 结果 `ok: true`；`/readyz` p95 5.005 ms，monitor BFF p95 17.771 ms，market pulse p95 27.752 ms，priority board p95 27.698 ms，watchlist signals p95 8.704 ms；Rust 指标 `hits: 6, fallbacks: 0, errors: 0`。

## 已补齐的测试缺口

- 增加 `scripts/full_regression_runner.py`，把原本分散的 pytest、Vitest、lint、build、Go test、Rust test、UI smoke、API smoke、QA deep、Go/Rust acceptance、prod preflight、cloud verify 统一成 profile 化回归。
- 增加 `backend/tests/test_full_regression_runner.py`，防止回归编排丢失关键覆盖维度、云端验证入口、敏感信息脱敏、页面路由列表、API smoke 认证和 QA deep 当前契约。
- 扩展响应式页面 smoke，从 5 个页面扩到 8 个核心页面，并增加更多 mock API，减少因数据缺失造成的假阳性。
- 修正 app API smoke 的登录态、AUTH_SECRET_KEY、ADMIN_API_TOKEN、后台任务关闭和 low-buy 空候选处理。
- 修正 QA deep 对 `/api/backtests`、`/api/replays` 的认证与当前异步回测接口契约。

## 剩余风险

- 后端 pytest 的 sklearn 训练相关 RuntimeWarning 已在后续治理中收敛；warning budget 入口见 `scripts/warning_budget.py` 和 `docs/operations/observability-warning-budget-runbook.md`。
- `profile release` 默认不包含需要 SSH 的 `cloud_verify`，必须显式使用 `--cloud-verify` 或 `make full-regression-cloud`。
- 云端性能报告显示 Go BFF 有 partial source failures 计数，当前请求成功且 proxy fallback 为 0；后续治理已把 partial failure 拆为 timeout/status/decode/other 并补充 Prometheus 告警。
