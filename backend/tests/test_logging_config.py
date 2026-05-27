from __future__ import annotations

import json
import logging

from app.core.logging_config import JsonLogFormatter


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
