#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RESOURCE_REPORT = Path("docs/reports/platform-resource-baseline-2026-06-08.json")
DEFAULT_BUDGET_REPORT = Path("docs/reports/platform-budget-2026-06-08.json")
DEFAULT_MANIFEST_REPORT = Path("docs/reports/platform-analytics-manifests-2026-06-08.json")
DEFAULT_EXPORT_PLAN = Path("docs/reports/platform-analytics-export-plan-2026-06-08.json")
DEFAULT_SUBMISSION_REPORT = Path("docs/reports/platform-analytics-export-submission-dry-run-2026-06-08.json")
DEFAULT_BACKUP_VERIFICATION = Path("docs/reports/platform-mysql-backup-verification-2026-06-08.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_readiness_report(
    *,
    resource_report: dict[str, Any],
    budget_report: dict[str, Any],
    manifest_report: dict[str, Any],
    export_plan: dict[str, Any],
    submission_report: dict[str, Any],
    backup_verification: dict[str, Any],
    paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    checks = [
        resource_limit_readiness(resource_report),
        mysql_backup_verification_readiness(backup_verification),
        worker_budget_readiness(budget_report),
        manifest_readiness(manifest_report),
        export_plan_readiness(export_plan),
        submission_readiness(submission_report, export_plan),
    ]
    blocking = [item for check in checks for item in check.get("blocking", [])]
    warnings = [item for check in checks for item in check.get("warnings", [])]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paths": paths or {},
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "ready_count": sum(1 for item in checks if item.get("status") == "ready"),
            "warning_count": sum(1 for item in checks if item.get("status") == "warning"),
            "blocking_count": sum(1 for item in checks if item.get("status") == "blocking"),
        },
        "evaluation": {
            "ok": not blocking,
            "status": "blocking" if blocking else ("warning" if warnings else "ready"),
            "blocking": blocking,
            "warnings": warnings,
        },
        "next_actions": next_actions(blocking, warnings),
    }


def mysql_backup_verification_readiness(report: dict[str, Any]) -> dict[str, Any]:
    evaluation = report.get("evaluation") or {}
    backup = report.get("backup") or {}
    blocking = [f"mysql_backup:{item}" for item in (evaluation.get("blocking") or [])]
    warnings = [f"mysql_backup:{item}" for item in (evaluation.get("warnings") or [])]
    if not bool(backup.get("present")):
        blocking.append("mysql_backup:backup_missing")
    if int(backup.get("size_bytes") or 0) <= 0:
        blocking.append(f"mysql_backup:invalid_size={backup.get('size_bytes')}")
    if backup.get("gzip_ok") is not True:
        blocking.append(f"mysql_backup:gzip_ok={backup.get('gzip_ok')}")
    if backup.get("sql_signature_ok") is not True:
        blocking.append(f"mysql_backup:sql_signature_ok={backup.get('sql_signature_ok')}")
    if not backup.get("sha256"):
        warnings.append("mysql_backup:sha256_missing")
    status = "blocking" if blocking else ("warning" if warnings else "ready")
    return {
        "name": "mysql_backup_verification",
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "evidence": {
            "path": backup.get("path"),
            "size_bytes": backup.get("size_bytes"),
            "gzip_ok": backup.get("gzip_ok"),
            "sql_signature_ok": backup.get("sql_signature_ok"),
            "sha256": backup.get("sha256"),
            "sql_signatures": backup.get("sql_signatures") or [],
        },
    }


def resource_limit_readiness(report: dict[str, Any]) -> dict[str, Any]:
    evaluation = report.get("evaluation") or {}
    resource_warnings = list(evaluation.get("warnings") or [])
    resource_blocking = list(evaluation.get("blocking") or [])
    config_missing = [item for item in resource_warnings if str(item).startswith("resource_config_missing=")]
    material_warnings = [
        item
        for item in resource_warnings
        if str(item).startswith(("swap_used_pct=", "mysql_slow_log_bytes=", "docker_build_cache_bytes=", "max_binlog_size="))
    ]
    blocking = [f"resource:{item}" for item in resource_blocking]
    warnings = [f"resource:{item}" for item in [*config_missing, *material_warnings]]
    status = "blocking" if blocking else ("warning" if warnings else "ready")
    return {
        "name": "resource_limits",
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "evidence": {
            "root_used_pct": (report.get("root") or {}).get("used_pct"),
            "swap_used_pct": ((report.get("memory") or {}).get("swap") or {}).get("used_pct"),
            "slow_log_bytes": (((report.get("mysql") or {}).get("slow_log") or {}).get("size_bytes")),
            "docker_build_cache_bytes": (((report.get("docker") or {}).get("build_cache") or {}).get("size_bytes")),
            "max_binlog_size": (((report.get("mysql") or {}).get("variables") or {}).get("max_binlog_size")),
        },
    }


def worker_budget_readiness(report: dict[str, Any]) -> dict[str, Any]:
    evaluation = report.get("evaluation") or {}
    raw_warnings = list(evaluation.get("warnings") or [])
    raw_blocking = list(evaluation.get("blocking") or [])
    blocking = [f"worker_budget:{item}" for item in raw_blocking]
    warnings = [f"worker_budget:{item}" for item in raw_warnings]
    status = "blocking" if blocking else ("warning" if warnings else "ready")
    return {
        "name": "worker_budget",
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "evidence": {
            "mysql": report.get("mysql") or {},
            "pool_budget": report.get("pool_budget") or {},
        },
    }


def manifest_readiness(report: dict[str, Any]) -> dict[str, Any]:
    evaluation = report.get("evaluation") or {}
    summary = report.get("summary") or {}
    blocking = [f"manifest:{item}" for item in (evaluation.get("blocking") or [])]
    warnings = [f"manifest:{item}" for item in (evaluation.get("warnings") or [])]
    status = "blocking" if blocking else ("warning" if warnings else "ready")
    return {
        "name": "analytics_manifest",
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "evidence": {
            "ready_count": summary.get("ready_count"),
            "missing_count": summary.get("missing_count"),
            "blocked_count": summary.get("blocked_count"),
            "verified_files": summary.get("verified_files"),
            "blocked_datasets": summary.get("blocked_datasets") or [],
        },
    }


def export_plan_readiness(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    evaluation = report.get("evaluation") or {}
    required_task_count = int(summary.get("required_task_count") or 0)
    blocking = []
    warnings = []
    safety = report.get("safety") or {}
    if required_task_count:
        warnings.append(f"export_plan:required_task_count={required_task_count}")
    for item in evaluation.get("blocking") or []:
        warnings.append(f"export_plan:{item}")
    status = "warning" if warnings else "ready"
    return {
        "name": "analytics_export_plan",
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "evidence": {
            "required_task_count": required_task_count,
            "required_tasks": summary.get("required_tasks") or [],
            "safe_dry_run": {
                "does_enqueue_tasks": safety.get("does_enqueue_tasks"),
                "does_run_exporters": safety.get("does_run_exporters"),
                "does_modify_mysql": safety.get("does_modify_mysql"),
                "does_clean_source_tables": safety.get("does_clean_source_tables"),
            },
        },
    }


def submission_readiness(report: dict[str, Any], export_plan: dict[str, Any]) -> dict[str, Any]:
    submission_summary = report.get("summary") or {}
    export_summary = export_plan.get("summary") or {}
    selected = int(submission_summary.get("selected_task_count") or 0)
    required = int(export_summary.get("required_task_count") or 0)
    submitted = int(submission_summary.get("submitted_task_count") or 0)
    blocking = []
    warnings = []
    if selected != required:
        blocking.append(f"submission:selected_task_count={selected}:required_task_count={required}")
    if submitted:
        blocking.append(f"submission:dry_run_submitted_task_count={submitted}")
    safety = report.get("safety") or {}
    if not bool(safety.get("requires_apply_flag")) or not bool(safety.get("requires_confirm_apply")):
        blocking.append("submission:apply_confirmation_guard_missing")
    if bool(safety.get("writes_runtime_tasks_only_when_apply")):
        blocking.append("submission:dry_run_would_write_tasks")
    status = "blocking" if blocking else ("warning" if warnings else "ready")
    return {
        "name": "analytics_export_submission",
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "evidence": {
            "selected_task_count": selected,
            "required_task_count": required,
            "submitted_task_count": submitted,
            "mode": report.get("mode"),
            "safety": safety,
        },
    }


def next_actions(blocking: list[str], warnings: list[str]) -> list[str]:
    actions: list[str] = []
    if any(item.startswith("resource:resource_config_missing=") for item in warnings):
        actions.append("Install resource limit templates in a maintenance window, then rerun resource baseline.")
    if any(item.startswith("resource:mysql_slow_log_bytes=") for item in warnings):
        actions.append("Back up and rotate MySQL slow log using the runbook.")
    if any(item.startswith("resource:docker_build_cache_bytes=") for item in warnings):
        actions.append("Enable BuildKit GC or perform safe build-cache-only cleanup; do not prune volumes.")
    if any(item.startswith("mysql_backup:") for item in blocking):
        actions.append("Create and verify a fresh MySQL .sql.gz backup before any maintenance or cleanup.")
    if any(item.startswith("worker_budget:") for item in warnings):
        actions.append("Restart/apply worker budget env and low-priority pause settings, then rerun budget verifier.")
    if any(item.startswith("manifest:") for item in blocking):
        actions.append("Submit planned analytics manifest export tasks in a low-traffic maintenance window and rerun manifest verifier.")
    if any(item.startswith("submission:") for item in blocking):
        actions.append("Fix analytics export submission plan before applying tasks.")
    if not actions:
        actions.append("All readiness checks are clear; continue with full validation gates before any cutover decision.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    evaluation = report.get("evaluation") or {}
    lines = [
        "# 平台资源优化 Readiness 聚合报告",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 状态：`{evaluation.get('status', 'unknown')}`",
        f"- 阻断项：{', '.join(evaluation.get('blocking') or []) or '无'}",
        f"- 警告项：{', '.join(evaluation.get('warnings') or []) or '无'}",
        "",
        "## 检查项",
        "",
        "| Check | Status | Blocking | Warnings |",
        "| --- | --- | --- | --- |",
    ]
    for check in report.get("checks") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(check.get("name") or ""),
                    str(check.get("status") or ""),
                    ", ".join(check.get("blocking") or []) or "-",
                    ", ".join(check.get("warnings") or []) or "-",
                ]
            )
            + " |"
        )
    lines.extend(["", "## 下一步", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate frontend-next platform optimization readiness reports.")
    parser.add_argument("--resource-report", type=Path, default=DEFAULT_RESOURCE_REPORT)
    parser.add_argument("--budget-report", type=Path, default=DEFAULT_BUDGET_REPORT)
    parser.add_argument("--manifest-report", type=Path, default=DEFAULT_MANIFEST_REPORT)
    parser.add_argument("--export-plan", type=Path, default=DEFAULT_EXPORT_PLAN)
    parser.add_argument("--submission-report", type=Path, default=DEFAULT_SUBMISSION_REPORT)
    parser.add_argument("--backup-verification-report", type=Path, default=DEFAULT_BACKUP_VERIFICATION)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-blocking", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = {
        "resource_report": str(args.resource_report),
        "budget_report": str(args.budget_report),
        "manifest_report": str(args.manifest_report),
        "export_plan": str(args.export_plan),
        "submission_report": str(args.submission_report),
        "backup_verification_report": str(args.backup_verification_report),
    }
    report = build_readiness_report(
        resource_report=load_json(args.resource_report),
        budget_report=load_json(args.budget_report),
        manifest_report=load_json(args.manifest_report),
        export_plan=load_json(args.export_plan),
        submission_report=load_json(args.submission_report),
        backup_verification=load_json(args.backup_verification_report),
        paths=paths,
    )
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report["evaluation"], ensure_ascii=False))
    if args.fail_on_blocking and report["evaluation"]["blocking"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
