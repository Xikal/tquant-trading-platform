# 主力模型生产验收报告

- 模型：`main_force_accumulation_washout_markup_v1`
- 验证窗口：2024-05-28 至 2026-05-28
- 切分策略：12m train / 3m valid / 3m test，purged gap 10 天，随机切分禁止
- 当前结论：不可晋级
- 证据状态：research_proxy_not_true_train_valid_test_split，生产可用=否
- 阻断原因：true_walk_forward_train_valid_test_not_implemented, shadow_record_count_lt_300, settled_shadow_count_lt_120

## 离线研究摘要

- 样本数：10980
- 可买动作样本：3415
- 研究标签胜率：67.789%
- Profit Factor：38.1328
- 20 日平均标签收益：10.2148%
- fallback rate：0.0%
- 防未来函数：pass，`max_source_date <= as_of_date`，`label_start_date > as_of_date`
- OOS 晋级：阻断
- OOS 阻断：true_walk_forward_train_valid_test_not_implemented
- 注意：当前收益是未来标签研究指标，不是可成交账户收益。

## Shadow 门禁

- Shadow 观察样本：10 / 300
- Shadow 已结算样本：0 / 120
- Shadow 胜率：0.0%
- Shadow PF：0.0
- Shadow fallback rate：10.0%
- Shadow 晋级：否
- Shadow 阻断：shadow_record_count_lt_300, settled_shadow_count_lt_120

## 生产边界

- 排序加权仍保持默认关闭。
- 模拟盘小仓建议仍保持默认关闭。
- 只允许生产只读展示和 Shadow 记录。
- 不允许自动下单，不允许覆盖硬止损，不允许绕过仓位、现金、最大持仓数或日亏损暂停。
