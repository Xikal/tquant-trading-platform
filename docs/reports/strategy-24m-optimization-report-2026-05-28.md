# 策略模型与相关策略24个月优化审查报告

- 生成时间：2026-05-29T09:46:32
- 数据源日期：2026-05-28
- 评估窗口：2024-05-28 至 2026-04-21，交易日 461
- 策略数量：17

## 一、总论

- 是否可接入生产链路：否
- 是否允许生产参数变更：否
- 原因：日线策略已有24个月研究基线，但 ETF 分钟线、成交元数据、Shadow 样本、候选参数 walk-forward/purged gap 均未闭环；新增模型只能进入只读 Shadow 或研究观察。

## 二、保留/降权/暂停/晋级清单

- 保留当前层级：first_board, volume_shrink, late_session_strong_support, core_midcap_vwap_ma5_retrace, ma_channel_band, leader_pullback_band
- 降权或降级观察：classic_retrace, ma_support, n_pattern_long_wash, breakout_support, limit_up_breakout_retrace, trend_rebound
- 暂停或降权生产权重：sector_mainline_first_divergence_low_buy, mainline_limitup_shrink_retrace_reclaim, n_pattern_short_wash, divergence_consensus
- 可生产晋级：无
- 仅 Paper/Shadow 观察：deep_pullback

## 二点五、平台策略与模型覆盖清单

- 覆盖项：8，生产可用项：0
| 范围 | 入口 | 状态 | 覆盖策略/模型 | 关键指标 | 生产可用 |
| --- | --- | --- | --- | --- | --- |
| 低吸/主线/龙头日线策略 24 个月基线 | low_buy_playbooks | completed_research_baseline | classic_retrace, ma_support, first_board, volume_shrink, late_session_strong_support, core_midcap_vwap_ma5_retrace, sector_mainline_first_divergence_low_buy, mainline_limitup_shrink_retrace_reclaim, ma_channel_band, leader_pullback_band, n_pattern_long_wash, n_pattern_short_wash, breakout_support, limit_up_breakout_retrace, divergence_consensus, deep_pullback, trend_rebound | strategy_count=17, coverage_pct=100.0 | 否 |
| ETF T0 分钟级做T | etf_backtest_and_research | partial_minute_coverage | etf_t0 | eligible_profile_count=22, accepted_symbol_count=0 | 否 |
| 行业 ETF 替代做T | paper_auto_and_market_monitor | no_shadow_or_trade_samples | sector_etf_t0 | sample_count=0, settled_count=0 | 否 |
| 个股底仓 SmartT 洗盘加仓日线代理验证 | paper_smart_t | no_signal_samples | first_board, volume_shrink, late_session_strong_support, core_midcap_vwap_ma5_retrace, sector_mainline_first_divergence_low_buy, mainline_limitup_shrink_retrace_reclaim, n_pattern_long_wash, n_pattern_short_wash | signal_count=0, washout_signal_count=0 | 否 |
| 主力建仓/洗盘/拉升观测模型 | low_buy_shadow_model | research_proxy_not_true_train_valid_test_split | main_force_accumulation_washout_markup_v1 | record_count=10980, oos_promotion_ready=False | 否 |
| 止盈止损辅助模型 | paper_exit_shadow | shadow_candidate | paper_exit_model_v1 | settled_count=0, record_count=0, walk_forward_passed=7, walk_forward_windows=7 | 否 |
| 次日事件模型 | low_buy_event_metrics | no_standalone_24m_model_readiness_artifact | next_day_event_model | {} | 否 |
| 回测页默认 preset 策略范围 | backtest_page | covered_by_low_buy_daily_baseline | core_midcap_vwap_ma5_retrace, first_board, late_session_strong_support, mainline_limitup_shrink_retrace_reclaim, n_pattern_long_wash, n_pattern_short_wash, sector_mainline_first_divergence_low_buy, volume_shrink | preset_count=3 | 否 |
- 覆盖阻断：low_buy_daily_24m:candidate_parameter_grid_not_fully_walk_forwarded; low_buy_daily_24m:purged_gap_not_executed_for_candidate_grid; low_buy_daily_24m:production_param_write_from_backtest_forbidden; etf_t0_minute:etf_t0_24m_minute_coverage_not_accepted; sector_etf_t0:sector_etf_t0_shadow_or_trade_samples_insufficient; smart_t:smart_t_minute_or_signal_samples_insufficient; main_force_observation_model:true_walk_forward_train_valid_test_not_implemented; main_force_observation_model:shadow_record_count_lt_300; main_force_observation_model:settled_shadow_count_lt_120; paper_exit_model:online_shadow_settled_sample_lt_required; paper_exit_model:full_strategy_parameter_grid_not_executed; paper_exit_model:hard_stop_must_not_be_removed_or_loosened ...

## 三、策略指标与审查结论

| 策略 | 层级 | 样本 | 胜率 | PF | 均笔 | 最大回撤 | 建议 | 过拟合风险 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| classic_retrace | research | 5616 | 51.23% | 1.189 | 0.25% | -28.04% | downgrade_to_factor_or_research_only | medium |
| ma_support | research | 14250 | 38.47% | 1.165 | 0.24% | -24.66% | downgrade_to_factor_or_research_only | medium |
| first_board | production | 8778 | 49.31% | 2.071 | 0.91% | -14.14% | retain_current_layer | medium |
| volume_shrink | production | 3174 | 55.19% | 1.440 | 0.45% | -33.90% | retain_current_layer | medium |
| late_session_strong_support | production | 7027 | 46.58% | 1.171 | 0.23% | -27.63% | retain_current_layer | medium |
| core_midcap_vwap_ma5_retrace | production | 5108 | 36.04% | 1.124 | 0.19% | -26.10% | retain_current_layer | medium |
| sector_mainline_first_divergence_low_buy | production | 867 | 33.07% | 0.870 | -0.20% | -33.96% | pause_or_downgrade | high |
| mainline_limitup_shrink_retrace_reclaim | production | 500 | 25.57% | 0.756 | -0.38% | -57.09% | pause_or_downgrade | high |
| ma_channel_band | research | 4993 | 58.06% | 1.725 | 0.93% | -23.20% | retain_research_or_shadow | medium |
| leader_pullback_band | research | 1954 | 56.62% | 1.428 | 0.50% | -19.65% | retain_research_or_shadow | medium |
| n_pattern_long_wash | production | 1785 | 48.31% | 1.126 | 0.23% | -54.17% | retain_but_reduce_weight_and_add_constraints | medium_high |
| n_pattern_short_wash | production | 1792 | 42.29% | 0.708 | -0.53% | -88.96% | pause_or_downgrade | high |
| breakout_support | research | 4760 | 47.12% | 1.038 | 0.06% | -38.20% | downgrade_to_factor_or_research_only | medium |
| limit_up_breakout_retrace | research | 1978 | 43.77% | 1.013 | 0.02% | -30.24% | downgrade_to_factor_or_research_only | medium |
| divergence_consensus | research | 202 | 41.29% | 0.920 | -0.12% | -50.91% | pause_or_downgrade | high |
| deep_pullback | research | 164 | 67.10% | 1.959 | 0.75% | -21.59% | paper_observe_candidate | medium_high |
| trend_rebound | research | 2609 | 47.34% | 1.066 | 0.10% | -43.03% | downgrade_to_factor_or_research_only | medium |

## 三点五、策略族闭环

- 状态：research_only，策略族 13 个，覆盖策略 17 个；排序影响=none，生产参数变更=不允许。
- 训练/验证/样本外：train=2024Q3, 2024Q4, 2025Q1, 2025Q2, 2025Q3, 2025Q4；validation=2026Q1；oos=2026Q2；证据=time_ordered_quarter_proxy；production_ready=false。
| 策略族 | 策略 | 胜率 | PF | 总收益 | 最大回撤 | 验证状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 突破回踩 | breakout_support, limit_up_breakout_retrace | 46.08% | 1.030 | 12.97% | -38.20% | paper_or_shadow_candidate |
| 主线中军回踩 | core_midcap_vwap_ma5_retrace | 36.04% | 1.124 | 162.88% | -26.10% | paper_or_shadow_candidate |
| 深回撤低吸 | deep_pullback | 67.10% | 1.959 | 63.86% | -21.59% | paper_or_shadow_candidate |
| 首板回踩 | first_board | 49.31% | 2.071 | 2504.92% | -14.14% | paper_or_shadow_candidate |
| 龙头回踩波段 | leader_pullback_band | 56.62% | 1.428 | 425.74% | -19.65% | paper_or_shadow_candidate |
| 右侧主升确认 | divergence_consensus | 41.29% | 0.920 | -28.57% | -50.91% | research_only_weak |
| 主线首分歧 | sector_mainline_first_divergence_low_buy | 33.07% | 0.870 | -12.74% | -33.96% | research_only_weak |
| 主线涨停回调 | mainline_limitup_shrink_retrace_reclaim | 25.57% | 0.756 | -57.09% | -57.09% | research_only_weak |
| N字洗盘回踩 | n_pattern_long_wash, n_pattern_short_wash | 45.29% | 0.916 | -102.23% | -88.96% | research_only_weak |
| 次日兑现模型 | late_session_strong_support | 46.58% | 1.171 | 143.12% | -27.63% | paper_or_shadow_candidate |
| 趋势回调低吸 | classic_retrace, ma_support, volume_shrink | 43.88% | 1.208 | 683.49% | -33.90% | paper_or_shadow_candidate |
| 趋势龙回头 | trend_rebound | 47.34% | 1.066 | 63.29% | -43.03% | paper_or_shadow_candidate |
| 均线通道支撑 | ma_channel_band | 58.06% | 1.725 | 3663.96% | -23.20% | paper_or_shadow_candidate |

## 四、参数审查口径

- 所有策略的 `optimized_parameters.optimized_values_for_production` 均保持等于当前生产默认值。
- `candidate_overrides_for_shadow_or_walk_forward` 只表示可进入 Shadow 或 walk-forward 的候选范围，不代表已优化完成。
- 本轮没有把回测收益直接写入生产参数；候选参数必须先通过时序 walk-forward、purged gap、稳定性和 Shadow。
- `spike_return_*` / `avg_max_gain_5d` 属于未来窗口最高价观察指标，只能判断冲高机会，不能作为可成交收益或生产晋级指标。
- `diagnostic_compound_return_pct` 是逐信号连续复利诊断字段，不是真实账户资金曲线。
- 资金曲线限制：total_return_pct 已改为每日信号等权资金约束口径，但仍未覆盖现金、持仓上限、并发仓位、滑点和排队成交，生产前必须补真实 Paper 账户曲线。

### classic_retrace

- 当前层级：research / research
- 当前建议：downgrade_to_factor_or_research_only
- 治理状态：research_candidate
- 调参建议：{"min_execution_quality_score": {"candidate_value": "+5", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "max_distribution_risk_score": {"candidate_value": "-0.3", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "mapped", "runtime_locations": ["prefilter"]}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=286 filled=259 PF=1.415 MDD=-19.76%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### ma_support

- 当前层级：research / research
- 当前建议：downgrade_to_factor_or_research_only
- 治理状态：research_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=847 filled=757 PF=1.107 MDD=-49.30%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### first_board

- 当前层级：production / core
- 当前建议：retain_current_layer
- 治理状态：positive_expectancy_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=494 filled=448 PF=3.294 MDD=-12.06%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### volume_shrink

- 当前层级：production / core
- 当前建议：retain_current_layer
- 治理状态：positive_expectancy_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：none
- 静态行业归因摘要：通用设备 sample=155 filled=131 PF=0.870 MDD=-47.81%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### late_session_strong_support

- 当前层级：production / auxiliary
- 当前建议：retain_current_layer
- 治理状态：research_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=385 filled=356 PF=1.166 MDD=-23.15%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### core_midcap_vwap_ma5_retrace

- 当前层级：production / auxiliary
- 当前建议：retain_current_layer
- 治理状态：research_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=263 filled=238 PF=1.169 MDD=-36.11%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### sector_mainline_first_divergence_low_buy

- 当前层级：production / auxiliary
- 当前建议：pause_or_downgrade
- 治理状态：weak_strategy
- 调参建议：{"max_holding_days": {"candidate_value": "min(current,3)", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "first_take_profit_pct": {"candidate_value": "3.0-5.0 grid", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：profit_factor_below_1, non_positive_avg_trade_return
- 静态行业归因摘要：汽车零部件 sample=45 filled=37 PF=0.762 MDD=-27.47%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### mainline_limitup_shrink_retrace_reclaim

- 当前层级：production / auxiliary
- 当前建议：pause_or_downgrade
- 治理状态：weak_strategy
- 调参建议：{"max_holding_days": {"candidate_value": "min(current,3)", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "first_take_profit_pct": {"candidate_value": "3.0-5.0 grid", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：profit_factor_below_1, non_positive_avg_trade_return, max_drawdown_over_50pct
- 静态行业归因摘要：汽车零部件 sample=25 filled=25 PF=1.414 MDD=-20.09%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### ma_channel_band

- 当前层级：research / research
- 当前建议：retain_research_or_shadow
- 治理状态：positive_expectancy_candidate
- 调参建议：{"min_execution_quality_score": {"candidate_value": "+5", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "max_distribution_risk_score": {"candidate_value": "-0.3", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "mapped", "runtime_locations": ["prefilter", "execution"]}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=253 filled=234 PF=1.362 MDD=-41.15%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### leader_pullback_band

- 当前层级：research / research
- 当前建议：retain_research_or_shadow
- 治理状态：positive_expectancy_candidate
- 调参建议：{"min_execution_quality_score": {"candidate_value": "+5", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "max_distribution_risk_score": {"candidate_value": "-0.3", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "mapped", "runtime_locations": ["prefilter", "execution"]}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=101 filled=91 PF=2.125 MDD=-15.96%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### n_pattern_long_wash

- 当前层级：production / core
- 当前建议：retain_but_reduce_weight_and_add_constraints
- 治理状态：high_return_high_drawdown
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：max_drawdown_over_50pct
- 静态行业归因摘要：通用设备 sample=84 filled=83 PF=1.038 MDD=-39.52%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### n_pattern_short_wash

- 当前层级：production / core
- 当前建议：pause_or_downgrade
- 治理状态：weak_strategy
- 调参建议：{"max_holding_days": {"candidate_value": "min(current,3)", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "first_take_profit_pct": {"candidate_value": "3.0-5.0 grid", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。
- 过拟合标记：profit_factor_below_1, non_positive_avg_trade_return, max_drawdown_over_50pct
- 静态行业归因摘要：汽车零部件 sample=106 filled=106 PF=0.834 MDD=-36.73%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### breakout_support

- 当前层级：research / research
- 当前建议：downgrade_to_factor_or_research_only
- 治理状态：research_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=277 filled=251 PF=0.985 MDD=-55.63%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### limit_up_breakout_retrace

- 当前层级：research / research
- 当前建议：downgrade_to_factor_or_research_only
- 治理状态：research_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=108 filled=101 PF=1.564 MDD=-16.08%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### divergence_consensus

- 当前层级：research / research
- 当前建议：pause_or_downgrade
- 治理状态：weak_strategy
- 调参建议：{"max_holding_days": {"candidate_value": "min(current,3)", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "first_take_profit_pct": {"candidate_value": "3.0-5.0 grid", "reason": "仅输出建议，不修改生产参数。", "combination_name": "降低持有与止盈等待", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：low_sample_count, profit_factor_below_1, non_positive_avg_trade_return, max_drawdown_over_50pct
- 静态行业归因摘要：汽车零部件 sample=13 filled=13 PF=0.874 MDD=-12.93%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### deep_pullback

- 当前层级：research / factor
- 当前建议：paper_observe_candidate
- 治理状态：positive_expectancy_candidate
- 调参建议：无生产调参；保持当前参数
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：low_sample_count
- 静态行业归因摘要：电网设备 sample=11 filled=11 PF=4.839 MDD=-3.71%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

### trend_rebound

- 当前层级：research / factor
- 当前建议：downgrade_to_factor_or_research_only
- 治理状态：research_candidate
- 调参建议：{"min_execution_quality_score": {"candidate_value": "+5", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}, "max_distribution_risk_score": {"candidate_value": "-0.3", "reason": "仅输出建议，不修改生产参数。", "combination_name": "收紧入场过滤", "status": "shadow_or_walk_forward_only", "runtime_key_status": "not_mapped_to_current_runtime_defaults", "runtime_locations": []}}
- walk-forward：acceptance_plan_ready_not_executed
- walk-forward 验收矩阵：acceptance_plan_ready_not_executed windows=7 purged_gap=10d grid=min_score; max_holding_days; stop_loss_pct; first_take_profit_pct, ...
- purged gap：planned_not_executed_for_strategy_parameter_candidates
- 未来函数风险：low_for_existing_report_generation
- 买入信号诊断：策略处于研究/因子层，强买入口被策略层级暂停。
- 过拟合标记：none
- 静态行业归因摘要：汽车零部件 sample=144 filled=130 PF=1.081 MDD=-40.24%; mapped=100.0%; 不能用当前静态行业字段替代历史行业/概念口径做生产放行。

## 五、新增模型结论

- 主力模型：离线 OOS 字段只能当研究代理指标；线上 Shadow settled 样本为 0，且未完成真实滚动训练/验证/测试切窗，不得直接作为生产下单模型或强制调参依据。
- 主力模型离线指标：{"record_count": 10980, "eligible_count": 3415, "success_rate_pct": 67.789, "profit_factor": 38.1328, "avg_return_20d_pct": 10.2148, "avg_max_adverse_20d_pct": -7.6199, "fallback_rate_pct": 0.0}
- 主力模型 OOS 阻断：true_walk_forward_train_valid_test_not_implemented
- 主力模型 OOS 证据：research_proxy_not_true_train_valid_test_split，main_force_model_backtest.py 目前按全窗口生成启发式标签表现；train/valid/test/purged_gap 参数写入报告，但未形成真实滚动训练验证测试切窗。
- 主力模型 Shadow：{"record_count": 10, "settled_count": 0, "success_rate_pct": 0.0, "profit_factor": 0.0, "fallback_rate_pct": 10.0, "promotion_ready": false, "promotion_blockers": ["shadow_record_count_lt_300", "settled_shadow_count_lt_120"]}
- 退出模型：quick_tp3_trailing1 已通过 7 个 OOS 窗口相对基线验证，可进入下一阶段 Shadow；但线上 settled 样本不足，仍不能写生产，且不能取消、放宽或覆盖硬止损。
- 退出模型样本：record=0 settled=0
- 退出参数 walk-forward：7/7 窗口通过，平均 PF 改善 0.9556，平均回撤改善 15.0326pct，Shadow 候选=是，生产可用=否。
- 止盈止损候选矩阵：quick_tp3_trailing1 暂列 PF 最优，coverage=26.08%，仅 Shadow/完整 walk-forward 复验，不能写生产。
- 市场状态保护候选：block_retreat 已完成 7/7 窗口，通过 2/7，平均 PF 差 -0.0051，平均收益差 -2.6517pct，平均回撤差 1.0627pct；不能写生产。
- P1 核心策略参数窄网格：矩阵窗口 21 个，合并口径通过 7/7；first_board 通过 7/7，volume_shrink 通过 6/7；主要来自 3% 首次止盈与 1% 移动防守提升的冲高兑现，而非放宽持仓收益。 生产可用=否。
- 次日事件模型：当前证据只覆盖相关规则策略和事件型信号表现；没有独立模型的walk-forward、Shadow、漂移报告，不建议接入生产模型链路。

## 六、数据闸门

- daily_24m_coverage：pass，blocking=False，全 A 日线覆盖率必须达到阈值后才能正式回测和参数晋级。
- daily_quality：pass，blocking=False，OHLC、重复 K 线、负成交量/成交额必须通过质量门禁。
- market_metadata_coverage：fail，blocking=True，涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 执行元数据必须通过门禁。
- etf_t0_minute_coverage：fail，blocking=True，ETF T0 必须有分钟线覆盖率，不能用日线代理验收。
- strategy_governance_report：pass，blocking=False，必须能列出所有策略并给出治理状态。
- constraint_policy_coverage：pass，blocking=False，策略必须具备弱市/板块/流动性/ST/涨跌停/连续止损/data_quality 等约束，弱策略和样本不足策略不得晋级。
- walk_forward_readiness：pass，blocking=False，Walk-forward 只允许在两年数据和候选策略足够时启动。
- temporal_no_future_function：pass，blocking=False，禁止未来函数、随机时间序列切分和 Shadow 特征混入 future/next/outcome 字段。
- exit_model_shadow：warn，blocking=False，退出辅助模型必须先积累 Shadow 样本，不能直接进入生产动作。

## 七、GPU / Go / Rust

- GPU：未使用，本轮为规则策略和既有报告聚合，无深度学习/RL/LLM训练；CPU足够。
- Go/Rust：未新增使用，本轮瓶颈在报告 JSON 聚合，平均耗时低于 1 秒，不值得迁移 Go/Rust。
- Profiling：scope=report_generation_and_existing_json_aggregation_only，bottleneck=read_sources 4.829ms
- 既有 Rust parity：covered_by_tests，backend/tests/test_finance_performance_math.py，metrics=max_drawdown, rolling_mean, rolling_std, volatility, correlation, beta, bollinger_bands, ATR Wilder, RSI Wilder, VWAP, RankIC
- 后续可 profile 的 Go/Rust 候选模块：全市场多参数候选网格回测 worker, 大规模分钟线 ETF T0 参数扫描

## 八、未完成项

- 执行候选参数网格的按月滚动 walk-forward、purged gap 和参数稳定性实算。
- P1 first_board/volume_shrink 窄网格已完成；继续补 purged-gap、Shadow settled 样本和剩余重点策略信号闸门。
- 补齐 ETF 24个月分钟级数据、bid/ask spread、溢折价、跟踪指数和流动性分层元数据。
- 让主力模型和退出模型积累线上 Shadow settled 样本后再评估生产晋级。

## 九、测试命令与结果

### 命令

- `PYTHONPATH=. python scripts/generate_strategy_24m_optimization_report.py --date 2026-05-28`
- `DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend backend/.venv/bin/python backend/scripts/strategy_24m_backtest_report.py --json-output /tmp/strategy-24m-full-probe.json --markdown-output /tmp/strategy-24m-full-probe.md`
- `PYTHONPATH=. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_24m_optimization_report.py`
- `PYTHONPATH=. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_backtest_isolation.py -k trade_extremes`

### 结果

- 尚未写入本报告；以执行终端结果为准。

## 十、报告文件

- Markdown：docs/reports/strategy-24m-optimization-report-2026-05-28.md
- JSON：docs/reports/strategy-24m-optimization-report-2026-05-28.json
