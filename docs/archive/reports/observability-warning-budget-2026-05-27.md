# Observability And Warning Budget Governance Report 2026-05-27

## 结论

本轮治理已把后端 pytest warning 从全量 `24 warnings` 收敛到 warning budget 允许的 1 个本地 LibreSSL 环境 warning；Go BFF partial source failures 和 Go market-read cache fallback 也完成指标拆分，可按原因和严重级别告警。

## 已治理项

- ML logistic 训练数值 warning：
  - 根因：小样本/可分数据下 sklearn logistic 路径在概率预测矩阵乘法中触发 RuntimeWarning。
  - 修复：logistic 模型使用更稳的 `liblinear`、正则化和 balanced class weight；二分类概率计算走显式稳定 sigmoid 路径。
  - 证据：`backend/tests/test_phase4_phase5_foundation.py` 对训练和 runtime worker 增加 RuntimeWarning 零容忍断言。

- 因子挖掘相关性 warning：
  - 根因：常量序列进入 pandas/numpy correlation/autocorr 时触发 divide warning。
  - 修复：`_safe_rank_corr`、`_safe_pearson`、`_safe_autocorr` 在方差不足时返回 `None`，不调用会除零的默认相关性实现。
  - 证据：`backend/.venv/bin/python -m pytest backend/tests/test_factor_mining.py -q -ra` 通过，仅剩允许的 LibreSSL warning。

- pandas 月频 warning：
  - 根因：`resample("M")` 触发 pandas FutureWarning。
  - 修复：改为 `resample("ME")`。

- BFF partial source failure 可观测性：
  - 新增指标：`reason="timeout|status|decode|other"`。
  - 响应 `partial_errors` 新增 `reason` 字段。
  - 告警：timeout、status/decode/other 分开处理，避免只看总数。

- market-read fallback 可观测性：
  - 新增 `tquant_market_read_unresolved_misses_total`。
  - Redis miss、MySQL fallback、unresolved miss 分离，避免把可接受的 MySQL 降级读误判为核心故障。

## 新增门禁

- `python scripts/warning_budget.py backend/tests`
- `make warning-budget`
- `python scripts/full_regression_runner.py --profile core --only warning_budget --fail-fast`

CI 已新增 `Enforce backend warning budget` 步骤。

## 验证结果

- `backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py backend/tests/test_full_regression_runner.py -q -ra`
  - 结果：39 passed / 1 allowed warning

- `python scripts/warning_budget.py backend/tests/test_phase4_phase5_foundation.py`
  - 结果：pass

- `python scripts/warning_budget.py backend/tests/test_factor_mining.py`
  - 结果：pass

- `python scripts/full_regression_runner.py --profile core --only warning_budget --fail-fast`
  - 结果：PASS warning_budget
  - 运行明细：临时报告已汇总到本文，`.runtime/full-regression/` 仅作为本地运行缓存，不作为持久审计文件保留。
  - warning budget：1 个允许的 LibreSSL 环境 warning，0 个 unexpected warning，0 个 violation。

- `python scripts/full_regression_runner.py --profile core --only backend_pytest --only warning_budget --only go_bff_test --only go_market_read_test --fail-fast`
  - 结果：backend_pytest、warning_budget、go_bff_test、go_market_read_test 全部 PASS
  - 运行明细：临时报告已汇总到本文，`.runtime/full-regression/` 仅作为本地运行缓存，不作为持久审计文件保留。
  - backend pytest：719 passed / 1 allowed warning

- `cd go-services/bff-gateway && go test ./...`
  - 结果：pass

- `cd go-services/market-read-service && go test ./...`
  - 结果：pass

- `python -m py_compile scripts/warning_budget.py scripts/full_regression_runner.py scripts/measure_cloud_go_rust_performance.py`
  - 结果：pass

- `git diff --check`
  - 结果：pass

- `backend/.venv/bin/python -m pytest backend/tests/test_full_regression_runner.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_factor_mining.py -q -ra`
  - 结果：50 passed / 1 allowed warning

## 运行手册

详细处理口径见：

- `docs/operations/observability-warning-budget-runbook.md`
- `deploy/prometheus/tquant-alerts.yml`

## 剩余风险

- 当前 warning budget 允许 1 个本地 LibreSSL 环境 warning；在 Linux CI 或生产镜像里如果仍出现该 warning，应改为修复运行时 OpenSSL，而不是扩大豁免。
- 云端 `observability` 新分级需要下一次部署后由新 Go 服务指标实际填充；当前本地测试已覆盖指标输出，云端旧报告仍是部署前指标结构。
