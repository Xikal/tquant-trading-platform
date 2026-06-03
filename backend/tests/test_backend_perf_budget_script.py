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
    assert {item["status"] for item in payload["findings"]} == {"ok"}
