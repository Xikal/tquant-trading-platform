from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.schema_defs.phase4 import RuntimeTaskAnalyticsReportOut, RuntimeTaskAnalyticsReportResponse
from app.services.analytics.config import analytics_config


def read_analytics_report_index(
    *,
    output_root: str | Path | None = None,
    limit: int = 20,
) -> RuntimeTaskAnalyticsReportResponse:
    config = analytics_config(output_root)
    index_path = config.report_dir / "index.json"
    if not index_path.exists():
        return RuntimeTaskAnalyticsReportResponse(items=[], total=0, updated_at="")
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RuntimeTaskAnalyticsReportResponse(items=[], total=0, updated_at="")
    reports = list(payload.get("reports") or [])
    items = [_report_out(item) for item in reports[: max(int(limit or 20), 1)]]
    return RuntimeTaskAnalyticsReportResponse(
        items=items,
        total=len(reports),
        updated_at=str(payload.get("updated_at") or ""),
    )


def _report_out(item: dict[str, Any]) -> RuntimeTaskAnalyticsReportOut:
    return RuntimeTaskAnalyticsReportOut(
        report_type=str(item.get("report_type") or ""),
        generated_at=str(item.get("generated_at") or ""),
        status=str(item.get("status") or ""),
        manifest_id=_optional_text(item.get("manifest_id")),
        dataset_version=_optional_text(item.get("dataset_version")),
        duration_seconds=_optional_float(item.get("duration_seconds")),
        output_md=str(item.get("output_md") or ""),
        output_json=str(item.get("output_json") or ""),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
