from __future__ import annotations

import json
import re
from argparse import Namespace
from pathlib import Path

from scripts import full_regression_runner
from scripts import warning_budget


def _args(**overrides):
    values = {
        "profile": "full",
        "report_dir": ".runtime/test-full-regression",
        "only": [],
        "skip": [],
        "fail_fast": False,
        "frontend_port": 4173,
        "cloud_verify": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_full_regression_runner_covers_required_dimensions() -> None:
    steps = full_regression_runner.select_steps(full_regression_runner.build_steps(_args()), _args(profile="full"))
    dimensions = {dimension for step in steps for dimension in step.dimensions}

    for dimension in (
        "backend_api",
        "strategy_logic",
        "risk",
        "paper",
        "backtest",
        "ml",
        "security",
        "persistence",
        "frontend",
        "ui",
        "mobile",
        "usability",
        "go",
        "rust",
        "performance",
            "production_path",
            "observability",
            "warning_budget",
        ):
        assert dimension in dimensions


def test_full_regression_runner_includes_warning_budget_gate() -> None:
    steps = full_regression_runner.select_steps(full_regression_runner.build_steps(_args()), _args(profile="core"))
    step_by_id = {step.step_id: step for step in steps}

    assert "warning_budget" in step_by_id
    assert "observability" in step_by_id["warning_budget"].dimensions
    assert "warning_budget" in step_by_id["warning_budget"].dimensions


def test_release_profile_can_include_cloud_verify_explicitly() -> None:
    args = _args(profile="release", cloud_verify=True)
    steps = full_regression_runner.select_steps(full_regression_runner.build_steps(args), args)
    step_ids = {step.step_id for step in steps}

    assert "prod_preflight" in step_ids
    assert "cloud_verify" in step_ids


def test_secret_redaction_masks_sensitive_values() -> None:
    text = "AUTH_SECRET_KEY=abc123\nAuthorization: Bearer token-value\npassword: plain"

    redacted = full_regression_runner.redact(text)

    assert "abc123" not in redacted
    assert "token-value" not in redacted
    assert "plain" not in redacted
    assert redacted.count("<redacted>") == 3


def test_report_markdown_contains_step_evidence() -> None:
    result = full_regression_runner.StepResult(
        step_id="sample",
        name="Sample",
        profile="core",
        dimensions=["backend"],
        command="pytest backend/tests",
        cwd="/tmp",
        ok=True,
        skipped=False,
        exit_code=0,
        elapsed_ms=12,
        output_tail="ok",
    )
    report = full_regression_runner.build_report(_args(profile="core"), [result], 0)
    markdown = full_regression_runner.render_markdown(report)

    assert "PASS sample" in markdown
    assert "`pytest backend/tests`" in markdown
    assert "Coverage Dimensions" in markdown


def test_warning_budget_parses_and_rejects_unexpected_warnings() -> None:
    stdout = """
=============================== warnings summary ===============================
backend/.venv/lib/python3.9/site-packages/urllib3/__init__.py:35
  /Users/j/Documents/gupiao/backend/.venv/lib/python3.9/site-packages/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'.
backend/tests/test_example.py::test_case
  /Users/j/Documents/gupiao/backend/.venv/lib/python3.9/site-packages/numpy/lib/_function_base_impl.py:2922: 10 warnings
  /Users/j/Documents/gupiao/backend/app/service.py:10: RuntimeWarning: invalid value encountered in matmul
"""
    warnings = warning_budget.warnings_from_pytest_output(stdout)
    budget = warning_budget.evaluate_budget(warnings)

    assert len(warnings) == 2
    assert warnings[1]["count"] == 10
    assert budget["allowed_warning_count"] == 1
    assert budget["unexpected_warning_count"] == 10
    assert budget["violations"][0]["type"] == "unexpected_warning"


def test_warning_budget_allows_documented_libressl_environment_warning() -> None:
    warnings = [
        {
            "category": "NotOpenSSLWarning",
            "message": "urllib3 v2 only supports OpenSSL 1.1.1+",
            "filename": "/Users/j/Documents/gupiao/backend/.venv/lib/python3.9/site-packages/urllib3/__init__.py",
            "lineno": 35,
        }
    ]
    budget = warning_budget.evaluate_budget(warnings)

    assert budget["allowed_warning_count"] == 1
    assert budget["violations"] == []


def test_warning_budget_allows_documented_upstream_import_warnings() -> None:
    warnings = [
        {
            "category": "StarletteDeprecationWarning",
            "message": "Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.",
            "filename": "/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/site-packages/fastapi/testclient.py",
            "lineno": 1,
        },
        {
            "category": "DeprecationWarning",
            "message": "pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html",
            "filename": "/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/site-packages/py_mini_racer/py_mini_racer.py",
            "lineno": 15,
        },
    ]
    budget = warning_budget.evaluate_budget(warnings)

    assert budget["allowed_warning_count"] == 2
    assert budget["violations"] == []


def test_warning_budget_fails_when_allowance_count_is_exceeded() -> None:
    warnings = [
        {
            "category": "NotOpenSSLWarning",
            "message": "urllib3 v2 only supports OpenSSL 1.1.1+",
            "filename": "/Users/j/Documents/gupiao/backend/.venv/lib/python3.9/site-packages/urllib3/__init__.py",
            "lineno": 35,
            "count": 2,
        }
    ]
    budget = warning_budget.evaluate_budget(warnings)

    assert budget["allowed_warning_count"] == 2
    assert budget["violations"][0]["type"] == "allowance_exceeded"


def test_responsive_smoke_covers_all_workspace_routes() -> None:
    script = Path(__file__).resolve().parents[2] / "frontend" / "scripts" / "smoke-responsive.mjs"
    source = script.read_text(encoding="utf-8")
    match = re.search(r"const paths = (?P<paths>\[[^\]]+\]);", source)
    assert match, "responsive smoke path list missing"
    paths = json.loads(match.group("paths").replace("'", '"'))

    assert paths == [
        "/monitor",
        "/emotion",
        "/analysis",
        "/playbook",
        "/strategy-tracking",
        "/strategy",
        "/backtest",
        "/paper",
        "/data",
        "/settings",
    ]
    assert "visible_text_length" in source
    assert "main_region_count" in source


def test_app_api_smoke_sets_hardened_auth_environment() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "app_api_smoke.sh"
    source = script.read_text(encoding="utf-8")

    assert "AUTH_SECRET_KEY=" in source
    assert "ADMIN_API_TOKEN=" in source
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED=false" in source
    assert "/api/auth/register" in source
    assert "AUTH_HEADER=" in source
    assert 'LOW_BUY_DETAIL_JSON="{}"' in source
    assert "confirmed_candidates should be a list" in source


def test_qa_smoke_deep_paths_keep_auth_header() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "qa_smoke.sh"
    source = script.read_text(encoding="utf-8")

    assert 'POST "http://127.0.0.1:${BACKEND_PORT}/api/backtests" "${AUTH_HEADER[@]}"' in source
    assert '"start_date":"2025-01-02"' in source
    assert '"risk_limits":{"max_position_pct":0.3,"max_positions":8}' in source
    assert 'GET /api/replays' not in source
    assert '/api/replays" "${AUTH_HEADER[@]}"' in source
    assert "backtest task response missing" in source
