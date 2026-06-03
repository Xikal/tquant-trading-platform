# 24M 回测前置加速 Spike（2026-06-03）

## 范围
- 只加速 TradeOutcome 输入准备。
- 最终仍调用 `portfolio_backtest_metrics`。
- 不改同票冷却、同板块、弱市、退潮、max5/max10 等组合约束。
- 不按月份分片后各自计算 max5/max10 再合并。

## 实测命令
`PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backtest_24m_precompute_spike.py --count 240`

## 结果
| 指标 | max5 baseline | max5 precompute | max10 baseline | max10 precompute |
| --- | ---: | ---: | ---: | ---: |
| profit_factor | 2.5163 | 2.5163 | 2.5163 | 2.5163 |
| avg_trade_return_pct | 1.0633 | 1.0633 | 1.0633 | 1.0633 |
| portfolio_return_pct | 28.8896 | 28.8896 | 13.5696 | 13.5696 |
| max_drawdown_pct | -1.0952 | -1.0952 | -0.5488 | -0.5488 |
| trade_count | 120 | 120 | 120 | 120 |
| candidate_count | 240 | 240 | 240 | 240 |

- max5_equal：true
- max10_equal：true
- baseline_ms：20.495
- precompute_ms：20.298
- 墙钟下降：0.96%

## 结论
- 组合口径一致性通过。
- fixture 层面前置构建收益很小，不足以作为生产化收益证明。
- 下一阶段应优先加速真实 24M 报告的数据读取、payload normalization、TradeOutcome 批量构建，而不是改 `portfolio_backtest_metrics`。

## 回滚方式
本轮只新增 spike 脚本和测试，没有接入生产任务；删除或忽略 `backend/scripts/backtest_24m_precompute_spike.py` 即可回到原状。

