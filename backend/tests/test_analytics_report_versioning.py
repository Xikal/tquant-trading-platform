from __future__ import annotations

import json

from app.services.analytics.report_queries import write_strategy_24m_report


def test_strategy_report_write_updates_local_report_index(tmp_path) -> None:
    report = {
        "title": "DuckDB 24个月策略分析报告",
        "generated_at": "2026-06-04T10:00:00Z",
        "status": "blocked_by_data",
        "duration_seconds": 1.25,
        "manifest": {
            "manifest_id": "daily_bars:daily_bars_20260604100000",
            "dataset_version": "daily_bars_20260604100000",
            "valid_until": "2026-06-11T10:00:00Z",
            "period_start": "2024-06-04",
            "period_end": "2026-06-04",
            "quality": {"status": "partial"},
        },
        "data_quality_conclusion": "数据不完整，报告仅作分析层预览。",
        "data_quality_sla": {"items": []},
        "data_quality_sla_conclusion": "blocked",
        "live_vs_backtest": {"conclusion": "no_data", "items": []},
        "duckdb_daily_bar_summary": {},
        "strategy_summary_note": "",
        "all_strategies": [],
        "validation_input_gaps": [],
        "strategy_adjustment_recommendations": [],
        "execution_assumptions": [],
        "sensitivity_notes": [],
    }
    output_md = tmp_path / "reports" / "strategy.md"
    output_json = tmp_path / "reports" / "strategy.json"

    write_strategy_24m_report(report, output_md=output_md, output_json=output_json, output_root=tmp_path)

    index_path = tmp_path / "reports" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = index["reports"][0]
    assert entry["report_type"] == "strategy_24m_duckdb"
    assert entry["status"] == "blocked_by_data"
    assert entry["manifest_id"] == "daily_bars:daily_bars_20260604100000"
    assert entry["dataset_version"] == "daily_bars_20260604100000"
    assert entry["duration_seconds"] == 1.25
    assert entry["output_md"] == str(output_md)
    assert entry["output_json"] == str(output_json)


def test_strategy_report_json_preserves_manifest_lifecycle_fields(tmp_path) -> None:
    report = {
        "title": "DuckDB 24个月策略分析报告",
        "generated_at": "2026-06-04T10:00:00Z",
        "status": "ok",
        "manifest": {
            "manifest_id": "daily_bars:daily_bars_20260604100000",
            "dataset_version": "daily_bars_20260604100000",
            "generated_at": "2026-06-04T10:00:00Z",
            "valid_until": "2026-06-11T10:00:00Z",
            "superseded_by": None,
            "status": "active",
            "period_start": "2024-06-04",
            "period_end": "2026-06-04",
            "quality": {"status": "ok"},
        },
        "data_quality_conclusion": "ok",
        "data_quality_sla": {"items": []},
        "data_quality_sla_conclusion": "ok",
        "live_vs_backtest": {"conclusion": "no_data", "items": []},
        "duckdb_daily_bar_summary": {},
        "strategy_summary_note": "",
        "all_strategies": [],
        "validation_input_gaps": [],
        "strategy_adjustment_recommendations": [],
        "execution_assumptions": [],
        "sensitivity_notes": [],
    }
    output_json = tmp_path / "reports" / "strategy.json"

    write_strategy_24m_report(report, output_md=tmp_path / "reports" / "strategy.md", output_json=output_json, output_root=tmp_path)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["manifest"]["manifest_id"] == "daily_bars:daily_bars_20260604100000"
    assert payload["manifest"]["valid_until"] == "2026-06-11T10:00:00Z"
    assert payload["manifest"]["status"] == "active"
