from __future__ import annotations

from pathlib import Path


def test_acceptance_script_uses_env_project_root():
    script = Path(__file__).resolve().parents[1].parent / "scripts" / "verify_go_rust_performance_acceptance.py"
    source = script.read_text(encoding="utf-8")
    assert "TQUANT_ACCEPTANCE_PROJECT_ROOT" in source
    assert "TQUANT_ACCEPTANCE_REPORT_PATH" in source
    assert "missing source path" in source


def test_cloud_measurement_script_has_hard_thresholds():
    script = Path(__file__).resolve().parents[1].parent / "scripts" / "measure_cloud_go_rust_performance.py"
    source = script.read_text(encoding="utf-8")
    assert '"priority_board": 500' in source
    assert '"market_pulse": 500' in source
    assert '"scan_worker_accept": 500' in source
    assert "scan_has_real_failure" in source
    assert "HTTPError" in source
    assert "rust_smoke" in source
    assert '"rust_finance_math"' in source
    assert "quote_cache_snapshot" in source
    assert '"quote_cache_coverage"' in source
    assert source.index("quote_cache = quote_cache_snapshot()") < source.index("api = [")
    assert "DEFAULT_LIMIT, MarketQuoteCacheRefreshService" in source
    assert '"quote_cache_warmup_coverage"' in source
    assert '"quote_cache_batch_coverage"' in source
    assert "tquant-go-bff-gateway" in source
    assert "tquant-go-scan-worker" in source


def test_cloud_measurement_scan_accept_reads_non_2xx_body():
    script = Path(__file__).resolve().parents[1].parent / "scripts" / "measure_cloud_go_rust_performance.py"
    source = script.read_text(encoding="utf-8")
    assert "CalledProcessError" in source
    assert "parse_scan_worker_payload" in source
    assert "busy" in source
    assert "duplicate" in source
    assert "fallback_available" in source


def test_cloud_measurement_retries_transient_remote_protocol_errors() -> None:
    script = Path(__file__).resolve().parents[1].parent / "scripts" / "measure_cloud_go_rust_performance.py"
    source = script.read_text(encoding="utf-8")

    assert "PERFORMANCE_MEASUREMENT_RETRY_ENABLED" in source
    assert "RemoteProtocolError" in source
    assert "Server disconnected without sending a response" in source
    assert "retrying transient online measurement" in source
    assert "retry_errors" in source


def test_mysql_compose_runs_go_services_on_production_path_by_default():
    compose = Path(__file__).resolve().parents[1].parent / "docker-compose.mysql.yml"
    source = compose.read_text(encoding="utf-8")
    for service in ("go-bff-gateway", "go-market-read-service", "go-scan-worker"):
        service_block = source.split(f"  {service}:", 1)[1].split("\n  ", 1)[0]
        assert "profiles:" not in service_block
    assert "TQUANT_BFF_GATEWAY_URL: ${TQUANT_BFF_GATEWAY_URL:-http://go-bff-gateway:8091}" in source
    assert "STRUCTURED_LOGS: ${STRUCTURED_LOGS:-true}" in source


def test_runbook_uses_safe_password_placeholder_and_documents_go_main_path():
    runbook = Path(__file__).resolve().parents[1].parent / "PRODUCTION_RUNBOOK.md"
    source = runbook.read_text(encoding="utf-8")
    assert "你的密码" not in source
    assert "<DB_PASSWORD>" in source
    assert "生产主路径组件" in source
    assert "traceparent" in source
    assert "自动止损实盘化" in source
