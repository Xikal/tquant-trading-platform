# 前排加权弱市候选压缩 A/B

- 结论：未通过。
- 本报告只用于 Shadow/Paper，不替换生产排序。
- 推荐策略：`weak_soft_score86_cap20`。

## 阻断项

- `weak_market_sample_insufficient_keep_watch_only`

## 对比

| 策略 | 样本 | 成交 | 信号日 | max5收益 | max5 PF | 弱市成交 | 弱市平均单笔 | 弱市 PF | 降级原因 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| weighted_current | 1544 | 1481 | 191 | 111.73% | 1.91 | 37 | 0.416% | 1.23 | 无 |
| weak_soft_only_cap30 | 1528 | 1465 | 181 | 111.74% | 1.93 | 21 | 2.373% | 4.89 | weak_market_buy_now_demoted:16 |
| weak_soft_score86_cap20 | 1522 | 1459 | 181 | 111.74% | 1.93 | 15 | 3.162% | 32.60 | weak_market_buy_now_demoted:16, weak_market_score_below_policy:6 |
| weak_watch_only | 1506 | 1444 | 177 | 111.74% | 1.93 | 0 | 0.000% | 0.00 | weak_market_watch_only:38 |
