# 6 个重点策略窄口径 walk-forward 执行清单

- 报告日期：2026-05-28
- 来源：docs/reports/market-state-guard-walk-forward-2026-05-28
- 新启动回测：否

| 策略 | 确认成交窗口 | 平均 PF | 平均回撤 | 保护 PF 差 | 优先级 |
| --- | ---: | ---: | ---: | ---: | --- |
| first_board | 7/7 | 2.0104 | -3.8433 | 0.0 | run_candidate_grid_first |
| volume_shrink | 7/7 | 1.21 | -8.9792 | 0.0 | run_candidate_grid_first |
| late_session_strong_support | 7/7 | 0.4639 | -4.7369 | 0.0 | run_after_core_or_keep_research |
| core_midcap_vwap_ma5_retrace | 5/7 | 0.5324 | -4.2944 | 0.0 | run_after_core_or_keep_research |
| ma_channel_band | 0/7 | 0.0 | 0.0 | 0.0 | shadow_signal_gate_first |
| leader_pullback_band | 0/7 | 0.0 | 0.0 | 0.0 | shadow_signal_gate_first |

- 下一步执行顺序：first_board, volume_shrink, late_session_strong_support, core_midcap_vwap_ma5_retrace, ma_channel_band, leader_pullback_band
- 剩余阻断：strategy_parameter_variants_not_recomputed_yet, full_purged_gap_candidate_grid_not_executed_yet, shadow_settled_sample_not_accumulated
