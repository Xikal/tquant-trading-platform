# 前排加权生产评分综合 readiness 报告

- 结论：`shadow_paper_extend_oos`。
- 建议小流量生产观察：否。
- 下一步：`continue_shadow_paper_validation`。
- 未部署，未替换生产排序。

## 阻断项

- `formal_oos_start_unavailable`
- `minute_coverage_below_95pct`
- `oos_filled_count_below_150`
- `oos_window_below_60_trade_days`
- `tick_data_insufficient_for_real_money_production`
- `tradability_fill_retention_below_70pct`
- `walk_forward_pass_rate_below_70pct`
- `walk_forward_two_consecutive_failed_windows`
- `walk_forward_window_count_below_6`
- `weak_market_sample_insufficient_keep_watch_only`

## OOS

- 状态：`awaiting_post_freeze_trade_dates`。
- 正式 OOS 起止：- 至 -。
- OOS 交易日：0 / 60。
- OOS 信号日：0。
- OOS 成交样本：0 / 150。

## Walk-forward

- 通过窗口：2 / 5。
- 通过率：40.00%。

## 可成交性

- 状态：`blocked`。
- 分钟覆盖：0.00%。
- tick 行数：0。
- 可成交留存：0.00%。

## 弱市压缩

- 状态：`weak_market_blocked`。
