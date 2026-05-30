# 前排加权 walk-forward 滚动验证

- 结论：未通过。
- 窗口：2 / 5 通过，通过率 40.00%。
- 说明：这是固定策略历史滚动回放，不等同正式前瞻 OOS。

## 阻断项

- `walk_forward_window_count_below_6`
- `walk_forward_pass_rate_below_70pct`
- `walk_forward_two_consecutive_failed_windows`

## 窗口明细

| 窗口 | OOS | 样本 | 成交 | max5收益 | max5 PF | +30bps max5 PF | 弱市平均单笔 | 阻断 | 通过 |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 2025-09-11~2025-12-11 | 212 | 200 | 7.55% | 1.49 | 1.21 | 1.058% | max5_extra_30bps_pf_below_1_30, max10_extra_30bps_pf_below_1_20 | 否 |
| 2 | 2025-10-20~2026-01-13 | 210 | 196 | 8.73% | 1.69 | 1.33 | 1.591% | 无 | 是 |
| 3 | 2025-11-07~2026-02-02 | 169 | 161 | 9.08% | 1.76 | 1.42 | 1.591% | 无 | 是 |
| 4 | 2025-12-05~2026-03-10 | 225 | 210 | 0.39% | 1.04 | 0.86 | 0.000% | max5_extra_30bps_pf_below_1_30, max5_extra_30bps_avg_trade_not_positive, max10_extra_30bps_pf_below_1_20, max10_extra_30bps_avg_trade_not_positive | 否 |
| 5 | 2026-01-07~2026-04-09 | 196 | 183 | 7.01% | 1.43 | 1.22 | 0.000% | max5_extra_30bps_pf_below_1_30, max10_extra_30bps_pf_below_1_20, max10_extra_30bps_avg_trade_not_positive | 否 |
