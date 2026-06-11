from __future__ import annotations

import json
from copy import deepcopy

import pytest
from scripts import strategy_success_rate_diagnostics as diagnostics


def _strategy_row(
    key: str,
    *,
    filled_count: int = 10,
    profit_factor: float = 1.2,
    avg_trade_return_pct: float = 0.3,
) -> dict:
    return {
        "strategy_key": key,
        "strategy_title": key,
        "policy_tier": "candidate",
        "sample_count": 20,
        "filled_count": filled_count,
        "win_rate_pct": 55.0,
        "profit_factor": profit_factor,
        "avg_trade_return_pct": avg_trade_return_pct,
        "max_drawdown_pct": -6.0,
        "priority_board_eligible": True,
        "walk_forward": {"passed_window_count": 1, "window_count": 2},
        "oos": {
            "status": "quarter_proxy",
            "filled_count": 4,
            "profit_factor": 1.1,
            "daily_signal_equal_weight_compound_return_pct": 0.8,
        },
        "quarter_breakdown": [{"key": "2026Q2", "filled_count": 4, "profit_factor": 1.1}],
        "market_state_breakdown": [
            {
                "key": "strong",
                "sample_count": 10,
                "filled_count": 6,
                "win_rate_pct": 60.0,
                "profit_factor": profit_factor,
                "avg_trade_return_pct": avg_trade_return_pct,
                "max_drawdown_pct": -4.0,
                "total_return_pct": 2.0,
            }
        ],
        "sector_breakdown": {"production_caveat": "aggregate only"},
        "portfolio_backtests": {
            "single_slot": {
                "capital_model_label": "single_slot",
                "candidate_count": 10,
                "trade_count": filled_count,
                "portfolio_return_pct": 1.5,
                "profit_factor": profit_factor,
                "avg_trade_return_pct": avg_trade_return_pct,
                "max_drawdown_pct": -3.0,
                "base_round_trip_cost_bps": 20,
                "extra_cost_bps": 0,
                "total_cost_bps_assumption": 20,
                "same_symbol_reentry_blocked": True,
                "sector_daily_limit": 1,
                "skipped_by_duplicate_symbol": 1,
                "skipped_by_sector_limit": 2,
                "skipped_by_strategy_daily_limit": 0,
            }
        },
    }


def _source_bundle() -> diagnostics.SourceBundle:
    return {
        "strategy_24m": {
            "status": "ok",
            "manifest": {"window": "24m"},
            "data_quality_conclusion": "fixture",
            "live_vs_backtest": {"status": "fixture"},
            "all_strategies": [
                _strategy_row("first_board", filled_count=12, profit_factor=1.4),
                _strategy_row("volume_shrink", filled_count=8, profit_factor=1.1),
                _strategy_row("late_session_strong_support", filled_count=2, profit_factor=0.8, avg_trade_return_pct=-0.2),
            ],
        },
        "execution_matrix": {
            "scope": {"fixture": True},
            "rows": [
                {
                    "variant_key": "default_exit",
                    "title": "默认退出",
                    "purpose": "fixture",
                    "coverage_status": "complete",
                    "coverage_pct": 100.0,
                    "evaluated_count": 10,
                    "filled_count": 3,
                    "net_win_rate": 66.67,
                    "avg_net_return_pct": 0.4,
                    "execution_profit_factor": 1.3,
                    "max_drawdown_pct": -2.0,
                    "total_return_pct": 1.2,
                    "filled_exit_reason_counts": {"time": 3},
                }
            ],
            "best_by_profit_factor": "default_exit",
            "best_by_avg_net_return": "default_exit",
            "best_by_drawdown": "default_exit",
        },
        "target_execution_matrix": {
            "scope": {"strategies": list(diagnostics.TARGET_STRATEGIES)},
            "rows": [
                {
                    "variant_key": "default_exit",
                    "coverage_status": "complete",
                    "filled_count": 0,
                }
            ],
        },
        "tradability": {
            "minute_coverage": {"coverage_pct": 0.0},
            "tick_coverage": {"coverage_pct": 0.0},
        },
        "n_pattern_observe": {"summary": {"filled_count": 0}},
        "latest_backtest": {
            "strategies": [
                {"strategy_key": "first_board", "avg_max_gain_5d": 2.1, "avg_return_5d": 0.2},
                {"strategy_key": "volume_shrink", "avg_max_gain_5d": 1.7, "avg_return_5d": -0.1},
                {"strategy_key": "late_session_strong_support", "avg_max_gain_5d": 1.2, "avg_return_5d": -0.3},
            ]
        },
        "source_paths": {key: f"fixture/{key}.json" for key in diagnostics.SOURCE_PATHS},
    }


def test_baseline_extracts_target_strategy_metrics_and_guardrails() -> None:
    payload = diagnostics.build_baseline_payload(
        _source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    rows = {row["strategy_key"]: row for row in payload["body"]["target_strategies"]}
    assert set(rows) == {"first_board", "volume_shrink", "late_session_strong_support"}
    assert rows["first_board"]["filled_count"] == 12
    assert rows["volume_shrink"]["profit_factor"] == 1.1
    assert rows["late_session_strong_support"]["walk_forward_summary"] == "1/2 pass"
    assert payload["metric_guardrails"]["production_return_fact_source"] == "portfolio_backtest_metrics"
    assert "avg_max_gain_5d" in payload["metric_guardrails"]["forbidden_promotion_metrics"]


def test_first_board_oos_blocks_tuning_without_full_outcome_rows() -> None:
    payload = diagnostics.build_first_board_oos_payload(
        _source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    diagnosis = payload["body"]["diagnosis"]
    throwback_pool = payload["body"]["throwback_pool"]
    assert payload["status"] == "blocked_by_data"
    assert diagnosis["category"] == "数据不足，阻断调参"
    assert diagnosis["production_tuning_allowed"] is False
    assert throwback_pool["status"] == "blocked_by_data"
    assert throwback_pool["production_tuning_allowed"] is False


def test_intraday_research_marks_partial_coverage_and_preserves_production_set() -> None:
    payload = diagnostics.build_intraday_payload(
        _source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    research = payload["body"]["confirmation_research"]
    assert research["status"] == "partial_minute_coverage"
    assert research["minute_coverage"]["coverage_pct"] == 0.0
    assert research["production_confirmation_collection_changed"] is False
    assert research["volume_shrink_requires_production_confirmation_now"] is False


def test_production_review_is_not_ready_when_required_research_gates_are_blocked() -> None:
    payload = diagnostics.build_production_review_payload(
        _source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    review = payload["body"]["production_review"]
    assert payload["status"] == "not_ready"
    assert review["candidate_to_promote"] is None
    assert review["production_change_allowed"] is False
    assert any("D5" in blocker for blocker in review["blockers"])


def test_generate_selected_report_writes_markdown_and_json(tmp_path) -> None:
    results = diagnostics.generate_reports(
        batch="D0",
        docs_report_dir=tmp_path / "docs",
        data_report_dir=tmp_path / "data",
        sources=_source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    assert len(results) == 1
    result = results[0]
    assert result.markdown_path.exists()
    assert result.json_path.exists()
    stored = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert stored["batch"] == "D0"
    assert "portfolio_backtest_metrics" in stored["metric_guardrails"]["production_return_fact_source"]


def test_exit_variant_report_preserves_empty_target_matrix_as_no_evidence() -> None:
    payload = diagnostics.build_exit_variants_payload(
        _source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    assert payload["body"]["target_strategy_matrix_run"]["status"] == "empty_no_evidence"
    assert payload["body"]["partial_exit_model_decision"]["default_behavior_changed"] is False
    assert payload["body"]["batch_conclusion"]["production_change_allowed"] is False


def test_generate_all_reports_with_explicit_fixture_sources(tmp_path) -> None:
    results = diagnostics.generate_reports(
        batch="ALL",
        docs_report_dir=tmp_path / "docs",
        data_report_dir=tmp_path / "data",
        sources=_source_bundle(),
        git={"branch": "test", "status_short": []},
    )

    assert len(results) == len(diagnostics.REPORT_BUILDERS)
    assert {result.batch for result in results} == set(diagnostics.REPORT_BUILDERS)
    assert all(result.markdown_path.exists() and result.json_path.exists() for result in results)


def test_missing_required_source_artifact_fails_fast(tmp_path) -> None:
    sources = deepcopy(_source_bundle())
    sources["target_execution_matrix"] = {"_missing": True, "_path": "fixture/missing.json"}

    with pytest.raises(FileNotFoundError, match="target_execution_matrix"):
        diagnostics.generate_reports(
            batch="D2",
            docs_report_dir=tmp_path / "docs",
            data_report_dir=tmp_path / "data",
            sources=sources,
            git={"branch": "test", "status_short": []},
        )
