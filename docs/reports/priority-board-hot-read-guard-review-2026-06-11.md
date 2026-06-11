# Priority Board 热读守卫复核（2026-06-11）

## 结论

本批次只复核和回归守卫，不修改 priority board 生产路径。当前 N=5 与 N=20 候选的受控热读测量均为 `4` 条跟踪 SQL，没有发现查询数随候选数量线性增长的证据。

审查报告中的“热聚合 N+1 嫌疑”在当前代码事实下应标记为 `needs_measurement / guarded`：风险点仍保留观察，但已有查询预算和 golden 输出守卫，不满足改生产代码的前置条件。

## 已覆盖守卫

- `backend/tests/test_low_buy_read_paths.py::test_priority_board_hot_read_query_budget_does_not_scale_with_candidates`
  - N=5 查询计数：`4`
  - N=20 查询计数：`4`
  - 断言：`large_count <= small_count + 2`
  - 断言：`large_count <= 6`
- `backend/tests/test_low_buy_read_paths.py::test_priority_board_hot_read_golden_output_keeps_order_and_strategy_guards`
  - 关键字段 digest：`5d981f6e5ddaa9289c20fddc2ee1a0ed98442655421f002415947d7696f3ac1d`
  - 覆盖字段：`symbol`、`strategy_key`、`buy_signal_state`、`priority_score`、`production_score`、`display_lane`、`production_sort_replaced`、`shadow_only`、`replacement_enabled`
- `backend/tests/test_low_buy_priority_board_strategy_variants.py`
  - 覆盖 `front_row_only`、`front_row_weighted`、event risk gate 下的 shadow-only 与 replacement guard。
- `backend/tests/test_low_buy_production_scoring.py`
  - 覆盖生产分、watch-only、非生产策略、低样本限权、hard risk、front row interaction 等生产评分守卫。

## 实测摘录

命令：

```bash
PYTHONPATH=backend:backend/tests:. backend/.venv/bin/python - <<'PY'
from test_low_buy_read_paths import LowBuyReadPathTests
case = LowBuyReadPathTests(methodName='test_priority_board_hot_read_query_budget_does_not_scale_with_candidates')
case.setUp()
small_count, small_response = case._measure_priority_board_hot_read(candidate_count=5)
large_count, large_response = case._measure_priority_board_hot_read(candidate_count=20)
print(f"small_count={small_count}")
print(f"large_count={large_count}")
print(f"large_total_candidates={large_response.total_candidates}")
print("top3=" + ",".join(item.symbol for item in large_response.items[:3]))
print("shadow_only=" + str(all(item.strategy_engine_shadow['shadow_only'] for item in large_response.items)))
print("replacement_enabled_false=" + str(all(item.strategy_engine_shadow['replacement_enabled'] is False for item in large_response.items)))
print("production_sort_replaced_false=" + str(all(item.production_sort_replaced is False for item in large_response.items)))
PY
```

结果：

```text
small_count=4
large_count=4
large_total_candidates=20
top3=000020,000019,000018
shadow_only=True
replacement_enabled_false=True
production_sort_replaced_false=True
```

## 验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py
```

结果：`32 passed / 1 LibreSSL warning`。

## 后续规则

后续任何新增候选上下文、榜单展示字段、read model fallback 或 priority board 热路径改动，必须同步维护查询预算测试和 golden 输出字段。只有新的测量证明查询随候选数量线性增长，才允许做批量预取或共享上下文缓存；改动必须保持排序、`production_score`、`priority_score`、lane 和 strategy engine shadow 字段零漂移。
