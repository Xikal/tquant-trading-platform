from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_trade_date_string_field_audit_lists_migration_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "audit_trade_date_fields.py")],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["count"] >= 1
    fields = {(item["table"], item["column"]) for item in payload["items"]}
    assert ("market_hourly_snapshot_history", "trade_date") in fields
    assert ("market_pulse_events", "trade_date") in fields
    assert ("intraday_confirmation_snapshots", "trade_date") in fields
