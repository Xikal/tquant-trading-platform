# 策略体系最小生产闭环验收报告

- 生成时间：2026-05-29T09:46:32
- 验收状态：readonly_shadow_loop_complete_production_blocked
- 最小只读/Shadow 闭环：完成
- 真实交易生产放行：否
- 完成度：100.0%

## 检查项

| 检查 | 状态 | 结论 |
|---|---|---|
| 策略族归类 | pass | 17 个低吸策略已归入 13 个策略族，旧 items 接口保持兼容。 |
| 主力观测模型旁路 | pass | 主力模型已只读/Shadow 接入候选与模拟盘展示，默认不加排序权重、不出自动小仓建议。 |
| 老鸭头结构因子 | pass | 老鸭头保持结构因子，不新增独立策略入口，只给适用低吸/N 字策略加分。 |
| 止盈止损辅助模型 | pass | 退出模型已接入模拟盘 Shadow 记录与只读展示，不自动执行，不覆盖硬止损。 |
| 策略族回测与调参闭环 | pass | 策略族维度已输出参数建议、胜率、收益率、最大回撤和盈亏比，但只作为研究报告。 |
| 防未来函数与过拟合门禁 | pass | 报告已区分训练/验证/样本外季度代理，禁止随机切分；真实 walk-forward 仍未完成。 |
| 需求源与验收边界 | pass | 需求文档已补齐，并明确最小只读/Shadow 闭环与真实交易生产放行门禁的边界。 |
| 局部 walk-forward 证据 | pass | 已接入 P1 窄网格、退出参数和市场状态 guard 的 OOS 窗口证据；仍只允许 Shadow/研究观察。 |
| 前端策略族高密度展示 | pass | 策略族概览保持高密度，详情进入只读弹窗，并展示 data_quality/fallback/缺失数据提示。 |
| 不影响排序与交易执行 | pass | 默认不改变原有策略排序、不写生产参数、不触发真实交易执行。 |

## 策略族 walk-forward 证据映射

| 策略族 | 策略 | 证据来源 | 生产放行 | 主要缺口 |
|---|---|---|---|---|
| 主线中军回踩 | core_midcap_vwap_ma5_retrace | focus_walk_forward_plan | 否 | true_strategy_family_walk_forward_not_executed, purged_gap_not_executed, online_shadow_settled_sample_lt_required |
| 首板回踩 | first_board | focus_parameter_walk_forward, focus_walk_forward_plan | 否 | true_strategy_family_walk_forward_not_executed, purged_gap_not_executed, online_shadow_settled_sample_lt_required |
| 龙头回踩波段 | leader_pullback_band | focus_walk_forward_plan | 否 | true_strategy_family_walk_forward_not_executed, purged_gap_not_executed, online_shadow_settled_sample_lt_required |
| 次日兑现模型 | late_session_strong_support | focus_walk_forward_plan | 否 | true_strategy_family_walk_forward_not_executed, purged_gap_not_executed, online_shadow_settled_sample_lt_required |
| 趋势回调低吸 | volume_shrink | focus_parameter_walk_forward, focus_walk_forward_plan | 否 | true_strategy_family_walk_forward_not_executed, purged_gap_not_executed, online_shadow_settled_sample_lt_required |
| 均线通道支撑 | ma_channel_band | focus_walk_forward_plan | 否 | true_strategy_family_walk_forward_not_executed, purged_gap_not_executed, online_shadow_settled_sample_lt_required |

## 目标逐项审计

- 审计状态：minimal_readonly_loop_complete_production_blocked
- 最小只读闭环完成度：100.0%
- 真实交易生产放行：否

| ID | 要求 | 状态 | 证据 |
|---|---|---|---|
| P0-1 | 建立策略族元数据与归类能力 | complete | strategy_family_classification |
| P0-2 | 前端按策略族收敛展示并保持旧接口兼容 | complete | frontend_family_dense_display |
| P1-1 | 主力结构识别模型旁路接入候选结果 | complete | main_force_readonly_shadow |
| P1-2 | 老鸭头结构作为因子接入，不新增重复策略 | complete | old_duck_head_factorized |
| P1-3 | 止盈止损建议接入模拟盘只读展示 | complete | paper_exit_model_readonly_shadow |
| P1-4 | 增加 Shadow 记录或可观测日志 | complete | main_force_readonly_shadow,paper_exit_model_readonly_shadow |
| P2-1 | 补充策略族维度回测入口和简洁报告 | complete | strategy_family_backtest_loop |
| P2-2 | 输出参数变化、胜率、收益、回撤、盈亏比 | complete | strategy_family_backtest_loop |
| P2-3 | 增加防未来函数和样本外验证检查 | complete | anti_future_overfit_guard |
| P3-1 | 前端高密度展示，详情进入折叠或弹窗 | complete | frontend_family_dense_display |
| P3-2 | 补充 data_quality、fallback、缺失数据提示 | complete | frontend_family_dense_display |
| G-1 | 主力、老鸭头、止盈止损保持旁路/Shadow/只读 | complete | main_force_readonly_shadow,old_duck_head_factorized,paper_exit_model_readonly_shadow |
| G-2 | 默认不影响原有策略排序或交易执行 | complete | no_ranking_or_trade_execution_effect |
| G-3 | 回测调参使用已有数据并标记缺口 | complete | walk_forward_evidence_snapshot |
| G-4 | 单文件尽量不超过 500 行 | complete | wc -l targeted files |
| G-5 | 需求源文档存在并纳入验收边界 | complete | requirements_source_document |
| D-1 | 最终交付字段已明确输出 | complete | final_status |
| D-2 | 真实交易生产放行 | blocked | production_trade_ready |

## 测试覆盖矩阵

- 覆盖状态：covered
- 覆盖项：6 / 6

| 覆盖点 | 状态 | 测试文件 | 关键测试 |
|---|---|---|---|
| 策略归类 | covered | backend/tests/test_priority_weighting.py | test_all_low_buy_strategies_have_explicit_family_metadata |
| 旁路信号 | covered | backend/tests/test_main_force_model_enrichment.py | test_enrichment_adds_readonly_advice_without_mutating_candidate, test_enrichment_blocks_risk_candidate_but_keeps_original_signal |
| 止盈止损建议 | covered | backend/tests/test_paper_exit_model_advisor.py | test_exit_model_advisor_never_overrides_hard_stop, test_exit_model_advisor_enforces_rule_floor |
| 模拟盘展示/快照 | covered | backend/tests/test_paper_exit_model_shadow.py | test_exit_model_shadow_records_are_upserted_by_as_of_trade_date, test_exit_model_shadow_latest_and_summary_include_fallback_and_sell_flying |
| 回测指标输出 | covered | backend/tests/test_strategy_24m_report_sections.py | test_strategy_family_summary_is_research_only_and_contains_parameter_changes |
| 前端高密度展示 | covered | frontend/src/features/workspace-shared/FamilyStrip.test.tsx | renders compact family tiles with data quality hints |

## 生产放行动作计划

- 状态：blocked_by_production_gates
- 动作数：6
- 需要外部数据的动作数：1

| 动作 | 外部数据 | 预计耗时 | 阻断项 | 下一步命令 |
|---|---|---|---|---|
| 补齐 ETF T0 分钟线与执行元数据 | 是 | 1-3 天，取决于 Tushare/交易所/供应商分钟线可用性 | etf_t0_minute_coverage, market_metadata_coverage | TUSHARE_TOKEN=... PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope t0-etf --period 5m --allow-partial |
| 积累退出模型 Shadow settled 样本 | 否 | 至少 1-2 周模拟盘持仓观察 | full_strategy_parameter_grid_not_executed, hard_stop_must_not_be_removed_or_loosened, online_shadow_settled_sample_lt_required, settled_shadow_count_lt_30, shadow_record_count_lt_30 | PYTHONPATH=backend:. backend/.venv/bin/python research/scripts/evaluate_exit_model_shadow.py |
| 补全重点策略参数稳定性与 Shadow 验证 | 否 | 0.5-1 天，若只复用既有矩阵；更久取决于新增参数网格 | online_shadow_settled_sample_lt_required, production_param_write_from_backtest_forbidden, purged_gap_candidate_grid_not_executed, strategy_specific_window_not_all_passed | PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_parameter_walk_forward_summary.py --date 2026-05-28 |
| 积累主力模型线上 Shadow settled 样本 | 否 | 至少 2-4 周自然交易日观察 | profit_factor_below_threshold, settled_shadow_count_lt_120, shadow_record_count_lt_300, success_rate_below_threshold | PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/main_force_shadow_warmup.py --date 2026-05-28 |
| 重测市场状态保护参数稳定性 | 否 | 0.5 天 | market_state_guard_not_consistently_better_than_current, production_param_write_from_backtest_forbidden | PYTHONPATH=backend:. backend/.venv/bin/python scripts/market_state_guard_walk_forward_summary.py --date 2026-05-28 |
| 补齐策略族真实 walk-forward 与 purged-gap | 否 | 0.5-1 天，基于现有 24M 日线与已落盘矩阵 | purged_gap_not_executed, settled_shadow_sample_gate_not_passed, true_walk_forward_not_executed | PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_24m_walk_forward_matrix.py --date 2026-05-28 --purged-gap-days 10 |

## 生产阻断

- optimization_gate：market_metadata_coverage，涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 执行元数据必须通过门禁。
- optimization_gate：etf_t0_minute_coverage，ETF T0 必须有分钟线覆盖率，不能用日线代理验收。
- strategy_family_split：true_walk_forward_not_executed，策略族仍未完成真实生产晋级验证。
- strategy_family_split：purged_gap_not_executed，策略族仍未完成真实生产晋级验证。
- strategy_family_split：settled_shadow_sample_gate_not_passed，策略族仍未完成真实生产晋级验证。
- main_force_shadow：shadow_record_count_lt_300，主力模型 Shadow 样本或效果未达标。
- main_force_shadow：settled_shadow_count_lt_120，主力模型 Shadow 样本或效果未达标。
- main_force_shadow：success_rate_below_threshold，主力模型 Shadow 样本或效果未达标。
- main_force_shadow：profit_factor_below_threshold，主力模型 Shadow 样本或效果未达标。
- exit_model_shadow：shadow_record_count_lt_30，止盈止损辅助模型 Shadow 样本未达标。
- exit_model_shadow：settled_shadow_count_lt_30，止盈止损辅助模型 Shadow 样本未达标。
- focus_parameter_walk_forward：production_param_write_from_backtest_forbidden，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- focus_parameter_walk_forward：purged_gap_candidate_grid_not_executed，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- focus_parameter_walk_forward：online_shadow_settled_sample_lt_required，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- focus_parameter_walk_forward：strategy_specific_window_not_all_passed，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- market_state_guard_walk_forward：production_param_write_from_backtest_forbidden，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- market_state_guard_walk_forward：market_state_guard_not_consistently_better_than_current，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- exit_parameter_walk_forward：online_shadow_settled_sample_lt_required，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- exit_parameter_walk_forward：full_strategy_parameter_grid_not_executed，已有局部 OOS 证据，但仍未满足生产晋级门禁。
- exit_parameter_walk_forward：hard_stop_must_not_be_removed_or_loosened，已有局部 OOS 证据，但仍未满足生产晋级门禁。

## 最终状态

- 策略是否已完成归类：是
- 主力观测模型是否已投入旁路生产使用：是
- 老鸭头是否仍保持因子化：是
- 止盈止损辅助模型是否已接入模拟盘：是
- 是否影响原有策略排序或交易执行：否
- 说明：策略体系已形成只读/Shadow 最小闭环；真实交易生产放行仍被数据、walk-forward、purged-gap 与 Shadow settled 样本门禁阻断。
