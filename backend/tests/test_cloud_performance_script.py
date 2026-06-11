from __future__ import annotations

import re
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
    assert '"/api/screeners/low-buy/priority-board?limit=12&refresh=cache"' in source
    assert "go_bff_metrics_before = metrics" in source
    assert "go_bff_metrics_delta = metric_delta" in source
    assert "go_market_metrics_delta = metric_delta" in source
    assert '"monitor_bff_sources"' in source
    assert '"priority_board_breakdown"' in source
    assert '"go_bff_cache_hit_rate"' in source
    assert '"go_bff_partial_errors_by_source"' in source
    assert "partial_errors_by_source" in source
    assert "capture_payload=True" in source
    assert "api_prewarm = prewarm_api_paths(token)" in source
    assert '"api_prewarm": api_prewarm' in source
    assert '"samples": sample_details' in source
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


def test_mysql_compose_exposes_low_priority_task_pause_to_workers():
    compose = Path(__file__).resolve().parents[1].parent / "docker-compose.mysql.yml"
    source = compose.read_text(encoding="utf-8")

    assert "x-low-priority-task-types: &low_priority_task_types" in source
    assert "analytics_export_backtest_trades" in source
    assert "analytics_export_backtest_daily_snapshots" in source
    assert "analytics_export_analysis_logs" in source
    assert "analytics_export_market_review_reports" in source
    assert "analytics_export_paper_review_reports" not in source
    for service in ("runtime-worker", "runtime-scheduler"):
        match = re.search(rf"^  {re.escape(service)}:\n(?P<body>(?:    .*\n)+)", source, flags=re.MULTILINE)
        assert match is not None
        service_block = match.group("body")
        assert "RUNTIME_LOW_PRIORITY_TASKS_PAUSED: ${RUNTIME_LOW_PRIORITY_TASKS_PAUSED:-false}" in service_block
        assert "RUNTIME_LOW_PRIORITY_TASK_TYPES: *low_priority_task_types" in service_block
        if service == "runtime-worker":
            assert "RUNTIME_WORKER_RECYCLE_RSS_MB: ${RUNTIME_WORKER_RECYCLE_RSS_MB:-0}" in service_block
    analytics_block = source.split("  analytics-worker:", 1)[1].split("\n\n  migration:", 1)[0]
    assert 'profiles: ["analytics"]' in analytics_block
    assert "RUNTIME_LOW_PRIORITY_TASKS_PAUSED: ${RUNTIME_LOW_PRIORITY_TASKS_PAUSED:-false}" in analytics_block
    assert "RUNTIME_LOW_PRIORITY_TASK_TYPES: *low_priority_task_types" in analytics_block


def test_mysql_compose_keeps_role_pool_budget_below_single_host_limit() -> None:
    compose = Path(__file__).resolve().parents[1].parent / "docker-compose.mysql.yml"
    source = compose.read_text(encoding="utf-8")

    assert "--max-connections=${MYSQL_MAX_CONNECTIONS:-120}" in source
    assert "--binlog-expire-logs-seconds=${MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}" in source
    assert "--max-binlog-size=${MYSQL_MAX_BINLOG_SIZE:-256M}" in source
    assert "DB_POOL_SIZE: ${WEB_DB_POOL_SIZE:-4}" in source
    assert "DB_MAX_OVERFLOW: ${WEB_DB_MAX_OVERFLOW:-4}" in source
    assert "DB_POOL_SIZE: ${WORKER_DB_POOL_SIZE:-2}" in source
    assert "DB_MAX_OVERFLOW: ${WORKER_DB_MAX_OVERFLOW:-2}" in source
    assert "DB_POOL_SIZE: ${SCHEDULER_DB_POOL_SIZE:-2}" in source
    assert "DB_MAX_OVERFLOW: ${SCHEDULER_DB_MAX_OVERFLOW:-2}" in source
    assert "DB_POOL_SIZE: ${ANALYTICS_DB_POOL_SIZE:-4}" in source
    assert "DB_MAX_OVERFLOW: ${ANALYTICS_DB_MAX_OVERFLOW:-4}" in source
    assert "APP_WORKERS: ${APP_WORKERS:-1}" in source
    assert "RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED: ${RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED:-false}" in source
    assert "RUNTIME_QUOTE_CACHE_REFRESH_INTERVAL_SECONDS: ${RUNTIME_QUOTE_CACHE_REFRESH_INTERVAL_SECONDS:-30}" in source
    assert "--max-connections=${MYSQL_MAX_CONNECTIONS:-300}" not in source


def test_backtest_worker_compose_service_is_removed_to_free_resources() -> None:
    compose = Path(__file__).resolve().parents[1].parent / "docker-compose.mysql.yml"
    source = compose.read_text(encoding="utf-8")

    assert "backtest-worker:" not in source
    assert "app.workers.backtest_queue_worker" not in source


def test_runbook_uses_safe_password_placeholder_and_documents_go_main_path():
    runbook = Path(__file__).resolve().parents[1].parent / "PRODUCTION_RUNBOOK.md"
    source = runbook.read_text(encoding="utf-8")
    assert "你的密码" not in source
    assert "<DB_PASSWORD>" in source
    assert "生产主路径组件" in source
    assert "traceparent" in source
    assert "自动止损实盘化" in source
