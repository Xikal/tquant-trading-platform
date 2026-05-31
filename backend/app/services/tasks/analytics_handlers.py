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
from app.services.data_quality.repair import repair_invalid_ohlc
from app.services.data_quality.sla import SUPPORTED_DATASETS, compute_dataset_sla
from app.services.data_quality.snapshots import data_quality_sla_payload
from app.services.track_record.reporting import track_record_drift_payload
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
    registry.register("data_quality_sla_refresh", handle_data_quality_sla_refresh)
    registry.register("data_repair_run", handle_data_repair_run)
    registry.register("realized_outcome_refresh", handle_realized_outcome_refresh)
    registry.register("strategy_drift_refresh", handle_strategy_drift_refresh)


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
        data_quality_sla=data_quality_sla_payload(context.db),
        track_record_drift=track_record_drift_payload(context.db),
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


def handle_data_quality_sla_refresh(context: TaskContext) -> dict[str, Any]:
    payload = context.payload
    datasets = [str(item) for item in (payload.get("datasets") or ["daily_bars", "minute_bars", "tick_trades"])]
    scope = str(payload.get("scope") or "production_universe")
    end = _payload_end_date(payload)
    start = date.fromisoformat(str(payload["start_date"])[:10]) if payload.get("start_date") else None
    expected_days = int(payload["expected_days"]) if payload.get("expected_days") is not None else None
    snapshots = []
    for index, dataset_key in enumerate(datasets, start=1):
        if dataset_key not in SUPPORTED_DATASETS:
            raise ValueError(f"unsupported SLA dataset: {dataset_key}")
        context.progress(10.0 + index * 20.0, f"刷新 {dataset_key} 数据质量 SLA")
        snapshot = compute_dataset_sla(
            context.db,
            dataset_key=dataset_key,
            scope=scope,
            as_of=end,
            start_date=start,
            expected_days=expected_days,
        )
        snapshots.append(
            {
                "dataset_key": snapshot.dataset_key,
                "scope": snapshot.scope,
                "status": snapshot.status,
                "coverage_pct": float(snapshot.coverage_pct or 0.0),
                "missing_days": int(snapshot.missing_days or 0),
                "invalid_rows": int(snapshot.invalid_rows or 0),
                "duplicate_rows": int(snapshot.duplicate_rows or 0),
                "blockers_json": snapshot.blockers_json,
            }
        )
    payload_out = data_quality_sla_payload(context.db)
    _notify_data_quality_failures(payload_out)
    return {"ok": True, "status": "completed", "snapshots": snapshots, "data_quality_sla": payload_out}


def handle_data_repair_run(context: TaskContext) -> dict[str, Any]:
    payload = context.payload
    dataset_key = str(payload.get("dataset_key") or "daily_bars")
    dry_run = bool(payload.get("dry_run", True))
    context.progress(10.0, "开始数据修复 dry-run" if dry_run else "开始数据修复 apply")
    result = repair_invalid_ohlc(
        context.db,
        dataset_key=dataset_key,
        dry_run=dry_run,
        backup_dir=payload.get("backup_dir") or None,
        output_path=payload.get("output_path") or None,
        refetch=bool(payload.get("refetch", True)),
        operator=str(payload.get("operator") or f"analytics-worker:{context.worker_id}"),
    )
    if result.audit_path:
        context.add_artifact(result.audit_path)
    if result.row_backup_path:
        context.add_artifact(result.row_backup_path)
    if result.backup_path:
        context.add_artifact(result.backup_path)
    return {"ok": True, "repair": result.as_dict()}


def handle_realized_outcome_refresh(context: TaskContext) -> dict[str, Any]:
    from app.services.track_record.realized_outcome import refresh_realized_outcomes

    payload = context.payload
    as_of = _payload_end_date({"end_date": payload.get("as_of_date") or payload.get("end_date")})
    horizons = [int(item) for item in payload.get("horizons") or [1, 3, 5, 10]]
    context.progress(20.0, "开始结算生产信号 realized outcome")
    result = refresh_realized_outcomes(context.db, as_of=as_of, horizons=horizons)
    return {
        **result,
        "worker_scope": "analytics-worker",
        "task_type": "realized_outcome_refresh",
        "gate_owner": "production-track-record",
        "not_research_gated": True,
    }


def handle_strategy_drift_refresh(context: TaskContext) -> dict[str, Any]:
    from app.services.track_record.drift_alerts import maybe_send_drift_alert
    from app.services.track_record.drift_metrics import compute_all_strategy_drift

    payload = context.payload
    as_of = _payload_end_date({"end_date": payload.get("as_of_date") or payload.get("end_date")})
    window_days = int(payload.get("window_days") or 60)
    min_sample = int(payload.get("min_sample") or 20)
    context.progress(20.0, "开始计算生产信号 realized vs expected 漂移")
    snapshots = compute_all_strategy_drift(context.db, window_days=window_days, as_of=as_of, min_sample=min_sample)
    alerts = [maybe_send_drift_alert(snapshot) for snapshot in snapshots]
    return {
        "ok": True,
        "worker_scope": "analytics-worker",
        "task_type": "strategy_drift_refresh",
        "gate_owner": "production-track-record",
        "not_research_gated": True,
        "snapshots": [_drift_snapshot_payload(snapshot) for snapshot in snapshots],
        "alerts": alerts,
    }


def _payload_end_date(payload: dict[str, Any]) -> date:
    raw = str(payload.get("end_date") or date.today().isoformat())
    return date.fromisoformat(raw[:10])


def _drift_snapshot_payload(snapshot) -> dict[str, Any]:  # noqa: ANN001
    return {
        "strategy_key": snapshot.strategy_key,
        "drift_flag": snapshot.drift_flag,
        "sample_settled": int(snapshot.sample_settled or 0),
        "realized_pf": float(snapshot.realized_pf or 0.0) if snapshot.realized_pf is not None else None,
        "expected_pf": float(snapshot.expected_pf or 0.0) if snapshot.expected_pf is not None else None,
        "decay_pct": float(snapshot.decay_pct or 0.0),
    }


def _notify_data_quality_failures(payload: dict[str, Any]) -> None:
    failed = [item for item in payload.get("items") or [] if item.get("status") in {"fail", "unavailable"}]
    if not failed:
        return
    try:
        from app.models.schema_defs.agent import AgentNotificationTestRequest
        from app.services.agent_notification_service import AgentNotificationService

        service = AgentNotificationService()
        if not service.supports_channel("feishu"):
            return
        lines = ["数据质量 SLA 未通过："]
        for item in failed[:8]:
            blockers = "、".join(item.get("blockers") or []) or item.get("status", "")
            lines.append(f"- {item.get('dataset_key')}[{item.get('scope')}] {blockers}")
        service.send_test(AgentNotificationTestRequest(channel="feishu", message="\n".join(lines)))
    except Exception:
        return
