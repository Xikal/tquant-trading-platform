# Confirmed Buy Strategy Backtest Baseline 2026-05-27

## 结论

本次补齐了 `buy_now / soft_buy_now` 专项回测口径。当前本地数据只能覆盖约 6.26 个月，不能替代完整 24 个月验收。基于当前可评估区间，confirmed 信号整体表现不足，后续必须优先验证 ATR 止损、T+1/T+2 出口结构和市场退潮过滤。

## 报告产物

- JSON：`backend/data/reports/low_buy_market_backtest_24m_confirmed_2025-10-09_2026-04-20.json`
- Markdown：`backend/data/reports/low_buy_market_backtest_24m_confirmed_2025-10-09_2026-04-20.md`
- 命令：

```bash
DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db \
PYTHONPATH=backend:. \
backend/.venv/bin/python backend/scripts/low_buy_market_backtest.py \
  --start 2025-10-09 \
  --end 2026-04-28 \
  --months 24 \
  --strategies all \
  --states confirmed \
  --engine fast \
  --materialization-mode isolated \
  --scan-limit 480 \
  --limit 80 \
  --output-dir backend/data/reports
```

## 数据覆盖

- 请求窗口：24 个月。
- 实际可评估区间：`2025-10-09` 至 `2026-04-20`。
- 实际估算月份：6.26 个月。
- 覆盖率：26.08%。
- 状态：partial。
- 结论：只能作为部分区间 baseline，不能作为完整 24 个月上线验收。

## 全策略 Confirmed 汇总

| 指标 | 数值 |
|---|---:|
| 评估样本 | 205 |
| 成交样本 | 202 |
| 净胜率 | 44.55% |
| 平均净收益 | -0.0982% |
| 总收益 | -32.9389% |
| 年化收益 | -76.0648% |
| 最大回撤 | -58.8845% |
| Sharpe | -0.3482 |
| Profit Factor | 0.9495 |
| 平均持仓 | 2.45 天 |
| 回撤恢复 | 截至回测结束尚未恢复最大回撤 |

## 信号与原因诊断

| 类型 | 分布 |
|---|---|
| 全部信号状态 | `watch=7276`, `avoid=4053`, `near_entry=2380`, `buy_now=176`, `soft_buy_now=29` |
| 本次评估状态 | `buy_now`, `soft_buy_now` |
| 状态过滤跳过 | `watch=7276`, `avoid=4053`, `near_entry=2380` |
| 未成交原因 | `信号后 2 日未出现可成交买点。=3` |
| 退出原因 | `触发移动防守线。=65`, `触发首次止盈位。=64`, `触发止损位。=46`, `到达最长持有天数，按收盘价退出。=26`, `开盘跳空跌破止损位，按开盘价退出。=1` |

## 策略明细

| 策略 | 评估 | 成交 | 净胜率 | 平均净收益 | 总收益 | 最大回撤 | Sharpe | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `first_board` 首板回调 | 39 | 39 | 43.59% | -0.1564% | -9.9682% | -33.9743% | -0.5168 | 0.91 |
| `volume_shrink` 量能低吸 | 11 | 10 | 30.0% | -0.9746% | -9.8451% | -11.9187% | -4.3682 | 0.5102 |
| `late_session_strong_support` 收盘强势承接 | 8 | 8 | 50.0% | 1.3404% | 10.0107% | -10.5294% | 3.7209 | 1.7842 |
| `core_midcap_vwap_ma5_retrace` 中军VWAP/均线回踩 | 2 | 1 | 0.0% | -8.235% | -8.235% | -8.235% | 0.0 | 0.0 |
| `n_pattern_long_wash` 长洗N字冲高 | 103 | 102 | 46.08% | 0.2008% | 10.2434% | -46.8545% | 0.689 | 1.1007 |
| `n_pattern_short_wash` 短洗N字冲高 | 42 | 42 | 45.24% | -0.6421% | -25.7628% | -42.5499% | -2.8126 | 0.6633 |

其余策略在当前 confirmed 口径下无成交样本：`classic_retrace`、`ma_support`、`sector_mainline_first_divergence_low_buy`、`mainline_limitup_shrink_retrace_reclaim`、`ma_channel_band`、`leader_pullback_band`、`breakout_support`、`limit_up_breakout_retrace`、`divergence_consensus`、`deep_pullback`、`trend_rebound`。

## 后续动作

## 执行模型矩阵

已新增 `backend/scripts/low_buy_execution_matrix.py`，用于统一跑固定止损、ATR 动态止损、T+1/T+2 出口、快止盈/移动防守矩阵。

报告产物：

- JSON：`backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json`
- Markdown：`backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.md`
- 阶段收尾 JSON：`backend/data/reports/execution_matrix_full/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json`
- 阶段收尾 Markdown：`backend/data/reports/execution_matrix_full/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.md`

命令：

```bash
DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db \
PYTHONPATH=backend:. \
backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py \
  --start 2025-10-09 \
  --end 2026-04-28 \
  --months 24 \
  --strategies all \
  --states confirmed \
  --engine fast \
  --materialization-mode isolated \
  --scan-limit 480 \
  --limit 80 \
  --variants default_exit,fixed_stop_m2p5,atr_stop_1p0,force_t1_close,force_t2_close,quick_tp3_trailing1 \
  --resume-existing \
  --resume-search-dir backend/data/reports/execution_matrix \
  --output-dir backend/data/reports/execution_matrix \
  --matrix-output-dir backend/data/reports/execution_matrix
```

当前矩阵同样受限于本地数据，只覆盖约 6.26 个月，不能替代完整 24 个月验收。按用户要求本轮已停止长跑并收尾，当前阶段矩阵覆盖 6 个变体；`fixed_stop_m3p5`、`atr_stop_0p8`、`atr_stop_1p2` 尚未跑完，可使用 `--resume-existing` 继续。

| 执行模型 | 成交 | 净胜率 | 平均净收益 | 止损率 | 执行 PF | 总收益 | 最大回撤 | Sharpe | 平均持仓 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选原始退出计划 | 202 | 44.55% | -0.0982% | 23.27% | 0.9495 | -32.9389% | -58.8845% | -0.3482 | 2.45 |
| 固定 -2.5% 止损 | 202 | 31.68% | -0.346% | 63.86% | 0.8027 | -56.1869% | -68.8534% | -1.5397 | 2.72 |
| ATR 1.0x 动态止损 | 202 | 43.56% | -0.3358% | 30.2% | 0.8448 | -59.1805% | -70.8719% | -1.1496 | 2.3 |
| 最迟 T+1 收盘退出 | 202 | 45.54% | 0.3029% | 19.8% | 1.1893 | 51.7536% | -42.7195% | 1.089 | 1.36 |
| 最迟 T+2 收盘退出 | 202 | 43.56% | 0.1075% | 22.28% | 1.0575 | -0.2683% | -45.9759% | 0.3632 | 1.91 |
| 3% 首次止盈 + 1% 移动防守 + 最多 3 天 | 202 | 82.67% | 0.826% | 17.33% | 2.0085 | 384.6271% | -27.1855% | 4.5913 | 1.3 |

阶段结论：

- 固定 -2.5% 在当前部分区间明显变差，止损率上升到 63.86%，不能推广。
- ATR 1.0x 在当前部分区间变差，止损率上升到 30.2%，不能推广。
- T+1 出口改善均净收益、执行 PF 和持仓周期，值得进入完整 24M/OOS 验证。
- `3% 首次止盈 + 1% 移动防守 + 最多 3 天` 在当前部分区间表现最好，但盈亏比仅 0.4209，说明收益结构偏高胜率小利润，不能仅凭该区间直接切生产。

## Q-006 市场保护 A/B 入口

已新增研究态市场保护回测入口，用于验证 `risk_release`、`high_flyer_retreat` 等退潮/高位分化状态下是否应把 `buy_now` / `soft_buy_now` 降级或阻断。该入口默认关闭，只写入回测诊断，不改变生产低吸策略、模拟盘或优先榜主路径。

代码入口：

- `backend/scripts/low_buy_market_backtest_market_guard.py`
- `backend/scripts/low_buy_market_backtest.py --market-guard-mode`
- `backend/scripts/low_buy_market_backtest_runner.py`
- `backend/scripts/low_buy_market_backtest_reporting.py`
- `backend/scripts/low_buy_market_backtest_markdown.py`

新增参数：

- `--market-guard-mode none|degrade_retreat|block_retreat`
- `--market-guard-states high_flyer_retreat,risk_release`
- `--market-guard-degrade-to near_entry|watch|avoid`
- `--market-guard-min-strength`

真实退潮/风险释放 smoke：

- 报告：`backend/data/reports/smoke/market_guard/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_2026-04-09_2026-04-20.md`
- 命令：

```bash
DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db \
PYTHONPATH=backend:. \
backend/.venv/bin/python backend/scripts/low_buy_market_backtest.py \
  --start 2026-03-01 \
  --end 2026-04-28 \
  --months 24 \
  --strategies first_board,volume_shrink,n_pattern_long_wash,n_pattern_short_wash \
  --states confirmed \
  --engine fast \
  --materialization-mode isolated \
  --scan-limit 160 \
  --limit 40 \
  --max-dates 8 \
  --market-guard-mode block_retreat \
  --market-guard-states high_flyer_retreat,risk_release \
  --output-dir backend/data/reports/smoke/market_guard
```

结果：8 个评估交易日、9 个 confirmed 信号，`market_guard_count=0`。该窗口没有出现目标退潮状态下的 actionable confirmed 信号，因此只能证明报告字段与默认无副作用路径可运行，不能证明退潮保护有效或无效。

强制机制 smoke：

- 报告：`backend/data/reports/smoke/market_guard_forced/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_broad_rally-repair-low_volume_wait-weight_support-weight_support_active-fast_rotation-high_flyer_retreat-risk_release_to_avoid_min_0_2026-04-09_2026-04-20.md`
- 命令：

```bash
DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db \
PYTHONPATH=backend:. \
backend/.venv/bin/python backend/scripts/low_buy_market_backtest.py \
  --start 2026-03-01 \
  --end 2026-04-28 \
  --months 24 \
  --strategies first_board,volume_shrink,n_pattern_long_wash,n_pattern_short_wash \
  --states confirmed \
  --engine fast \
  --materialization-mode isolated \
  --scan-limit 160 \
  --limit 40 \
  --max-dates 8 \
  --market-guard-mode block_retreat \
  --market-guard-states broad_rally,repair,low_volume_wait,weight_support,weight_support_active,fast_rotation,high_flyer_retreat,risk_release \
  --output-dir backend/data/reports/smoke/market_guard_forced
```

结果：`market_guard_count=9`，分布为 `block_retreat:fast_rotation:buy_now->avoid=4`、`block_retreat:repair:buy_now->avoid=2`、`block_retreat:weight_support_active:buy_now->avoid=2`、`block_retreat:broad_rally:buy_now->avoid=1`。该结果只用于验证机制和诊断字段，不作为生产市场保护规则。

阶段结论：Q-006 的 A/B 入口、报告字段和测试已完成；完整 24 个月退潮样本验证仍未完成。

## Q-007 首板出货风险阈值矩阵

已新增 `first_board` 预筛 `max_distribution_risk_score` 研究矩阵，用于比较 5.8、5.5、5.2、5.0 对候选数、confirmed 成交、PF 和回撤的影响。矩阵通过研究态 prefilter override 运行，不修改生产默认参数。

代码入口：

- `backend/app/services/low_buy/candidate_rule_params.py`
- `backend/scripts/low_buy_market_backtest.py --prefilter-override`
- `backend/scripts/low_buy_first_board_distribution_matrix.py`

报告产物：

- JSON：`backend/data/reports/first_board_distribution_matrix/first_board_distribution_matrix_24m_confirmed_2025-10-09_2026-04-28.json`
- Markdown：`backend/data/reports/first_board_distribution_matrix/first_board_distribution_matrix_24m_confirmed_2025-10-09_2026-04-28.md`

命令：

```bash
DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db \
PYTHONPATH=backend:. \
backend/.venv/bin/python backend/scripts/low_buy_first_board_distribution_matrix.py \
  --start 2025-10-09 \
  --end 2026-04-28 \
  --months 24 \
  --states confirmed \
  --scan-limit 480 \
  --limit 80 \
  --thresholds 5.8,5.5,5.2,5.0 \
  --output-dir backend/data/reports/first_board_distribution_matrix \
  --matrix-output-dir backend/data/reports/first_board_distribution_matrix
```

当前矩阵仍受本地数据限制，只覆盖约 6.26 个月，不能替代完整 24 个月验收。

| 预筛阈值 | 命中候选 | 候选保留 | confirmed | 成交 | 净胜率 | 均净收益 | PF | 最大回撤 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5.8 | 1178 | 100.0% | 39 | 39 | 43.59% | -0.1564% | 0.91 | -33.9743% |
| 5.5 | 1176 | 99.83% | 39 | 39 | 43.59% | -0.1564% | 0.91 | -33.9743% |
| 5.2 | 1176 | 99.83% | 39 | 39 | 43.59% | -0.1564% | 0.91 | -33.9743% |
| 5.0 | 1176 | 99.83% | 39 | 39 | 43.59% | -0.1564% | 0.91 | -33.9743% |

阶段结论：

- 当前可用样本中，预筛阈值从 5.8 降到 5.0 只减少 2 个命中候选，confirmed 成交和绩效完全不变。
- 执行确认层已经配置 `first_board.max_distribution_risk_score=5.2`，因此单独下调预筛阈值不足以改善当前 confirmed 结果。
- 现阶段没有证据支持把生产预筛默认值从 5.8 直接下调到 5.2；应在完整 24M/OOS 数据补齐后复跑。

## 后续动作

1. Q-002：补完整固定止损 2.5/3.5、ATR 0.8/1.0/1.2 矩阵；当前 ATR 1.0x 部分区间未通过。
2. Q-003：把 T+1 出口和 `3% 首次止盈 + 1% 移动防守 + 最多 3 天` 作为研究候选配置，补完整 24M、OOS、分市场状态和模拟盘观察，不直接上线。
3. Q-006：用完整 24M 数据复跑真实退潮/高位分化过滤 A/B，并验证新开仓减少、回撤改善和非退潮样本不过度流失。
4. Q-007：完整 24M/OOS 数据补齐后复跑首板出货风险阈值矩阵；当前部分区间不调整生产默认值。
5. 完整 24 个月验收需要补齐或连接覆盖 24 个月的日线数据源。
