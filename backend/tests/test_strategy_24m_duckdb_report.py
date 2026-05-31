from __future__ import annotations

import json
from datetime import date

from app.services.analytics.report_queries import (
    build_strategy_24m_duckdb_report,
    render_strategy_24m_markdown,
    write_strategy_24m_report,
)


def _strategy(key: str, *, filled: int = 120, pf: float = 1.4, avg: float = 0.42) -> dict:
    return {
        "strategy_key": key,
        "strategy_title": key,
        "sample_count": filled + 5,
        "filled_count": filled,
        "daily_signal_equal_weight_compound_return_pct": 18.2,
        "max_drawdown_pct": -8.5,
        "profit_factor": pf,
        "avg_trade_return_pct": avg,
        "portfolio_backtests": {
            "max_5": {"portfolio_return_pct": 9.8},
            "max_10": {"portfolio_return_pct": 6.3},
        },
        "quarter_breakdown": [
            {
                "key": "2026Q1",
                "sample_count": 60,
                "filled_count": 58,
                "daily_signal_equal_weight_compound_return_pct": 4.5,
                "profit_factor": 1.2,
                "max_drawdown_pct": -2.1,
            },
            {
                "key": "2026Q2",
                "sample_count": 65,
                "filled_count": 62,
                "daily_signal_equal_weight_compound_return_pct": 3.2,
                "profit_factor": 1.1,
                "max_drawdown_pct": -1.7,
            },
        ],
    }


def _manifest() -> dict:
    return {
        "dataset_version": "test",
        "period_start": "2024-06-01",
        "period_end": "2026-05-30",
        "quality": {"status": "ok"},
        "files": [],
    }


def test_strategy_report_uses_daily_equal_return_and_portfolio_columns(tmp_path):
    source = tmp_path / "strategy.json"
    source.write_text(
        _json(
            {
                "all_strategies": [_strategy("first_board")],
                "strategy_family_summary": {
                    "time_series_splits": {
                        "evidence_level": "quarter_breakdown_proxy_not_true_walk_forward",
                        "out_of_sample_quarters": ["2026Q2"],
                        "roles": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    walk = tmp_path / "walk.json"
    walk.write_text(
        _json(
            {
                "strategies": [
                    {
                        "strategy_key": "first_board",
                        "window_count": 7,
                        "passed_window_count": 7,
                        "pass_rate_pct": 100,
                        "windows": [{"current": {"profit_factor": 1.2, "total_return_pct": 3.0, "max_drawdown_pct": -2}}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    params = tmp_path / "params.json"
    params.write_text(_json({"strategies": []}), encoding="utf-8")

    report = build_strategy_24m_duckdb_report(
        _manifest(),
        output_root=tmp_path / "analytics",
        legacy_strategy_report=source,
        focus_walk_forward_report=walk,
        parameter_walk_forward_report=params,
    )
    markdown = render_strategy_24m_markdown(report)

    assert report["status"] == "ok"
    assert "| 策略 | 层级 | 样本 | 成交 | 每日信号等权复利收益 | 真实组合 max5 | 真实组合 max10 |" in markdown
    assert "## Batch B 决策上下文" in markdown
    assert "## Batch C 决策上下文" in markdown
    assert "信号归因" in markdown
    assert "分钟入场质量" in markdown
    assert "事件风险" in markdown
    assert "策略晋级" in markdown
    assert "总收益 |" not in markdown
    assert "strategy_24m" not in markdown
    assert "max5 9.80%" in markdown
    assert report["strategy_adjustment_recommendations"][0]["evidence"]["walk_forward"]["window_count"] == 7


def test_strategy_report_blocks_production_when_walk_forward_missing(tmp_path):
    source = tmp_path / "strategy.json"
    source.write_text(
        _json(
            {
                "all_strategies": [_strategy("first_board")],
                "strategy_family_summary": {
                    "time_series_splits": {
                        "evidence_level": "quarter_breakdown_proxy_not_true_walk_forward",
                        "out_of_sample_quarters": ["2026Q2"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty.json"
    empty.write_text(_json({"strategies": []}), encoding="utf-8")

    report = build_strategy_24m_duckdb_report(
        _manifest(),
        output_root=tmp_path / "analytics",
        legacy_strategy_report=source,
        focus_walk_forward_report=empty,
        parameter_walk_forward_report=empty,
    )

    assert report["status"] == "blocked_by_validation_inputs"
    assert report["validation_input_gaps"][0]["field"] == "walk_forward"


def test_strategy_report_keeps_n_pattern_research_without_production_gap(tmp_path):
    source = tmp_path / "strategy.json"
    source.write_text(
        _json(
            {
                "all_strategies": [_strategy("n_pattern_short_wash", pf=0.72, avg=-0.49)],
                "strategy_family_summary": {
                    "time_series_splits": {
                        "evidence_level": "quarter_breakdown_proxy_not_true_walk_forward",
                        "out_of_sample_quarters": ["2026Q2"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty.json"
    empty.write_text(_json({"strategies": []}), encoding="utf-8")

    report = build_strategy_24m_duckdb_report(
        _manifest(),
        output_root=tmp_path / "analytics",
        legacy_strategy_report=source,
        focus_walk_forward_report=empty,
        parameter_walk_forward_report=empty,
    )

    assert report["status"] == "ok"
    assert report["validation_input_gaps"] == []
    assert report["strategy_adjustment_recommendations"][0]["recommended_action"] == "delete_candidate"


def test_strategy_report_includes_data_quality_sla_and_blocks_on_fail(tmp_path):
    source = tmp_path / "strategy.json"
    source.write_text(
        _json(
            {
                "all_strategies": [_strategy("first_board")],
                "strategy_family_summary": {
                    "time_series_splits": {
                        "evidence_level": "quarter_breakdown_proxy_not_true_walk_forward",
                        "out_of_sample_quarters": ["2026Q2"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty.json"
    empty.write_text(_json({"strategies": []}), encoding="utf-8")

    report = build_strategy_24m_duckdb_report(
        _manifest(),
        output_root=tmp_path / "analytics",
        legacy_strategy_report=source,
        focus_walk_forward_report=empty,
        parameter_walk_forward_report=empty,
        data_quality_sla={
            "items": [
                {
                    "dataset_key": "daily_bars",
                    "scope": "production_universe",
                    "status": "fail",
                    "coverage_pct": 98.7,
                    "missing_days": 3,
                    "invalid_rows": 1,
                    "duplicate_rows": 0,
                    "blockers": ["daily_bars_invalid_ohlc"],
                    "checked_at": "2026-05-30T10:00:00",
                }
            ],
            "latest_repair_audits": [],
        },
    )
    markdown = render_strategy_24m_markdown(report)

    assert report["status"] == "blocked_by_data"
    assert "## 数据质量 SLA" in markdown
    assert "daily_bars_invalid_ohlc" in markdown
    assert "98.70%" in markdown


def test_strategy_report_includes_live_vs_backtest_track_record_segment(tmp_path):
    source = tmp_path / "strategy.json"
    source.write_text(
        _json(
            {
                "all_strategies": [_strategy("first_board")],
                "strategy_family_summary": {
                    "time_series_splits": {
                        "evidence_level": "quarter_breakdown_proxy_not_true_walk_forward",
                        "out_of_sample_quarters": ["2026Q2"],
                        "roles": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    walk = tmp_path / "walk.json"
    walk.write_text(
        _json(
            {
                "strategies": [
                    {
                        "strategy_key": "first_board",
                        "window_count": 7,
                        "passed_window_count": 7,
                        "pass_rate_pct": 100,
                        "windows": [{"current": {"profit_factor": 1.2, "total_return_pct": 3.0, "max_drawdown_pct": -2}}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    params = tmp_path / "params.json"
    params.write_text(_json({"strategies": []}), encoding="utf-8")

    report = build_strategy_24m_duckdb_report(
        _manifest(),
        output_root=tmp_path / "analytics",
        legacy_strategy_report=source,
        focus_walk_forward_report=walk,
        parameter_walk_forward_report=params,
        track_record_drift={
            "items": [
                {
                    "strategy_key": "first_board",
                    "as_of_date": "2026-06-30",
                    "window_days": 60,
                    "sample_settled": 30,
                    "realized_pf": 1.2,
                    "expected_pf": 1.8,
                    "realized_avg": 0.4,
                    "expected_avg": 0.8,
                    "realized_max5": 2.1,
                    "backtest_max5": 4.0,
                    "realized_max10": 3.0,
                    "backtest_max10": 5.0,
                    "tracking_error": -0.4,
                    "decay_pct": -50.0,
                    "drift_flag": "decay_advisory",
                }
            ]
        },
    )
    markdown = render_strategy_24m_markdown(report)

    assert report["status"] == "ok"
    assert "## 真实战绩 vs 回测" in markdown
    assert "decay_advisory" in markdown
    assert "30" in markdown
    assert "真实战绩 vs 回测" in report["live_vs_backtest"]["conclusion"]
    assert "总收益 |" not in markdown


def test_strategy_report_serializes_duckdb_dates(tmp_path):
    source = tmp_path / "strategy.json"
    source.write_text(
        _json(
            {
                "all_strategies": [_strategy("first_board")],
                "strategy_family_summary": {
                    "time_series_splits": {
                        "evidence_level": "quarter_breakdown_proxy_not_true_walk_forward",
                        "out_of_sample_quarters": ["2026Q2"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty.json"
    empty.write_text(_json({"strategies": []}), encoding="utf-8")
    report = build_strategy_24m_duckdb_report(
        {
            **_manifest(),
            "period_start": date(2024, 6, 3),
            "period_end": date(2026, 5, 29),
            "quality": {"status": "ok", "actual_start": date(2024, 6, 3), "actual_end": date(2026, 5, 29)},
        },
        output_root=tmp_path / "analytics",
        legacy_strategy_report=source,
        focus_walk_forward_report=empty,
        parameter_walk_forward_report=empty,
    )
    report["duckdb_daily_bar_summary"] = {
        "min_trade_date": date(2024, 6, 3),
        "max_trade_date": date(2026, 5, 29),
    }

    output_json = tmp_path / "report.json"
    write_strategy_24m_report(report, output_md=tmp_path / "report.md", output_json=output_json)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["manifest"]["period_start"] == "2024-06-03"
    assert payload["manifest"]["quality"]["actual_end"] == "2026-05-29"
    assert payload["duckdb_daily_bar_summary"]["max_trade_date"] == "2026-05-29"


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
