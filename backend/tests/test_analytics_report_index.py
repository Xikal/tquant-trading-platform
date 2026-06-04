from __future__ import annotations

import json

from app.services.analytics.report_index import read_analytics_report_index


def test_read_analytics_report_index_returns_latest_history_with_duration_and_manifest(tmp_path) -> None:
    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True)
    (report_dir / "index.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-06-04T10:02:00Z",
                "reports": [
                    {
                        "report_type": "strategy_24m_duckdb",
                        "generated_at": "2026-06-04T10:00:00Z",
                        "status": "ok",
                        "manifest_id": "daily_bars:daily_bars_20260604100000",
                        "dataset_version": "daily_bars_20260604100000",
                        "duration_seconds": 2.5,
                        "output_md": "/tmp/report.md",
                        "output_json": "/tmp/report.json",
                    },
                    {
                        "report_type": "strategy_24m_duckdb",
                        "generated_at": "2026-06-03T10:00:00Z",
                        "status": "blocked_by_data",
                        "manifest_id": "daily_bars:daily_bars_20260603100000",
                        "dataset_version": "daily_bars_20260603100000",
                        "duration_seconds": 4,
                        "output_md": "/tmp/old.md",
                        "output_json": "/tmp/old.json",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    response = read_analytics_report_index(output_root=tmp_path, limit=1)

    assert response.total == 2
    assert response.updated_at == "2026-06-04T10:02:00Z"
    assert len(response.items) == 1
    assert response.items[0].manifest_id == "daily_bars:daily_bars_20260604100000"
    assert response.items[0].duration_seconds == 2.5
    assert response.items[0].output_json == "/tmp/report.json"
