#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ANALYTICS_ROOT = "/var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics"
DEFAULT_TASK_OUTPUT_ROOT = "/app/backend/data/analytics"


@dataclass(frozen=True)
class ExportSpec:
    dataset_key: str
    task_type: str
    window_key: str
    window_value: int
    source_table: str
    owner_role: str


EXPORT_SPECS: dict[str, ExportSpec] = {
    "daily_bars": ExportSpec(
        dataset_key="daily_bars",
        task_type="analytics_export_daily_bars",
        window_key="months",
        window_value=24,
        source_table="daily_bar_snapshots",
        owner_role="data",
    ),
    "strategy_tracking_snapshots": ExportSpec(
        dataset_key="strategy_tracking_snapshots",
        task_type="analytics_export_strategy_tracking_snapshots",
        window_key="days",
        window_value=90,
        source_table="strategy_tracking_snapshots",
        owner_role="quant",
    ),
    "key_level_snapshots": ExportSpec(
        dataset_key="key_level_snapshots",
        task_type="analytics_export_key_level_snapshots",
        window_key="days",
        window_value=90,
        source_table="a_key_level_snapshots",
        owner_role="data",
    ),
    "low_buy_result_snapshots": ExportSpec(
        dataset_key="low_buy_result_snapshots",
        task_type="analytics_export_low_buy_result_snapshots",
        window_key="days",
        window_value=90,
        source_table="low_buy_result_snapshots",
        owner_role="quant",
    ),
    "backtest_runs": ExportSpec(
        dataset_key="backtest_runs",
        task_type="analytics_export_backtest_runs",
        window_key="days",
        window_value=180,
        source_table="backtest_runs",
        owner_role="quant",
    ),
    "backtest_trades": ExportSpec(
        dataset_key="backtest_trades",
        task_type="analytics_export_backtest_trades",
        window_key="days",
        window_value=180,
        source_table="backtest_trades",
        owner_role="quant",
    ),
    "backtest_daily_snapshots": ExportSpec(
        dataset_key="backtest_daily_snapshots",
        task_type="analytics_export_backtest_daily_snapshots",
        window_key="days",
        window_value=180,
        source_table="backtest_daily_snapshots",
        owner_role="quant",
    ),
    "analysis_logs": ExportSpec(
        dataset_key="analysis_logs",
        task_type="analytics_export_analysis_logs",
        window_key="days",
        window_value=90,
        source_table="analysis_logs",
        owner_role="quant",
    ),
    "market_review_reports": ExportSpec(
        dataset_key="market_review_reports",
        task_type="analytics_export_market_review_reports",
        window_key="days",
        window_value=90,
        source_table="market_review_reports",
        owner_role="quant",
    ),
    "paper_review_reports": ExportSpec(
        dataset_key="paper_review_reports",
        task_type="analytics_export_paper_review_reports",
        window_key="days",
        window_value=90,
        source_table="paper_review_reports",
        owner_role="quant",
    ),
}


def load_manifest_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_export_plan(
    manifest_report: dict[str, Any],
    *,
    analytics_root: str,
    task_output_root: str,
    end_date: str,
) -> dict[str, Any]:
    datasets = normalize_datasets(manifest_report.get("datasets") or {})
    actions = []
    for dataset_key, spec in EXPORT_SPECS.items():
        item = datasets.get(dataset_key, {"dataset_key": dataset_key, "present": False, "blockers": ["manifest_missing"]})
        action = classify_dataset_action(item)
        actions.append(
            build_dataset_action(spec, item, action, output_root=task_output_root, end_date=end_date)
        )

    summary = summarize_actions(actions)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest_report": manifest_report.get("source_manifest_report") or manifest_report.get("report_path"),
        "analytics_root": analytics_root,
        "task_output_root": task_output_root,
        "end_date": end_date,
        "dry_run_only": True,
        "safety": {
            "does_enqueue_tasks": False,
            "does_run_exporters": False,
            "does_modify_mysql": False,
            "does_clean_source_tables": False,
            "requires_operator_window": True,
            "post_export_verify_required": True,
        },
        "summary": summary,
        "actions": actions,
        "post_verify": {
            "command": (
                "python3 scripts/verify_analytics_manifests.py "
                f"--analytics-root {analytics_root} "
                "--json-output docs/reports/platform-analytics-manifests-2026-06-08.json "
                "--markdown-output docs/reports/platform-analytics-manifests-2026-06-08.md"
            ),
            "required_before_mysql_retention": True,
        },
        "evaluation": {
            "status": "blocking" if summary["export_required_count"] or summary["reexport_required_count"] else "warning"
            if summary["optional_refresh_count"]
            else "ok",
            "blocking": build_blocking(summary),
            "warnings": build_warnings(summary),
        },
    }


def normalize_datasets(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict):
        return {str(key): dict(value or {}) for key, value in raw.items() if isinstance(value, dict)}
    if isinstance(raw, list):
        result: dict[str, dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = str(item.get("dataset_key") or item.get("dataset") or "")
            if key:
                result[key] = dict(item)
        return result
    return {}


def classify_dataset_action(item: dict[str, Any]) -> str:
    blockers = [str(value) for value in (item.get("blockers") or [])]
    warnings = item.get("warnings") or []
    if not item.get("present") or "manifest_missing" in blockers:
        return "export_required"
    if any(token.startswith("artifact_hash_mismatch") or token.startswith("artifact_file_missing") for token in blockers):
        return "reexport_required"
    if blockers:
        return "manual_investigation_required"
    if warnings:
        return "lifecycle_refresh_optional"
    return "ready"


def build_dataset_action(
    spec: ExportSpec,
    item: dict[str, Any],
    action: str,
    *,
    output_root: str,
    end_date: str,
) -> dict[str, Any]:
    payload = {
        spec.window_key: spec.window_value,
        "end_date": end_date,
        "output_root": output_root,
        "source": "platform_analytics_manifest_export_plan",
        "idempotency_key": f"analytics-export:{spec.dataset_key}:{end_date}",
    }
    base = {
        "dataset_key": spec.dataset_key,
        "action": action,
        "task_type": spec.task_type,
        "worker": "analytics",
        "priority": "low",
        "owner_role": spec.owner_role,
        "source_table": item.get("source_table") or spec.source_table,
        "window": {spec.window_key: spec.window_value, "end_date": end_date},
        "manifest_present": bool(item.get("present")),
        "row_count": int(item.get("row_count") or 0),
        "quality_status": str(item.get("quality_status") or item.get("status") or ""),
        "warnings": list(item.get("warnings") or []),
        "blockers": list(item.get("blockers") or []),
        "payload": payload,
        "safe_to_auto_execute": False,
        "operator_steps": operator_steps(spec, payload, action),
    }
    if action in {"export_required", "reexport_required"}:
        base["readiness"] = "needs_analytics_worker_window"
    elif action == "manual_investigation_required":
        base["readiness"] = "needs_manual_manifest_fix"
    else:
        base["readiness"] = "no_required_export"
    return base


def operator_steps(spec: ExportSpec, payload: dict[str, Any], action: str) -> list[str]:
    if action == "ready":
        return ["无需导出；保留 manifest hash 复验证据。"]
    if action == "lifecycle_refresh_optional":
        return ["可在低峰期重新导出以刷新 manifest lifecycle 字段；不是 MySQL 清理前的阻断项。"]
    if action == "manual_investigation_required":
        return ["先人工检查 manifest JSON、dataset_key、日期窗口和文件路径，再决定是否重跑导出。"]
    return [
        f"在低峰期提交 analytics worker 任务 `{spec.task_type}`，payload 使用本报告中的 JSON。",
        "任务完成后复跑 `scripts/verify_analytics_manifests.py`，确认 manifest、文件存在性和 sha256。",
        "只有所有相关 manifest 复验无 blocking 后，才允许进入热库保留窗口 dry-run；仍不得自动清理 MySQL 源数据。",
    ]


def summarize_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "dataset_count": len(actions),
        "ready_count": sum(1 for item in actions if item["action"] in {"ready", "lifecycle_refresh_optional"}),
        "optional_refresh_count": count_action(actions, "lifecycle_refresh_optional"),
        "export_required_count": count_action(actions, "export_required"),
        "reexport_required_count": count_action(actions, "reexport_required"),
        "manual_investigation_count": count_action(actions, "manual_investigation_required"),
        "required_task_count": sum(1 for item in actions if item["action"] in {"export_required", "reexport_required"}),
        "required_tasks": [item["task_type"] for item in actions if item["action"] in {"export_required", "reexport_required"}],
        "blocked_datasets": [
            item["dataset_key"]
            for item in actions
            if item["action"] in {"export_required", "reexport_required", "manual_investigation_required"}
        ],
    }


def count_action(actions: list[dict[str, Any]], action: str) -> int:
    return sum(1 for item in actions if item["action"] == action)


def build_blocking(summary: dict[str, Any]) -> list[str]:
    blocking = []
    if summary["export_required_count"]:
        blocking.append(f"manifest_export_required_count={summary['export_required_count']}")
    if summary["reexport_required_count"]:
        blocking.append(f"manifest_reexport_required_count={summary['reexport_required_count']}")
    if summary["manual_investigation_count"]:
        blocking.append(f"manifest_manual_investigation_count={summary['manual_investigation_count']}")
    return blocking


def build_warnings(summary: dict[str, Any]) -> list[str]:
    warnings = []
    if summary["optional_refresh_count"]:
        warnings.append(f"manifest_optional_refresh_count={summary['optional_refresh_count']}")
    return warnings


def render_markdown(plan: dict[str, Any]) -> str:
    evaluation = plan.get("evaluation", {})
    summary = plan.get("summary", {})
    lines = [
        "# Analytics Manifest 导出计划",
        "",
        f"- 生成时间：`{plan.get('generated_at', '')}`",
        f"- Analytics root：`{plan.get('analytics_root', '')}`",
        f"- Task output root：`{plan.get('task_output_root', '')}`",
        f"- 截止日期：`{plan.get('end_date', '')}`",
        f"- 状态：`{evaluation.get('status', 'unknown')}`",
        "- 安全边界：dry-run 报告；不 enqueue、不执行 exporter、不修改 MySQL、不清源表。",
        "",
        "## 汇总",
        "",
        "| 指标 | 当前值 |",
        "| --- | ---: |",
        f"| 数据集数量 | {summary.get('dataset_count', 0)} |",
        f"| ready | {summary.get('ready_count', 0)} |",
        f"| optional refresh | {summary.get('optional_refresh_count', 0)} |",
        f"| export required | {summary.get('export_required_count', 0)} |",
        f"| reexport required | {summary.get('reexport_required_count', 0)} |",
        f"| manual investigation | {summary.get('manual_investigation_count', 0)} |",
        f"| required tasks | {summary.get('required_task_count', 0)} |",
        "",
        "## 数据集计划",
        "",
        "| Dataset | Action | Task | Window | Source | Blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in plan.get("actions") or []:
        window = item.get("window") or {}
        window_text = ", ".join(f"{key}={value}" for key, value in window.items())
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("dataset_key", "")),
                    str(item.get("action", "")),
                    str(item.get("task_type", "")),
                    window_text,
                    str(item.get("source_table", "")),
                    ", ".join(item.get("blockers") or []) or "-",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 执行说明",
            "",
            "本报告只把 manifest 复验结果转成低优先级 analytics worker 任务计划；需要运维窗口或任务系统另行提交。任务完成后必须复跑 manifest 复验，所有相关数据集无 blocking 前，不能执行 MySQL 热库保留窗口清理。",
            "",
            "复验命令：",
            "",
            "```bash",
            str((plan.get("post_verify") or {}).get("command") or ""),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(plan: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(plan), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan analytics manifest exports without executing them.")
    parser.add_argument("--manifest-report", type=Path, required=True)
    parser.add_argument("--analytics-root", default=DEFAULT_ANALYTICS_ROOT)
    parser.add_argument("--task-output-root", default=DEFAULT_TASK_OUTPUT_ROOT)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-blocking", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = load_manifest_report(args.manifest_report)
    source["report_path"] = str(args.manifest_report)
    plan = build_export_plan(
        source,
        analytics_root=str(args.analytics_root),
        task_output_root=str(args.task_output_root),
        end_date=str(args.end_date)[:10],
    )
    write_outputs(plan, args.json_output, args.markdown_output)
    print(json.dumps(plan["evaluation"], ensure_ascii=False))
    if args.fail_on_blocking and plan["evaluation"]["blocking"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
