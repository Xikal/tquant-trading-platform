from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app.core.database import SessionLocal
from app.models.schema_defs.backtest import BacktestRunCreate
from app.services.analytics import export_daily_bars_parquet, load_manifest
from app.services.analytics.config import PROJECT_ROOT
from app.services.analytics.quality import check_daily_bars_24m_quality
from app.services.analytics.report_queries import build_strategy_24m_duckdb_report, write_strategy_24m_report
from app.services.backtest_job_service import BacktestJobService
from app.services.tasks.handlers import TaskContext
from app.services.tasks.registry import TaskHandlerRegistry


DEFAULT_MD = PROJECT_ROOT / "backend" / "data" / "analytics" / "reports" / "strategy_24m_duckdb_report.md"
DEFAULT_JSON = PROJECT_ROOT / "backend" / "data" / "analytics" / "reports" / "strategy_24m_duckdb_report.json"


def register_analytics_handlers(registry: TaskHandlerRegistry) -> None:
    registry.register("data_backfill_24m", handle_data_backfill_24m)
    registry.register("analytics_export_daily_bars", handle_analytics_export_daily_bars)
    registry.register("analytics_quality_check", handle_analytics_quality_check)
    registry.register("strategy_24m_duckdb_report", handle_strategy_24m_duckdb_report)
    registry.register("decision_context_24m_report", handle_strategy_24m_duckdb_report)
    registry.register("portfolio_execution_24m_report", handle_strategy_24m_duckdb_report)
    registry.register("backtest_all_strategies_24m", handle_backtest_all_strategies_24m)


def handle_data_backfill_24m(context: TaskContext) -> dict[str, Any]:
    payload = context.payload
    months = int(payload.get("months") or 24)
    end_date = str(payload.get("end_date") or date.today().isoformat())
    command = [
        sys.executable,
        str(PROJECT_ROOT / "backend" / "scripts" / "backfill_daily_history.py"),
        "--months",
        str(months),
        "--end-date",
        end_date,
        "--scope",
        str(payload.get("scope") or "all-stock"),
        "--report-output",
        str(PROJECT_ROOT / "backend" / "data" / "analytics" / "reports" / f"data_backfill_24m_task_{context.task_id}.json"),
    ]
    if payload.get("start_date"):
        command.extend(["--start-date", str(payload["start_date"])])
    if payload.get("limit"):
        command.extend(["--limit", str(payload["limit"])])
    context.progress(5.0, "开始补齐24个月日线数据", {"command": " ".join(command)})
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=int(payload.get("timeout_seconds") or 21600))
    artifact = str(PROJECT_ROOT / "backend" / "data" / "analytics" / "reports" / f"data_backfill_24m_task_{context.task_id}.json")
    context.add_artifact(artifact)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "data_backfill_24m failed")[-1000:])
    context.progress(90.0, "补数脚本完成，等待质量复查")
    quality = check_daily_bars_24m_quality(context.db, months=months, end_date=date.fromisoformat(end_date), create_backfill_task=False)
    return {"ok": quality.status == "ok", "quality": quality.as_dict(), "artifacts": [artifact], "stdout_tail": completed.stdout[-2000:]}


def handle_analytics_export_daily_bars(context: TaskContext) -> dict[str, Any]:
    months = int(context.payload.get("months") or 24)
    end = _payload_end_date(context.payload)
    context.progress(10.0, "开始导出 daily_bars Parquet")
    manifest = export_daily_bars_parquet(
        context.db,
        months=months,
        end_date=end,
        output_root=context.payload.get("output_root"),
        create_backfill_task=True,
    )
    context.add_artifact(str(manifest.get("manifest_path") or ""))
    return {"ok": manifest.get("quality", {}).get("status") == "ok", "manifest": manifest, "artifacts": [manifest.get("manifest_path")]}


def handle_analytics_quality_check(context: TaskContext) -> dict[str, Any]:
    months = int(context.payload.get("months") or 24)
    end = _payload_end_date(context.payload)
    context.progress(20.0, "开始检查24个月日线完整性")
    quality = check_daily_bars_24m_quality(context.db, months=months, end_date=end, create_backfill_task=True)
    return {"ok": quality.status == "ok", "quality": quality.as_dict()}


def handle_strategy_24m_duckdb_report(context: TaskContext) -> dict[str, Any]:
    months = int(context.payload.get("months") or 24)
    end = _payload_end_date(context.payload)
    context.progress(10.0, "检查24个月日线完整性")
    manifest_ref = str(context.payload.get("manifest") or "latest")
    if manifest_ref == "latest":
        manifest = export_daily_bars_parquet(
            context.db,
            months=months,
            end_date=end,
            output_root=context.payload.get("output_root"),
            create_backfill_task=True,
        )
    else:
        manifest = load_manifest(manifest_ref, output_root=context.payload.get("output_root"))
    context.progress(55.0, "开始 DuckDB 报告查询")
    report = build_strategy_24m_duckdb_report(
        manifest,
        output_root=context.payload.get("output_root"),
        legacy_strategy_report=context.payload.get("strategy_report_json") or None,
    )
    output_md = Path(context.payload.get("output_md") or DEFAULT_MD)
    output_json = Path(context.payload.get("output_json") or DEFAULT_JSON)
    write_strategy_24m_report(report, output_md=output_md, output_json=output_json)
    context.add_artifact(str(output_md))
    context.add_artifact(str(output_json))
    if report.get("status") != "ok":
        raise RuntimeError(f"strategy_24m_duckdb_report blocked: {report.get('status')}")
    return {
        "ok": True,
        "status": report.get("status"),
        "manifest": report.get("manifest"),
        "artifacts": [str(output_md), str(output_json)],
        "strategy_count": len(report.get("all_strategies") or []),
        "recommendations": report.get("strategy_adjustment_recommendations") or [],
    }


def handle_backtest_all_strategies_24m(context: TaskContext) -> dict[str, Any]:
    months = int(context.payload.get("months") or 24)
    end = _payload_end_date(context.payload)
    quality = check_daily_bars_24m_quality(context.db, months=months, end_date=end, create_backfill_task=True)
    if quality.status != "ok":
        return {"ok": False, "status": "blocked_by_data", "quality": quality.as_dict()}
    from app.services.low_buy_screener import PLAYBOOKS

    context.progress(20.0, "数据完整性通过，提交全策略回测任务")
    start = quality.period_start
    payload = BacktestRunCreate(
        name=f"全策略24个月回测 {start}~{quality.period_end}",
        strategies=list(PLAYBOOKS.keys()),
        start_date=start,
        end_date=quality.period_end,
        initial_capital=float(context.payload.get("initial_capital") or 100000),
        resource_tier="full",
        params={"source_task_id": context.task_id, "months": months},
    )
    run = BacktestJobService(context.db).create_run(payload, owner_user_id=None)
    return {"ok": True, "status": "queued_backtest_run", "run_id": run.id, "quality": quality.as_dict()}


def _payload_end_date(payload: dict[str, Any]) -> date:
    raw = str(payload.get("end_date") or date.today().isoformat())
    return date.fromisoformat(raw[:10])
