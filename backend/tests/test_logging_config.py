from __future__ import annotations

import json
import logging
import sys

from app.core.logging_config import JsonLogFormatter, configure_logging


def test_json_log_formatter_emits_valid_structured_log() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("structured",),
        exc_info=None,
    )

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["module"] == "app.test"
    assert payload["message"] == "hello structured"
    assert payload["timestamp"]


def test_json_log_formatter_emits_whitelisted_extra_fields() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=20,
        msg="provider fallback",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    record.task_id = 42
    record.task_type = "analytics_export"
    record.trade_date = "2026-06-11"
    record.symbol = "600000"
    record.component = "runtime-task-worker"
    record.provider = "eastmoney"
    record.read_path = "priority_board_read_model"
    record.secret = "must-not-leak"

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["request_id"] == "req-1"
    assert payload["task_id"] == 42
    assert payload["task_type"] == "analytics_export"
    assert payload["trade_date"] == "2026-06-11"
    assert payload["symbol"] == "600000"
    assert payload["component"] == "runtime-task-worker"
    assert payload["provider"] == "eastmoney"
    assert payload["read_path"] == "priority_board_read_model"
    assert "secret" not in payload


def test_json_log_formatter_keeps_exception_field() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=55,
            msg="failed",
            args=(),
            exc_info=exc_info,
        )

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["exception"]
    assert "ValueError: boom" in payload["exception"]


def test_configure_logging_leaves_plain_mode_formatter_unchanged() -> None:
    logger = logging.getLogger("test.configure.plain")
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s:%(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        root.handlers = [handler]
        configure_logging(structured=False)
        assert root.handlers[0].formatter is formatter
    finally:
        root.handlers = original_handlers
