from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_backend_perf_budget_script_reports_optional_gate(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.prom"
    metrics.write_text(
        "\n".join(
            [
                "tquant_rust_math_fallback_ratio_bps 0",
                "tquant_local_quote_cache_coverage_ratio_bps 9000",
                "tquant_runtime_task_duration_p95_ms 120000",
                "tquant_response_serialization_ms{route=\"priority_board\"} 12",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_backend_perf_budget.py", "--metrics-file", str(metrics)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["strict"] is False
    assert payload["level"] == "all"
    assert {item["status"] for item in payload["findings"]} == {"ok"}
    assert {item["level"] for item in payload["findings"]} == {"level1", "level2", "level3"}


def test_backend_perf_budget_strict_all_only_blocks_level1(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.prom"
    metrics.write_text(
        "\n".join(
            [
                "tquant_rust_math_fallback_ratio_bps 0",
                "tquant_local_quote_cache_coverage_ratio_bps 100",
                "tquant_runtime_task_duration_p95_ms 900000",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_backend_perf_budget.py", "--metrics-file", str(metrics), "--strict"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert any(item["level"] == "level2" and item["status"] == "exceeded" for item in payload["findings"])
    assert any(item["level"] == "level3" and item["status"] == "exceeded" for item in payload["findings"])


def test_backend_perf_budget_uses_max_labeled_sample_and_ignores_none_placeholder(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.prom"
    metrics.write_text(
        "\n".join(
            [
                'tquant_response_serialization_ms{route="none"} 0',
                'tquant_response_serialization_ms{route="priority_board"} 12',
                'tquant_response_serialization_ms{route="monitor_bff"} 320',
                "tquant_rust_math_fallback_ratio_bps 0",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_backend_perf_budget.py", "--metrics-file", str(metrics), "--level", "level2"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    serialization = next(item for item in payload["findings"] if item["metric"] == "tquant_response_serialization_ms")
    assert serialization["status"] == "exceeded"
    assert serialization["value"] == 320
    assert serialization["sample_count"] == 2


def test_backend_perf_budget_reports_not_measured_for_only_none_placeholder(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.prom"
    metrics.write_text('tquant_response_serialization_ms{route="none"} 0\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/check_backend_perf_budget.py", "--metrics-file", str(metrics), "--level", "level2"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    serialization = next(item for item in payload["findings"] if item["metric"] == "tquant_response_serialization_ms")
    assert serialization["status"] == "not_measured"
