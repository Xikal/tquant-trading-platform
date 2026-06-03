# 全市场扫描并行化 Spike（2026-06-03）

## 范围
- 只做 fixture-only spike。
- 不写生产表。
- 不替换现有物化任务。
- 固定策略：`first_board`
- 固定交易日：`2026-06-03`
- 固定标的数：200

## 实测命令
`PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/parallel_scan_spike.py --symbols 200 --trade-date 2026-06-03 --strategy-key first_board --max-workers 8 --simulate-io-seconds 0.001`

## 结果
| 项 | 串行 | 并行 |
| --- | ---: | ---: |
| symbol_count | 200 | 200 |
| candidate_count | 200 | 200 |
| buy_now | 18 | 18 |
| near_entry | 43 | 43 |
| watch | 139 | 139 |
| wall clock ms | 252.894 | 32.311 |

- 墙钟下降：87.22%
- ordering_equal：true
- golden_equal：true
- payload_hash：`10dfad840d023189ccf1cba3c4cbbaa0e4e0bafc422b401817381ee7bf2cc8fb`
- DB 查询放大：0（fixture-only，无 DB 查询）

## 结论
满足 spike 进入下一阶段评估的必要条件：
- golden 100% 一致。
- 墙钟下降 >=25%。
- DB 查询数未放大。

但本次仍不建议直接生产化，原因：
- 数据为 deterministic fixture，不是真实全市场扫描输入。
- 尚未覆盖真实 DB 查询、行情缓存、策略池组合和失败恢复。
- 下一阶段若生产化，必须用真实 100-300 标的小批量、固定 trade_date、固定策略做同样 golden。

