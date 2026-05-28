from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_report_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "docs" / "reports"


def load_etf_minute_provider_diagnostics(report_dir: Path | None = None) -> dict[str, Any]:
    directory = report_dir or default_report_dir()
    if not directory.exists():
        return _empty("not_found")

    reports = sorted(directory.glob("etf-minute-backfill*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for report_path in reports:
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        diagnostics = summarize_etf_minute_provider_report(payload, report_path)
        if diagnostics["status"] != "unknown" or diagnostics["provider_errors_sample"]:
            return diagnostics
    return _empty("not_found")


def summarize_etf_minute_provider_report(payload: dict[str, Any], report_path: Path) -> dict[str, Any]:
    provider_errors = []
    for result in payload.get("results") or []:
        symbol = str(result.get("symbol") or "")
        for error in result.get("provider_errors") or []:
            provider_errors.append(
                {
                    "symbol": symbol,
                    "source": str(error.get("source") or ""),
                    "message": sanitize_provider_message(str(error.get("message") or "")),
                }
            )
            if len(provider_errors) >= 12:
                break
        if len(provider_errors) >= 12:
            break

    totals = payload.get("totals") or {}
    ok_count = int(totals.get("ok") or 0)
    return {
        "status": str(payload.get("status") or "unknown"),
        "report_path": _display_path(report_path),
        "generated_at": str(payload.get("generated_at") or ""),
        "totals": {
            "ok": ok_count,
            "skip": int(totals.get("skip") or 0),
            "empty": int(totals.get("empty") or 0),
            "error": int(totals.get("error") or 0),
        },
        "provider_errors_sample": provider_errors,
        "write_effect": "no_bars_written" if ok_count <= 0 else "provider_bars_written",
        "fake_data_policy": "fake_minute_bars_forbidden",
    }


def sanitize_provider_message(message: str) -> str:
    compact = " ".join(message.split())
    lowered = compact.lower()
    if "token=" in lowered or "apikey=" in lowered or "api_key=" in lowered:
        return "message redacted because it may contain credentials"
    return compact[:220]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(__file__).resolve().parents[4]))
    except ValueError:
        return str(path)


def _empty(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "report_path": "",
        "generated_at": "",
        "totals": {"ok": 0, "skip": 0, "empty": 0, "error": 0},
        "provider_errors_sample": [],
        "write_effect": "no_bars_written",
        "fake_data_policy": "fake_minute_bars_forbidden",
    }
