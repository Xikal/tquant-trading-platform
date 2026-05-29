from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "strategy_system_acceptance_report.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("strategy_system_acceptance_report", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strategy_system_acceptance_report_proves_readonly_loop_but_blocks_production() -> None:
    module = _load_module()

    report = module.build_report(report_date="2026-05-28", root=ROOT)

    assert report["overall_status"] == "readonly_shadow_loop_complete_production_blocked"
    assert report["minimal_readonly_loop_complete"] is True
    assert report["production_trade_ready"] is False
    assert report["completion_pct"] == 100.0
    assert all(item["complete"] for item in report["checks"])
    checks_by_key = {item["key"]: item for item in report["checks"]}
    assert checks_by_key["requirements_source_document"]["complete"] is True
    assert report["source_files"]["requirements_plan"] == "docs/strategy-system-consolidation-and-enhancement-development-plan.md"
    assert len(report["production_blockers"]) >= 4
    final = report["final_status"]
    assert final["strategy_classified"] is True
    assert final["main_force_side_channel_in_use"] is True
    assert final["old_duck_head_factorized"] is True
    assert final["exit_model_connected_to_paper"] is True
    assert final["original_ranking_or_trade_execution_affected"] is False

    by_key = {item["key"]: item for item in report["checks"]}
    assert by_key["main_force_readonly_shadow"]["evidence"]["ranking_enabled_default"] is False
    assert by_key["old_duck_head_factorized"]["evidence"]["standalone_strategy_registered"] is False
    assert by_key["paper_exit_model_readonly_shadow"]["evidence"]["hard_stop_override_allowed"] is False
    assert by_key["anti_future_overfit_guard"]["evidence"]["train_quarters"]
    assert by_key["anti_future_overfit_guard"]["evidence"]["validation_quarters"]
    assert by_key["anti_future_overfit_guard"]["evidence"]["out_of_sample_quarters"]
    walk_forward = by_key["walk_forward_evidence_snapshot"]["evidence"]
    assert walk_forward["focus_parameter_scope"]["total_matrix_window_count"] == 21
    assert walk_forward["focus_parameter_findings"]["production_eligible"] is False
    assert walk_forward["exit_parameter"]["shadow_candidate"] is True
    assert walk_forward["exit_parameter"]["production_eligible"] is False
    assert walk_forward["market_state_guard"]["production_eligible"] is False
    purged_gap = walk_forward["purged_gap_audit"]
    assert purged_gap["status"] == "partial_oos_evidence_purged_gap_not_proven"
    assert purged_gap["total_matrix_window_count"] == 21
    assert purged_gap["temporal_order_passed"] is True
    assert purged_gap["explicit_train_validation_split_present"] is True
    assert purged_gap["explicit_purged_gap_encoded"] is True
    assert purged_gap["proposed_split_plan_present"] is True
    assert purged_gap["purged_gap_plan_ready"] is True
    assert purged_gap["purged_gap_passed"] is False
    assert "execution_matrix_coverage_partial_only" in purged_gap["production_blockers"]
    assert "purged_gap_not_encoded_in_source_matrices" not in purged_gap["production_blockers"]
    assert purged_gap["daily_data_status"] == "covered"
    assert purged_gap["daily_data_total_trade_dates"] == 466
    assert purged_gap["daily_data_first_trade_date"] == "2024-05-28"
    assert purged_gap["daily_data_last_trade_date"] == "2026-04-28"
    assert purged_gap["daily_data_manifest_window_count"] == 21
    assert purged_gap["daily_data_covered_window_count"] == 21
    assert purged_gap["daily_data_min_window_trade_dates"] >= 50
    assert purged_gap["rerun_manifest_status"] == "executed_complete"
    assert purged_gap["rerun_command_count"] == 21
    assert purged_gap["rerun_manifest_database_url"] == "sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db"
    assert purged_gap["rerun_smoke_status"] == "executed_with_samples"
    assert purged_gap["rerun_smoke_matrix_count"] == 1
    assert purged_gap["rerun_smoke_output_structure_passed"] is True
    assert purged_gap["rerun_smoke_data_sample_available"] is True
    assert purged_gap["rerun_smoke_partial_coverage_only"] is True
    assert purged_gap["rerun_smoke_total_evaluated_count"] == 576
    assert purged_gap["rerun_smoke_total_filled_count"] == 554
    assert purged_gap["rerun_full_status"] == "executed_complete"
    assert purged_gap["rerun_full_complete"] is True
    assert purged_gap["rerun_full_matrix_count"] == 21
    assert purged_gap["rerun_full_failed_count"] == 0
    assert purged_gap["rerun_full_total_evaluated_count"] == 6336
    assert purged_gap["rerun_full_total_filled_count"] == 5964
    assert purged_gap["rerun_full_partial_coverage_only"] is True
    family_evidence = walk_forward["family_evidence"]
    assert family_evidence["status"] == "partial_evidence_only"
    assert family_evidence["production_ready"] is False
    assert family_evidence["covered_family_count"] >= 6
    families = {item["family_key"]: item for item in family_evidence["families"]}
    assert families["first_board_retest"]["strategy_keys"] == ["first_board"]
    assert "focus_parameter_walk_forward" in families["first_board_retest"]["evidence_sources"]
    assert families["first_board_retest"]["strategy_specific_shadow_candidate"] is True
    assert "volume_shrink" in families["trend_pullback"]["strategy_keys"]
    assert families["trend_pullback"]["research_only_or_retest"] == ["volume_shrink"]
    assert families["trend_support_band"]["strategy_keys"] == ["ma_channel_band"]
    assert families["leader_pullback_band"]["strategy_keys"] == ["leader_pullback_band"]
    assert all(item["production_ready"] is False for item in families.values())
    assert "strategy_parameter_windows_not_executed" in families["trend_support_band"]["missing_for_production"]

    audit = report["requirement_audit"]
    assert audit["status"] == "minimal_readonly_loop_complete_production_blocked"
    assert audit["minimal_loop_completion_pct"] == 100.0
    assert audit["production_trade_ready"] is False
    audit_items = {item["id"]: item for item in audit["items"]}
    assert audit_items["P0-1"]["status"] == "complete"
    assert audit_items["P1-4"]["status"] == "complete"
    assert audit_items["P2-3"]["status"] == "complete"
    assert audit_items["G-2"]["status"] == "complete"
    assert audit_items["G-5"]["status"] == "complete"
    assert audit_items["D-2"]["status"] == "blocked"
    assert audit_items["D-2"]["required_for_minimal_loop"] is False

    coverage = report["test_coverage_matrix"]
    assert coverage["status"] == "covered"
    assert coverage["covered_count"] == coverage["required_count"]
    coverage_rows = {item["key"]: item for item in coverage["rows"]}
    assert coverage_rows["strategy_family_classification"]["status"] == "covered"
    assert coverage_rows["main_force_readonly_side_channel"]["status"] == "covered"
    assert coverage_rows["exit_model_readonly_advice"]["status"] == "covered"
    assert coverage_rows["paper_shadow_snapshot"]["status"] == "covered"
    assert coverage_rows["strategy_family_backtest_metrics"]["status"] == "covered"
    assert coverage_rows["frontend_family_display"]["status"] == "covered"

    plan = report["promotion_action_plan"]
    assert plan["status"] == "blocked_by_production_gates"
    assert plan["requires_external_data_count"] >= 1
    action_rows = {item["key"]: item for item in plan["actions"]}
    assert action_rows["data_gate"]["requires_external_data"] is True
    assert "backfill_etf_minute_history.py" in " ".join(action_rows["data_gate"]["next_commands"])
    assert "strategy_family_walk_forward" in action_rows
    assert "main_force_shadow" in action_rows
    assert "exit_model_shadow" in action_rows
    assert "focus_parameter" in action_rows
    assert "market_state_guard" in action_rows


def test_strategy_system_acceptance_markdown_contains_final_status() -> None:
    module = _load_module()

    markdown = module.render_markdown(module.build_report(report_date="2026-05-28", root=ROOT))

    assert "# 策略体系最小生产闭环验收报告" in markdown
    assert "最小只读/Shadow 闭环：完成" in markdown
    assert "真实交易生产放行：否" in markdown
    assert "策略是否已完成归类：是" in markdown
    assert "主力观测模型是否已投入旁路生产使用：是" in markdown
    assert "老鸭头是否仍保持因子化：是" in markdown
    assert "止盈止损辅助模型是否已接入模拟盘：是" in markdown
    assert "是否影响原有策略排序或交易执行：否" in markdown
    assert "局部 walk-forward 证据" in markdown
    assert "## 目标逐项审计" in markdown
    assert "## 测试覆盖矩阵" in markdown
    assert "## 生产放行动作计划" in markdown
    assert "需求源与验收边界" in markdown
    assert "真实交易生产放行：否" in markdown
