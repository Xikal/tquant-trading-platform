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
DEFAULT_READINESS_REPORT = Path("docs/reports/platform-optimization-readiness-2026-06-08.json")
DEFAULT_MAINTENANCE_PLAN = Path("docs/reports/platform-maintenance-window-plan-2026-06-08.json")
DEFAULT_CHUNK_PROFILE = Path("docs/reports/frontend-next-chunk-profile-2026-06-08.json")
DEFAULT_COMPLETION_AUDIT = Path("docs/reports/platform-resource-optimization-completion-audit-2026-06-08.json")
DEFAULT_CLOUD_PERFORMANCE = Path("docs/reports/gupiao-cloud-performance-2026-06-08-000012.json")
DEFAULT_BACKUP_VERIFICATION = Path("docs/reports/platform-mysql-backup-verification-2026-06-08.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


KEY_DELIVERABLES = [
    "frontend-next strategy-tracking BFF 合包、paper 非机甲长列表虚拟化、ECharts 首屏懒加载、CSS guard/报告。",
    "scripts/collect_platform_resource_report.py：只读采集 df/free/docker/journal/mysql/binlog/slow log/备份状态。",
    "scripts/install_platform_resource_limits.py 与 deploy/* 模板：Docker log、journal、BuildKit 和 MySQL slow logrotate 上限，默认 dry-run；MySQL binlog/max-binlog 由 docker-compose.mysql.yml command 管理。",
    "scripts/verify_platform_budget.py：MySQL 连接池、worker 角色预算、Web 重任务 guard。",
    "scripts/verify_analytics_manifests.py：Parquet manifest 只读校验和 sha256 文件验证。",
    "scripts/plan_analytics_manifest_exports.py 与 scripts/submit_analytics_manifest_exports.py：导出任务计划和显式 apply 入队。",
    "scripts/verify_platform_optimization_readiness.py：聚合 resource/budget/manifest/export/submission 总 gate。",
    "scripts/plan_platform_maintenance_window.py：生成人工维护窗口步骤，不执行命令。",
    "docs/operations/mysql-maintenance-runbook.md：MySQL 备份、binlog、slow log、analytics manifest 运维流程。",
    "docs/frontend-next-cutover-runbook-2026-06-05.md 与 PRODUCTION_RUNBOOK.md：补入正式部署/切流前平台资源 gate。",
    "frontend-next/scripts/perf-profile.mjs：输出结构化 perf JSON，供完成度审计验证 strategy 请求和 paper DOM。",
]


VALIDATION_REFERENCES = [
    "docs/reports/platform-resource-baseline-2026-06-08.md",
    "docs/reports/platform-mysql-backup-verification-2026-06-08.md",
    "docs/reports/platform-budget-2026-06-08.md",
    "docs/reports/platform-analytics-manifests-2026-06-08.md",
    "docs/reports/platform-optimization-readiness-2026-06-08.md",
    "docs/reports/platform-maintenance-window-plan-2026-06-08.md",
    "docs/reports/frontend-next-performance-optimization-2026-06-08.md",
    "docs/reports/frontend-next-css-optimization-2026-06-08.md",
    "docs/reports/frontend-next-perf-compare-2026-06-08.json",
    "docs/reports/frontend-next-chunk-profile-2026-06-08.md",
    "docs/reports/platform-resource-optimization-completion-audit-2026-06-08.md",
]


def build_acceptance(
    *,
    resource_report: dict[str, Any],
    budget_report: dict[str, Any],
    manifest_report: dict[str, Any],
    readiness_report: dict[str, Any],
    maintenance_plan: dict[str, Any],
    chunk_profile: dict[str, Any] | None = None,
    completion_audit: dict[str, Any] | None = None,
    cloud_performance: dict[str, Any] | None = None,
    cloud_performance_report_path: Path | None = None,
    backup_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = readiness_report.get("evaluation") or {}
    resource_eval = resource_report.get("evaluation") or {}
    budget_eval = budget_report.get("evaluation") or {}
    manifest_eval = manifest_report.get("evaluation") or {}
    manifest_summary = manifest_report.get("summary") or {}
    root = resource_report.get("root") or {}
    memory = resource_report.get("memory") or {}
    mysql = resource_report.get("mysql") or {}
    docker = resource_report.get("docker") or {}
    deploy_backups = resource_report.get("deploy_backups") or {}
    mysql_backups = resource_report.get("mysql_backups") or {}
    chunk = chunk_profile or {}
    completion = completion_audit or {}
    online_performance = summarize_cloud_performance(cloud_performance or {}, cloud_performance_report_path)
    backup_state = summarize_backup_verification(backup_verification or {})
    validation_references = list(VALIDATION_REFERENCES)
    if cloud_performance and cloud_performance_report_path:
        cloud_path = str(cloud_performance_report_path)
        if cloud_path not in validation_references:
            validation_references.append(cloud_path)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": readiness.get("status") or "unknown",
        "self_use_status": "可以继续通过 /next/* 自用和验收；阻断项主要影响正式 cutover 和长期稳定性。",
        "formal_cutover_status": "not_ready" if readiness.get("status") == "blocking" else "requires_separate_authorization",
        "deployed": False,
        "cutover": False,
        "old_frontend_modified": False,
        "strategy_policy_modified": False,
        "production_semantics_changed": False,
        "backend_change_reason": (
            "后端改动用于 BFF 合包、worker 预算/低优先级暂停、analytics Parquet 导出、"
            "只读资源/manifest/readiness 验证和部署资源 gate；不改变生产策略语义、生产排序、"
            "production_score 或 priority_board 口径。"
        ),
        "platform_impact": "不影响；当前未部署、未切流，生产策略语义和排序口径未改变。",
        "key_deliverables": KEY_DELIVERABLES,
        "validation_references": validation_references,
        "phase_completion": {
            "phase_a_resource_limits": "implemented_not_applied_online",
            "phase_b_frontend_next_performance": "implemented_local_verified",
            "phase_c_worker_budget": "implemented_not_applied_online",
            "phase_d_parquet_manifest": "implemented_but_online_manifest_blocking",
            "phase_e_prebuilt_deploy": "scripted_not_applied_online",
            "phase_f_qa_reporting": "partial_current_slice_verified",
        },
        "before_after": {
            "root_used_pct": root.get("used_pct"),
            "available_memory_mb": ((memory.get("mem") or {}).get("available_mb")),
            "swap_used_pct": ((memory.get("swap") or {}).get("used_pct")),
            "journal_usage_bytes": (resource_report.get("journal") or {}).get("usage_bytes"),
            "mysql_volume_bytes": max(
                [
                    int(row.get("size_bytes") or 0)
                    for row in ((mysql.get("volume") or {}).get("rows") or [])
                    if isinstance(row, dict)
                ]
                or [0]
            ),
            "mysql_slow_log_bytes": ((mysql.get("slow_log") or {}).get("size_bytes")),
            "docker_build_cache_bytes": ((docker.get("build_cache") or {}).get("size_bytes")),
            "deploy_backup_count": deploy_backups.get("count"),
            "mysql_max_connections": (budget_report.get("mysql") or {}).get("max_connections"),
            "threads_connected": (budget_report.get("mysql") or {}).get("threads_connected"),
            "frontend_initial_js_raw_bytes": (chunk.get("summary") or {}).get("initial_js_raw_bytes"),
            "frontend_initial_echarts_asset_count": (chunk.get("summary") or {}).get("initial_echarts_assets"),
            "online_readyz_p95_ms": online_performance.get("api_p95_ms", {}).get("readyz"),
            "online_monitor_bff_p95_ms": online_performance.get("api_p95_ms", {}).get("monitor_bff"),
            "online_priority_board_p95_ms": online_performance.get("api_p95_ms", {}).get("priority_board"),
            "mysql_backup_gzip_ok": backup_state.get("gzip_ok"),
            "mysql_backup_sql_signature_ok": backup_state.get("sql_signature_ok"),
        },
        "resource_state": {
            "evaluation": resource_eval,
            "mysql_backup": mysql_backups,
            "mysql_backup_verification": backup_state,
            "deploy_backups": deploy_backups,
            "mysql": {
                "binlog_expire_logs_seconds": ((mysql.get("variables") or {}).get("binlog_expire_logs_seconds")),
                "max_binlog_size": ((mysql.get("variables") or {}).get("max_binlog_size")),
                "binary_log_count": ((mysql.get("binary_logs") or {}).get("count")),
                "binary_log_total_bytes": ((mysql.get("binary_logs") or {}).get("total_bytes")),
                "slow_log_bytes": ((mysql.get("slow_log") or {}).get("size_bytes")),
            },
            "docker": {
                "build_cache_bytes": ((docker.get("build_cache") or {}).get("size_bytes")),
                "volume_bytes": ((docker.get("local_volumes") or {}).get("size_bytes")),
            },
        },
        "worker_state": {
            "evaluation": budget_eval,
            "pool_budget": budget_report.get("pool_budget") or {},
            "mysql": budget_report.get("mysql") or {},
        },
        "online_performance_state": online_performance,
        "parquet_manifest_state": {
            "evaluation": manifest_eval,
            "ready_count": manifest_summary.get("ready_count"),
            "missing_count": manifest_summary.get("missing_count"),
            "blocked_count": manifest_summary.get("blocked_count"),
            "verified_files": manifest_summary.get("verified_files"),
            "blocked_datasets": manifest_summary.get("blocked_datasets") or [],
        },
        "readiness": readiness,
        "maintenance_plan": {
            "path": "docs/reports/platform-maintenance-window-plan-2026-06-08.md",
            "step_count": len(maintenance_plan.get("steps") or []),
            "operator_apply_steps": (maintenance_plan.get("safety") or {}).get("operator_apply_steps") or [],
        },
        "completion_audit": {
            "path": "docs/reports/platform-resource-optimization-completion-audit-2026-06-08.md",
            "status": completion.get("status") or "not_generated",
            "summary": completion.get("summary") or {},
        },
        "rollback": [
            "资源上限配置：恢复 /etc/tquant-resource-backups/<timestamp>/ 中的配置并重启对应服务。",
            "Analytics 导出任务：通过 POST /api/runtime-tasks/<task_id>/cancel 取消 queued/running 任务。",
            "frontend-next：当前未切流；旧 frontend 保持可回滚入口。",
            "MySQL 源数据：当前未清理；任何热库清理仍需单独授权和恢复路径。",
        ],
        "required_before_cutover": [
            "维护窗口内 apply 资源上限配置并重启/复验相关服务。",
            "执行 analytics manifest 导出任务，补齐 9 个缺失 manifest 后重跑 verifier/readiness。",
            "复跑 frontend-next 全量验收命令、资源验收、request trace 和 performance gate。",
            "用户单独授权 cutover；失败即停止，保留旧 frontend 回滚。",
        ],
        "open_items": build_open_items(readiness_report),
        "cutover_requires_separate_authorization": True,
    }


def build_open_items(readiness_report: dict[str, Any]) -> list[str]:
    evaluation = readiness_report.get("evaluation") or {}
    items = []
    for blocker in evaluation.get("blocking") or []:
        items.append(f"blocking:{blocker}")
    for warning in evaluation.get("warnings") or []:
        items.append(f"warning:{warning}")
    return items


def summarize_cloud_performance(report: dict[str, Any], report_path: Path | None = None) -> dict[str, Any]:
    api_p95_ms: dict[str, Any] = {}
    api_statuses: dict[str, Any] = {}
    for item in report.get("api") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        api_p95_ms[str(name)] = item.get("p95_ms")
        api_statuses[str(name)] = item.get("statuses")
    return {
        "report": str(report_path) if report and report_path else "",
        "ok": report.get("ok") if report else None,
        "failures": report.get("failures") or [],
        "api_p95_ms": api_p95_ms,
        "api_statuses": api_statuses,
        "monitor_bff_sources": report.get("monitor_bff_sources") or [],
        "priority_board_breakdown": report.get("priority_board_breakdown") or {},
    }


def summarize_backup_verification(report: dict[str, Any]) -> dict[str, Any]:
    backup = report.get("backup") or {}
    evaluation = report.get("evaluation") or {}
    return {
        "report": "docs/reports/platform-mysql-backup-verification-2026-06-08.md" if report else "",
        "status": evaluation.get("status"),
        "blocking": evaluation.get("blocking") or [],
        "warnings": evaluation.get("warnings") or [],
        "path": backup.get("path"),
        "size_bytes": backup.get("size_bytes"),
        "gzip_ok": backup.get("gzip_ok"),
        "sql_signature_ok": backup.get("sql_signature_ok"),
        "sha256": backup.get("sha256"),
        "sql_signatures": backup.get("sql_signatures") or [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# frontend-next 与平台资源优化验收草案",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 总状态：`{report.get('status', '')}`",
        f"- 未部署：`{not bool(report.get('deployed'))}`",
        f"- 未切流：`{not bool(report.get('cutover'))}`",
        f"- 自用状态：{report.get('self_use_status')}",
        f"- 正式 cutover 状态：`{report.get('formal_cutover_status')}`",
        f"- 是否影响平台功能：{report.get('platform_impact')}",
        f"- 后端改动原因：{report.get('backend_change_reason')}",
        f"- 旧 frontend 是否未改：`{not bool(report.get('old_frontend_modified'))}`",
        f"- strategy_policy.py 是否未改：`{not bool(report.get('strategy_policy_modified'))}`",
        f"- Cutover 是否仍需单独授权：`{bool(report.get('cutover_requires_separate_authorization'))}`",
        "",
        "## 新增/修改重点文件",
        "",
    ]
    for item in report.get("key_deliverables") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 证据报告",
            "",
        ]
    )
    for item in report.get("validation_references") or []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Phase 完成度",
            "",
            "| Phase | 状态 |",
            "| --- | --- |",
        ]
    )
    for key, value in (report.get("phase_completion") or {}).items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Before/After 指标", "", "| 指标 | 当前值 |", "| --- | ---: |"])
    for key, value in (report.get("before_after") or {}).items():
        lines.append(f"| {key} | {value} |")
    resource = report.get("resource_state") or {}
    mysql = resource.get("mysql") or {}
    mysql_backup = resource.get("mysql_backup") or {}
    mysql_backup_verification = resource.get("mysql_backup_verification") or {}
    deploy_backups = resource.get("deploy_backups") or {}
    worker = report.get("worker_state") or {}
    lines.extend(
        [
            "",
            "## 资源与 MySQL 状态",
            "",
            f"- binlog_expire_logs_seconds：`{mysql.get('binlog_expire_logs_seconds')}`",
            f"- max_binlog_size：`{mysql.get('max_binlog_size')}`",
            f"- binary_log_count：`{mysql.get('binary_log_count')}`",
            f"- binary_log_total_bytes：`{mysql.get('binary_log_total_bytes')}`",
            f"- slow_log_bytes：`{mysql.get('slow_log_bytes')}`",
            f"- MySQL 备份数量：`{mysql_backup.get('count')}`",
            f"- MySQL 最新备份：`{(mysql_backup.get('latest') or {}).get('path')}`",
            f"- MySQL 备份校验报告：`{mysql_backup_verification.get('report')}`",
            f"- MySQL 备份 gzip 完整：`{mysql_backup_verification.get('gzip_ok')}`",
            f"- MySQL 备份 SQL 特征：`{mysql_backup_verification.get('sql_signature_ok')}`",
            f"- MySQL 备份 sha256：`{mysql_backup_verification.get('sha256')}`",
            f"- 部署归档数量：`{deploy_backups.get('count')}`",
            "",
            "## Worker 降载状态",
            "",
            f"- MySQL max_connections：`{(worker.get('mysql') or {}).get('max_connections')}`",
            f"- Threads_connected：`{(worker.get('mysql') or {}).get('threads_connected')}`",
            f"- Pool budget：`{(worker.get('pool_budget') or {}).get('total')}`",
        ]
    )
    manifest = report.get("parquet_manifest_state") or {}
    lines.extend(
        [
            "",
            "## Parquet Manifest 状态",
            "",
            f"- ready_count：`{manifest.get('ready_count')}`",
            f"- missing_count：`{manifest.get('missing_count')}`",
            f"- blocked_count：`{manifest.get('blocked_count')}`",
            f"- verified_files：`{manifest.get('verified_files')}`",
            f"- blocked_datasets：{', '.join(manifest.get('blocked_datasets') or []) or '无'}",
            "",
            "## 回滚方式",
            "",
        ]
    )
    for item in report.get("rollback") or []:
        lines.append(f"- {item}")
    online = report.get("online_performance_state") or {}
    online_p95 = online.get("api_p95_ms") or {}
    lines.extend(
        [
            "",
            "## 线上性能状态",
            "",
            f"- 报告：`{online.get('report')}`",
            f"- ok：`{online.get('ok')}`",
            f"- failures：`{online.get('failures')}`",
            f"- readyz p95：`{online_p95.get('readyz')}` ms",
            f"- monitor_bff p95：`{online_p95.get('monitor_bff')}` ms",
            f"- market_pulse p95：`{online_p95.get('market_pulse')}` ms",
            f"- priority_board p95：`{online_p95.get('priority_board')}` ms",
            f"- watchlist_signals p95：`{online_p95.get('watchlist_signals')}` ms",
        ]
    )
    audit = report.get("completion_audit") or {}
    lines.extend(
        [
            "",
            "## 完成度审计",
            "",
            f"- 报告：`{audit.get('path')}`",
            f"- 状态：`{audit.get('status')}`",
            f"- 汇总：`{audit.get('summary')}`",
        ]
    )
    lines.extend(["", "## Cutover 前必须补齐", ""])
    for item in report.get("required_before_cutover") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 未完成项", ""])
    for item in report.get("open_items") or []:
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
    parser = argparse.ArgumentParser(description="Render platform resource optimization acceptance draft.")
    parser.add_argument("--resource-report", type=Path, default=DEFAULT_RESOURCE_REPORT)
    parser.add_argument("--budget-report", type=Path, default=DEFAULT_BUDGET_REPORT)
    parser.add_argument("--manifest-report", type=Path, default=DEFAULT_MANIFEST_REPORT)
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS_REPORT)
    parser.add_argument("--maintenance-plan", type=Path, default=DEFAULT_MAINTENANCE_PLAN)
    parser.add_argument("--chunk-profile", type=Path, default=DEFAULT_CHUNK_PROFILE)
    parser.add_argument("--completion-audit", type=Path, default=DEFAULT_COMPLETION_AUDIT)
    parser.add_argument("--cloud-performance-report", type=Path, default=DEFAULT_CLOUD_PERFORMANCE)
    parser.add_argument("--backup-verification-report", type=Path, default=DEFAULT_BACKUP_VERIFICATION)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    chunk_profile = load_json(args.chunk_profile) if args.chunk_profile.exists() else {}
    completion_audit = load_json(args.completion_audit) if args.completion_audit.exists() else {}
    cloud_performance = load_json(args.cloud_performance_report) if args.cloud_performance_report.exists() else {}
    backup_verification = load_json(args.backup_verification_report) if args.backup_verification_report.exists() else {}
    report = build_acceptance(
        resource_report=load_json(args.resource_report),
        budget_report=load_json(args.budget_report),
        manifest_report=load_json(args.manifest_report),
        readiness_report=load_json(args.readiness_report),
        maintenance_plan=load_json(args.maintenance_plan),
        chunk_profile=chunk_profile,
        completion_audit=completion_audit,
        cloud_performance=cloud_performance,
        cloud_performance_report_path=args.cloud_performance_report,
        backup_verification=backup_verification,
    )
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps({"status": report["status"], "open_items": len(report["open_items"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
