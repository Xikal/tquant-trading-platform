from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_strategy_24m_optimization_report.py"
FOCUS_SCRIPT = ROOT / "scripts" / "focus_strategy_walk_forward_plan.py"
FOCUS_PARAM_SCRIPT = ROOT / "scripts" / "focus_strategy_parameter_walk_forward_summary.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("strategy_24m_optimization_report", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_focus_module():
    spec = importlib.util.spec_from_file_location("focus_strategy_walk_forward_plan", FOCUS_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_focus_param_module():
    spec = importlib.util.spec_from_file_location(
        "focus_strategy_parameter_walk_forward_summary",
        FOCUS_PARAM_SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_report_keeps_candidates_out_of_production():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)

    assert report["executive_conclusion"]["can_connect_to_production_chain"] is False
    assert report["executive_conclusion"]["production_parameter_change_allowed"] is False
    assert report["scope"]["strategy_count"] == 17
    assert report["acceleration"]["gpu_used"] is False
    assert report["acceleration"]["go_rust_acceleration_used"] is False
    assert report["acceleration"]["profile_scope"] == "report_generation_and_existing_json_aggregation_only"
    assert report["acceleration"]["profile_bottleneck_avg_ms"] > 0
    assert report["acceleration"]["existing_rust_parity"]["status"] == "covered_by_tests"
    assert report["performance_profile"]["full_backtest_profiled"] is False
    assert report["strategy_decisions"]["promote_to_production"] == []
    assert report["scope_coverage"]["production_eligible_item_count"] == 0
    assert report["scope_coverage"]["item_count"] >= 8
    assert report["models"]["main_force_model"]["shadow_gate"]["promotion_ready"] is False
    assert report["models"]["exit_model"]["promotion_ready"] is False
    assert report["focus_parameter_walk_forward"]["aggregate_findings"]["production_eligible"] is False
    assert report["focus_parameter_walk_forward"]["scope"]["total_matrix_window_count"] == 21
    assert report["strategy_family_summary"]["family_count"] >= 12
    assert report["strategy_family_summary"]["strategy_count"] == 17
    assert report["strategy_family_summary"]["production_parameter_change_allowed"] is False
    splits = report["strategy_family_summary"]["time_series_splits"]
    assert splits["status"] == "time_ordered_quarter_proxy"
    assert splits["random_split_allowed"] is False
    assert splits["future_data_allowed_in_signal"] is False
    assert splits["production_ready"] is False
    assert splits["train_quarters"]
    assert splits["validation_quarters"]
    assert splits["out_of_sample_quarters"]
    family_by_key = {item["key"]: item for item in report["strategy_family_summary"]["families"]}
    assert family_by_key["trend_support_band"]["title"] == "均线通道支撑"
    assert family_by_key["leader_pullback_band"]["title"] == "龙头回踩波段"
    assert family_by_key["leader_pullback_band"]["shadow_only"] is True
    blocking_keys = {
        gate.get("key") or gate.get("gate")
        for gate in report["executive_conclusion"]["blocking_gates"]
    }
    assert "market_metadata_coverage" in blocking_keys
    assert "etf_t0_minute_coverage" in blocking_keys

    for item in report["strategy_items"]:
        assert item["original_parameters"]
        assert item["optimized_parameters"]["production_config_change_recommended"] is False
        assert (
            item["optimized_parameters"]["optimized_values_for_production"]
            == item["original_parameters"]
        )
        assert item["after_metrics"]["verified_improvement"] is False
        assert item["walk_forward_validation"]["candidate_passed"] is False
        assert item["purged_gap_validation"]["candidate_passed"] is False
        assert item["future_function_risk"]["status"] == "pass"
        if item["policy_layer"] != "production":
            assert item["buy_signal_diagnosis"]["production_buy_signal_ready"] is False


def test_render_markdown_contains_required_sections():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    report["tests"]["results"] = [
        {
            "status": "pass",
            "summary": "PYTHONPATH=. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_24m_optimization_report.py => passed",
        }
    ]
    markdown = module.render_markdown(report)

    assert "# 策略模型与相关策略24个月优化审查报告" in markdown
    assert "是否可接入生产链路：否" in markdown
    assert "## 四、参数审查口径" in markdown
    assert "## 五、新增模型结论" in markdown
    assert "## 七、GPU / Go / Rust" in markdown
    assert "Profiling：scope=report_generation_and_existing_json_aggregation_only" in markdown
    assert "既有 Rust parity" in markdown
    assert "## 二点五、平台策略与模型覆盖清单" in markdown
    assert "## 三点五、策略族闭环" in markdown
    assert "均线通道支撑" in markdown
    assert "龙头回踩波段" in markdown
    assert "排序影响=none" in markdown
    assert "训练/验证/样本外" in markdown
    assert "production_ready=false" in markdown
    assert "ETF T0 分钟级做T" in markdown
    assert "止盈止损辅助模型" in markdown
    assert "不能作为可成交收益或生产晋级指标" in markdown
    assert "不是真实账户资金曲线" in markdown
    assert "静态行业归因摘要" in markdown
    assert "walk-forward 验收矩阵" in markdown
    assert "买入信号诊断" in markdown
    assert "策略处于研究/因子层" in markdown
    assert "P1 核心策略参数窄网格" in markdown
    assert "冲高兑现" in markdown
    assert "pass：PYTHONPATH=. backend/.venv/bin/python -m pytest -q" in markdown
    assert "market_metadata_coverage：fail" in markdown
    assert "None：" not in markdown
    assert "docs/reports/strategy-24m-optimization-report-2026-05-28.md" in markdown


def test_walk_forward_policy_is_time_ordered_and_random_split_forbidden():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    policy = report["walk_forward_policy"]

    assert policy["status"] == "ready"
    assert policy["random_split_allowed"] is False
    assert policy["time_series_split"] == "required_time_ordered_only_no_random_split"
    assert policy["window_count"] > 0
    for window in policy["windows"]:
        assert window["split_order"] == "train_before_validation_before_oos"
        assert window["train_end"] < window["validation_start"]
        assert window["validation_end"] < window["oos_start"]


def test_scope_coverage_records_non_low_buy_surfaces_as_blocked_or_shadow():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    coverage = report["scope_coverage"]
    by_key = {item["key"]: item for item in coverage["items"]}

    expected = {
        "low_buy_daily_24m",
        "etf_t0_minute",
        "sector_etf_t0",
        "smart_t",
        "main_force_observation_model",
        "paper_exit_model",
        "next_day_event_model",
        "backtest_page_presets",
    }
    assert expected <= set(by_key)
    assert all(item["production_eligible"] is False for item in by_key.values())
    assert by_key["etf_t0_minute"]["metrics"]["accepted_symbol_count"] == 0
    assert "etf_t0_24m_minute_coverage_not_accepted" in by_key["etf_t0_minute"]["blockers"]
    assert by_key["paper_exit_model"]["metrics"]["hard_stop_override_allowed"] is False
    assert by_key["main_force_observation_model"]["metrics"]["oos_promotion_ready"] is False
    assert "backtest_page_presets_require_same_walk_forward_governance" in by_key["backtest_page_presets"]["blockers"]


def test_temporal_guard_forbids_future_features_and_direct_param_writes():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)

    assert report["temporal_guard"]["status"] == "pass"
    assert "future" in report["temporal_guard"]["forbidden_feature_keywords"]
    forbidden = report["controlled_parameter_policy"]["forbidden"]
    assert "random_time_series_split" in forbidden
    assert "production_param_write_from_backtest" in forbidden
    assert "hard_stop_cancel_or_loosen" in forbidden
    policy = report["metric_interpretation_policy"]
    assert "spike_return_*" in policy["research_only_metrics"]
    assert "diagnostic_compound_return_pct" in policy["research_only_metrics"]
    assert "paper_account_equity_curve" in policy["production_promotion_metrics"]


def test_purged_gap_and_shadow_gates_block_production_effects():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    main_force = report["models"]["main_force_model"]
    exit_model = report["models"]["exit_model"]

    assert main_force["walk_forward"]["purged_gap_days"] == 10
    assert main_force["temporal_guard"]["status"] == "pass"
    assert main_force["oos_evidence_status"] == "research_proxy_not_true_train_valid_test_split"
    assert "未形成真实滚动训练验证测试切窗" in main_force["oos_evidence_caveat"]
    assert main_force["shadow_gate"]["record_count"] < 300
    assert main_force["shadow_gate"]["settled_count"] == 0
    assert main_force["shadow_gate"]["promotion_ready"] is False
    assert "settled_shadow_count_lt_120" in main_force["shadow_gate"]["promotion_blockers"]
    assert exit_model["shadow_only"] is True
    assert exit_model["hard_stop_override_allowed"] is False
    assert exit_model["promotion_ready"] is False
    assert exit_model["execution_matrix_shadow_evidence"]["shadow_only"] is True
    assert exit_model["execution_matrix_shadow_evidence"]["production_eligible"] is False
    exit_wf = exit_model["walk_forward_shadow_summary"]
    assert exit_wf["status"] == "shadow_candidate"
    assert exit_wf["window_count"] == 7
    assert exit_wf["passed_window_count"] == 7
    assert exit_wf["pass_rate_pct"] == 100.0
    assert exit_wf["shadow_candidate"] is True
    assert exit_wf["production_eligible"] is False
    assert exit_wf["hard_stop_override_allowed"] is False
    assert "online_shadow_settled_sample_lt_required" in exit_wf["promotion_blockers"]
    for item in report["strategy_items"]:
        assert item["purged_gap_validation"]["required_before_production"] is True
        assert item["purged_gap_validation"]["purged_gap_days"] == 10
        assert item["optimized_parameters"]["production_config_change_recommended"] is False


def test_execution_matrix_evidence_is_shadow_only_partial_window():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    evidence = report["exit_parameter_shadow_evidence"]
    best = evidence["best_by_profit_factor"]

    assert evidence["status"] == "partial_window_research_only"
    assert evidence["coverage_pct"] < 90
    assert evidence["production_eligible"] is False
    assert evidence["shadow_only"] is True
    assert "not_recomputed_with_full_24m_walk_forward" in evidence["promotion_blockers"]
    assert best["variant_key"] == "quick_tp3_trailing1"
    assert best["candidate_parameter_changes"] == {
        "first_take_profit_pct": 3.0,
        "trailing_stop_pct": 1.0,
        "max_holding_days": 3,
    }
    assert best["production_parameter_change_allowed"] is False


def test_signal_diagnostics_and_parameter_runtime_mapping_are_explicit():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    by_key = {item["strategy_key"]: item for item in report["strategy_items"]}
    leader = by_key["leader_pullback_band"]
    support = by_key["ma_support"]
    channel = by_key["ma_channel_band"]

    assert leader["buy_signal_diagnosis"]["strong_buy_paused"] is True
    assert leader["buy_signal_diagnosis"]["near_entry_count"] > 0
    assert "strategy_layer_pauses_strong_buy" in leader["buy_signal_diagnosis"]["blockers"]
    assert support["buy_signal_diagnosis"]["confirmed_trade_count"] == 0
    assert "signals_are_observation_or_near_entry_only" in support["buy_signal_diagnosis"]["blockers"]
    assert (
        channel["changed_parameters"]["min_execution_quality_score"]["runtime_key_status"]
        == "not_mapped_to_current_runtime_defaults"
    )
    assert (
        channel["changed_parameters"]["max_distribution_risk_score"]["runtime_key_status"]
        == "mapped"
    )


def test_exit_parameter_walk_forward_evidence_is_shadow_candidate_only():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    evidence = report["exit_parameter_walk_forward"]
    delta = evidence["aggregate_delta"]

    assert evidence["variant_under_test"] == "quick_tp3_trailing1"
    assert evidence["baseline_variant"] == "default_exit"
    assert evidence["window_count"] == 7
    assert evidence["passed_window_count"] == 7
    assert evidence["pass_rate_pct"] == 100.0
    assert evidence["shadow_candidate"] is True
    assert evidence["production_eligible"] is False
    assert evidence["hard_stop_override_allowed"] is False
    assert delta["avg_delta_profit_factor"] > 0
    assert delta["avg_delta_max_drawdown_pct"] > 0
    assert len(evidence["windows"]) == 7
    for window in evidence["windows"]:
        assert window["quick_tp3_trailing1"]["pass_vs_default"] is True


def test_market_state_guard_walk_forward_blocks_production_candidate():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    evidence = report["market_state_guard_walk_forward"]
    delta = evidence["aggregate_delta"]

    assert evidence["parameter_under_test"] == "market_state_switch"
    assert evidence["variant_under_test"] == "block_retreat"
    assert evidence["baseline_variant"] == "current"
    assert evidence["completed_window_count"] == 7
    assert evidence["planned_window_count"] == 7
    assert evidence["passed_window_count"] == 2
    assert evidence["pass_rate_pct"] == 28.5714
    assert evidence["partial_evidence"] is False
    assert evidence["shadow_candidate"] is False
    assert evidence["production_eligible"] is False
    assert delta["avg_delta_profit_factor"] < 0
    assert delta["avg_delta_total_return_pct"] < 0
    assert delta["total_market_guard_count"] == 33
    assert "market_state_guard_walk_forward_partial_windows" not in evidence["promotion_blockers"]
    assert "market_state_guard_not_consistently_better_than_current" in evidence["promotion_blockers"]
    assert sum(
        1 for window in evidence["windows"] if window["block_retreat"]["pass_vs_current"]
    ) == 2


def test_low_sample_strategy_is_not_misclassified_as_high_quality():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)
    by_key = {item["strategy_key"]: item for item in report["strategy_items"]}
    deep_pullback = by_key["deep_pullback"]
    divergence = by_key["divergence_consensus"]

    assert deep_pullback["before_metrics"]["sample_count"] < 300
    assert "low_sample_count" in deep_pullback["overfit_flags"]
    assert deep_pullback["review_recommendation"] == "paper_observe_candidate"
    assert deep_pullback["strategy_key"] not in report["strategy_decisions"]["promote_to_production"]
    assert divergence["review_recommendation"] == "pause_or_downgrade"
    assert divergence["overfit_risk_level"] == "high"


def test_required_but_unavailable_metrics_are_explicitly_reported():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)

    for item in report["strategy_items"]:
        before = item["before_metrics"]
        assert isinstance(before["consecutive_loss_count"], int)
        assert isinstance(before["max_single_loss_pct"], (int, float))
        assert isinstance(before["max_single_gain_pct"], (int, float))
        assert before["in_sample_performance"]["status"].startswith("baseline_quarter_proxy")
        assert before["out_of_sample_performance"]["status"].startswith("latest_quarter_proxy")
        assert item["sector_breakdown"]["status"] == "static_instrument_sector_only"
        assert item["sector_breakdown"]["required_before_production"] is False
        assert item["sector_breakdown"]["mapped_rate_pct"] > 90
        assert item["sector_breakdown"]["rows"]
        assert "consecutive_loss_count" not in item["missing_required_metrics"]
        assert "max_single_loss_pct" not in item["missing_required_metrics"]
        assert "max_single_gain_pct" not in item["missing_required_metrics"]
        assert "sector_breakdown" not in item["missing_required_metrics"]
        assert "candidate_walk_forward_oos_metrics" not in item["missing_required_metrics"]


def test_candidate_walk_forward_acceptance_matrix_is_recorded_but_not_promoted():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)

    assert report["walk_forward_policy"]["window_count"] == 7
    for item in report["strategy_items"]:
        wf = item["walk_forward_validation"]
        assert wf["status"] == "acceptance_plan_ready_not_executed"
        assert wf["window_count"] == 7
        assert len(wf["windows"]) == 7
        assert wf["purged_gap_days"] == 10
        assert wf["purged_gap_passed"] is False
        assert wf["candidate_passed"] is False
        assert wf["production_eligible"] is False
        assert wf["shadow_only"] is True
        assert wf["random_split_allowed"] is False
        assert wf["parameter_grid"]
        assert wf["oos_metrics"]["status"] == "not_executed"
        assert "candidate_grid_not_recomputed_on_24m_windows" in wf["promotion_blockers"]
        assert "purged_gap_not_executed_for_candidate_grid" in wf["promotion_blockers"]


def test_report_records_trade_extremes_after_source_json_refresh():
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)

    assert not any("逐笔连续亏损和最大单笔盈亏指标代码已补齐" in item for item in report["unfinished_items"])
    assert not any("补充策略按板块/行业" in item for item in report["unfinished_items"])
    assert not any("补齐候选参数 walk-forward/purged gap 验收矩阵" in item for item in report["unfinished_items"])
    assert any("P1 first_board/volume_shrink 窄网格已完成" in item for item in report["unfinished_items"])
    assert any("执行候选参数网格" in item for item in report["unfinished_items"])
    assert any("trade_extremes" in command for command in report["tests"]["planned_commands"])


def test_focus_strategy_walk_forward_plan_reuses_existing_oos_evidence_only():
    module = _load_focus_module()

    report = module.build_report(ROOT)

    assert report["scope"]["new_backtest_started"] is False
    assert report["scope"]["window_count"] == 7
    assert report["rules"]["no_production_param_write"] is True
    assert report["rules"]["random_split_allowed"] is False
    assert report["rules"]["purged_gap_days"] == 10
    assert report["next_execution_order"][0] in {"first_board", "volume_shrink"}
    by_key = {item["strategy_key"]: item for item in report["strategies"]}
    assert set(by_key) == set(module.FOCUS_STRATEGIES)
    assert by_key["first_board"]["windows_with_confirmed_trades"] == 7
    assert by_key["leader_pullback_band"]["execution_priority"] == "shadow_signal_gate_first"
    assert by_key["leader_pullback_band"]["production_eligible"] is False


def test_focus_strategy_parameter_walk_forward_summary_is_shadow_only():
    module = _load_focus_param_module()

    report = module.build_summary(report_date="2026-05-28", root=ROOT)
    findings = report["aggregate_findings"]

    assert report["scope"]["total_matrix_window_count"] == 21
    assert report["rules"]["no_production_param_write"] is True
    assert report["rules"]["random_split_allowed"] is False
    assert findings["production_eligible"] is False
    assert findings["shadow_candidate"] is False
    assert findings["combined_passed_all_windows"] is True
    assert findings["combined_result_masks_strategy_instability"] is True
    assert findings["strategy_pass_counts"] == {"first_board": 7, "volume_shrink": 6}
    assert findings["strategy_specific_shadow_candidates"] == ["first_board"]
    assert findings["research_only_or_retest"] == ["volume_shrink"]
    assert "冲高兑现" in findings["profit_mechanism"]
    assert "strategy_specific_window_not_all_passed" in report["promotion_blockers"]
    assert report["combined"]["passed_window_count"] == 7
    by_key = {item["scope_key"]: item for item in report["strategies"]}
    assert by_key["first_board"]["passed_window_count"] == 7
    assert by_key["volume_shrink"]["passed_window_count"] == 6
    assert by_key["volume_shrink"]["production_eligible"] is False
