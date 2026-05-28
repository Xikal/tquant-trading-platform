# 策略胜率/盈利率提升闭环报告

- 生成时间：2026-05-28T10:21:55
- 请求窗口：2024-05-28 至 2026-04-28
- 总体状态：blocked_or_research_only
- 允许正式回测：否
- 允许 Walk-forward 晋级：否
- 生产参数自动变更：禁止
- 原因：两年数据覆盖、ETF 分钟线或质量门禁未达标，只允许研究/观察，不允许参数晋级。

## 数据覆盖
- 日线状态：complete，覆盖率 100.0%，实际 2024-05-28 至 2026-04-28，股票数 4967。
- 完整交易日：466 / 466。
- 分钟线状态：blocked_by_data（原始数据状态 partial），窗口内分钟线 24344，库内总分钟线 24586，任意分钟线 ETF 22 / 22 (100.0%)，验收达标 ETF 0 / 22 (0.0%)。
- ETF 分钟线阻断原因：insufficient_window_trade_day_coverage。
- ETF 分钟线验收交易日：466 个；近端短窗口分钟线不计作 24 个月验收通过。
- 窗口外分钟线：242 条，仅作为近端补数探针，不计入 24 个月验收。
- ETF 分钟线缺口样本：159915, 159930, 510300, 510310, 510500, 511880, 512170, 512200
- ETF 分钟线补数诊断：docs/reports/etf-minute-backfill-tushare-probe-2026-05-28.json，状态 partial_data，写入效果 no_bars_written，totals ok=0 empty=1 error=0。
- Provider 失败样本：510300 tushare.stk_mins: tushare token not configured; 510300 eastmoney.etf_minute: Remote end closed connection without response; 510300 akshare.fund_etf_hist_min_em: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/stock/kline/get?fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf; 510300 sina.kline: empty
- 分钟线造数策略：fake_minute_bars_forbidden。

## 数据质量与元数据门禁
- OHLC 质量：pass，重复 K 线 0，非法 OHLC 0，负成交 0。
- 交易元数据状态：fail，阻断缺口 5 个。
- 元数据缺口样本：minute_bar_snapshots.bid_ask_spread_positive_coverage_lt_95pct, minute_bar_snapshots.premium_discount_coverage_lt_95pct, minute_bar_snapshots.tracking_index_coverage_lt_95pct, minute_bar_snapshots.liquidity_tier_coverage_lt_95pct, minute_bar_snapshots.data_quality_fresh_coverage_lt_95pct
- etf_intraday_execution_metadata_coverage：ETF T0 需要真实盘口价差、折溢价、跟踪指数、流动性和 fresh/verified 分钟执行元数据；默认 0 或 partial_metadata 不能正式验收。 证据 {'etf_minute_rows': 24344, 'bid_ask_spread_positive_pct': 0.0, 'premium_discount_pct': 0.0, 'tracking_index_symbol_pct': 0.09, 'liquidity_tier_pct': 0.09, 'fresh_or_verified_pct': 0.0}

## 门禁
| 门禁 | 状态 | 严重级别 | 说明 |
|---|---|---|---|
| daily_24m_coverage | pass | blocking | 全 A 日线覆盖率必须达到阈值后才能正式回测和参数晋级。 |
| daily_quality | pass | blocking | OHLC、重复 K 线、负成交量/成交额必须通过质量门禁。 |
| market_metadata_coverage | fail | blocking | 涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 执行元数据必须通过门禁。 |
| etf_t0_minute_coverage | fail | blocking | ETF T0 必须有分钟线覆盖率，不能用日线代理验收。 |
| strategy_governance_report | pass | blocking | 必须能列出所有策略并给出治理状态。 |
| constraint_policy_coverage | pass | blocking | 策略必须具备弱市/板块/流动性/ST/涨跌停/连续止损/data_quality 等约束，弱策略和样本不足策略不得晋级。 |
| walk_forward_readiness | pass | blocking | Walk-forward 只允许在两年数据和候选策略足够时启动。 |
| temporal_no_future_function | pass | blocking | 禁止未来函数、随机时间序列切分和 Shadow 特征混入 future/next/outcome 字段。 |
| exit_model_shadow | warn | warning | 退出辅助模型必须先积累 Shadow 样本，不能直接进入生产动作。 |

## 策略治理
| 策略 | 状态 | 动作 | 样本/成交 | 胜率 | PF | 平均单笔 | 最大回撤 | 止损率 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 深度低吸 | positive_expectancy_candidate | walk_forward_then_paper_observe | 164/155 | 67.10% | 1.96 | 0.752% | -22.62% | 22.58% |
| 首板回调 | high_return_high_drawdown | add_market_state_position_exit_constraints | 8778/7874 | 49.31% | 2.07 | 0.914% | -81.04% | 6.10% |
| 均线通道波段 | high_return_high_drawdown | add_market_state_position_exit_constraints | 4993/4690 | 58.06% | 1.72 | 0.928% | -93.28% | 30.85% |
| 龙头回踩波段 | high_return_high_drawdown | add_market_state_position_exit_constraints | 1954/1814 | 56.62% | 1.43 | 0.501% | -80.28% | 31.64% |
| 量能低吸 | high_return_high_drawdown | add_market_state_position_exit_constraints | 3174/2814 | 55.19% | 1.44 | 0.445% | -95.03% | 22.10% |
| 分歧转一致 | weak_strategy | pause_or_downgrade_production_weight | 202/201 | 41.29% | 0.92 | -0.123% | -58.73% | 3.98% |
| 收盘强势承接 | high_return_high_drawdown | add_market_state_position_exit_constraints | 7027/6310 | 46.58% | 1.17 | 0.230% | -99.51% | 15.18% |
| 长洗N字冲高 | high_return_high_drawdown | add_market_state_position_exit_constraints | 1785/1743 | 48.31% | 1.13 | 0.234% | -98.11% | 23.12% |
| 原始低吸法 | high_return_high_drawdown | add_market_state_position_exit_constraints | 5616/5056 | 51.23% | 1.19 | 0.250% | -99.08% | 33.29% |
| 涨停突破回踩 | high_return_high_drawdown | add_market_state_position_exit_constraints | 1978/1926 | 43.77% | 1.01 | 0.017% | -86.32% | 21.13% |
| 均线支撑 | high_return_high_drawdown | add_market_state_position_exit_constraints | 14250/12739 | 38.47% | 1.16 | 0.238% | -99.99% | 21.99% |
| 位置支撑 | high_return_high_drawdown | add_market_state_position_exit_constraints | 4760/4249 | 47.12% | 1.04 | 0.059% | -99.84% | 21.20% |
| 趋势龙回头 | high_return_high_drawdown | add_market_state_position_exit_constraints | 2609/2372 | 47.34% | 1.07 | 0.097% | -99.23% | 28.25% |
| 中军VWAP/均线回踩 | high_return_high_drawdown | add_market_state_position_exit_constraints | 5108/4576 | 36.04% | 1.12 | 0.187% | -99.79% | 23.75% |
| 主线首分歧低吸 | weak_strategy | pause_or_downgrade_production_weight | 867/759 | 33.07% | 0.87 | -0.199% | -92.19% | 18.45% |
| 主线涨停缩量回调 | weak_strategy | pause_or_downgrade_production_weight | 500/485 | 25.57% | 0.76 | -0.380% | -88.46% | 14.43% |
| 短洗N字冲高 | weak_strategy | pause_or_downgrade_production_weight | 1792/1757 | 42.29% | 0.71 | -0.528% | -100.00% | 22.31% |

## 约束增强审计
- 状态：pass，问题数 0。
- 生产影响：audit_only_no_parameter_write。
- 基础必需约束：consecutive_stop_loss_strategy_pause, data_quality_non_fresh_no_strong_buy, last_20_trades_negative_net_win_rate_downgrade, limit_up_down_nearby_no_entry_or_downgrade, liquidity_amount_floor, sector_concentration_position_cap, st_stopped_delisted_no_entry
- 高风险必需约束：market_breadth_poor_reduce, sector_strength_floor, trailing_profit_pullback_limit, weak_market_block_or_reduce
- 约束增强审计只读，不修改生产参数、订单、持仓或账本。
- 弱策略不得获得生产晋级动作；样本不足策略不得进入调参网格。
- 高回撤和弱策略必须包含弱市/市场宽度/板块强度/退出回吐约束。

## Walk-forward
- 状态：ready
- 推荐切分：12m_train_3m_validation_3m_oos_monthly_roll
- 时间序列切分：required_time_ordered_only_no_random_split；随机切分：禁止。
- 窗口数：7，滚动步长：monthly。
- 候选策略数：13
- 阻断原因：无

| 窗口 | 训练 | 验证 | 样本外 | 交易日 |
|---:|---|---|---|---:|
| 1 | 2024-05-28 至 2025-04-30 | 2025-05-06 至 2025-07-31 | 2025-08-01 至 2025-10-31 | 226/62/60 |
| 2 | 2024-06-03 至 2025-05-30 | 2025-06-03 至 2025-08-29 | 2025-09-01 至 2025-11-28 | 241/64/59 |
| 3 | 2024-07-01 至 2025-06-30 | 2025-07-01 至 2025-09-30 | 2025-10-09 至 2025-12-31 | 242/66/60 |
| 4 | 2024-08-01 至 2025-07-31 | 2025-08-01 至 2025-10-31 | 2025-11-03 至 2026-01-30 | 242/60/63 |
| 5 | 2024-09-02 至 2025-08-29 | 2025-09-01 至 2025-11-28 | 2025-12-01 至 2026-02-27 | 241/59/57 |
| 6 | 2024-10-08 至 2025-09-30 | 2025-10-09 至 2025-12-31 | 2026-01-05 至 2026-03-31 | 244/60/56 |
| 7 | 2024-11-01 至 2025-10-31 | 2025-11-03 至 2026-01-30 | 2026-02-02 至 2026-04-28 | 243/63/55 |

- 受控参数网格：
  - min_score: current, +3, +5
  - max_holding_days: 2, 3, 5
  - stop_loss: current, -2.5pct, ATR_1.0
  - take_profit: 3.0pct, 4.0pct, 5.0pct
  - trailing_pullback: 1.0pct, 1.5pct, 2.0pct
  - single_position_pct: 0.5x, current
  - market_state_switch: current, reduce_weak, block_retreat
  - sector_strength_threshold: current, +10pct, +20pct
  - liquidity_amount_threshold: current, +20pct, +50pct

- 稳定性与过拟合检查：
  - parameter_stability_pm_10pct：最优参数附近 -10%/+10% 仍需保持 OOS 期望不显著恶化。
  - parameter_stability_pm_20pct：关键阈值 -20%/+20% 压力测试用于识别尖峰最优。
  - pbo_or_equivalent：用 IS 排名到 OOS 排名退化比例估算过拟合概率。
  - deflated_sharpe_or_equivalent：对多参数尝试后的 Sharpe 做保守修正或等价降噪评估。
  - market_state_pass_rate：按市场状态分组检查 OOS 通过率，弱市/退潮不得隐藏总样本里。

## 防未来函数门禁
- 状态：pass，问题数 0。
- 检查项：walk_forward_train_validation_oos_order, random_time_series_split_forbidden, exit_model_shadow_feature_snapshot_no_future_keys
- 禁止特征关键词：future, next, outcome, t_plus, t+
- T 日信号和模型特征只能使用当时可得数据；未来收益、结算 outcome、next/future 字段不得进入特征快照。
- Walk-forward 必须保持训练、验证、样本外严格时间顺序，禁止随机切分时间序列。

## 退出模型 Shadow
- 状态：insufficient_shadow_samples，记录 0，已结算 0。
- 生产影响：none_shadow_only；硬止损可被覆盖：否。
- Shadow-only：是；可晋级：否。
- 动作差异：一致 0，更激进 0，更保守 0，fallback 0，硬止损覆盖风险 0。
- 后验摘要：已标注 0，5日均收益 0.0%，5日平均最大不利 0.0%，卖飞率 0.0%。
- 晋级阻断：shadow_record_count_lt_30, settled_shadow_count_lt_30

## 数据补齐计划
- `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope t0-etf --start-date 2024-05-28 --end-date 2026-04-28 --period 5m --workers 2 --allow-partial`
- ETF 1m 免费接口通常只返回近 5 个交易日；24 个月 ETF T0 验收应优先补 5m 历史分钟线，或接入正式分钟数据源后再启用 1m 验收。

## 不变量
- T 日信号只能使用 T 日及以前可得数据；T+1 交易不能使用 T+1 收盘后数据。
- 分钟策略只能使用当前分钟及以前数据；市场情绪、板块强度、龙头强度必须使用当时快照。
- Python 保持策略、风控、回测语义和模拟盘账本真源；Go/Rust 不输出买卖决策。
- 所有新增策略、参数、模型、约束必须可关闭、可回滚、可观测。
- 回测与治理脚本只读，不修改生产参数、订单、成交、持仓或账本。

## 下一步
- 补齐并持久化涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 折溢价/流动性/盘口价差元数据；OHLCV 通过不等于可验收。
- 补齐 ETF 白名单分钟线、费用/滑点/溢折价/流动性/T+0 字段；分钟线不足时 ETF T0 继续 blocked_by_data。
- 继续积累退出模型 Shadow 样本；只记录规则动作和模型建议差异，不改变订单和账本。
- 将治理结果接入回测页/策略工作台/模拟盘展示，但保持生产参数只读。
