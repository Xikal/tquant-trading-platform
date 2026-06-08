#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


REQUIRED_ACTIONS = {"export_required", "reexport_required"}


def load_export_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def selectable_actions(plan: dict[str, Any], *, include_optional_refresh: bool = False) -> list[dict[str, Any]]:
    allowed = set(REQUIRED_ACTIONS)
    if include_optional_refresh:
        allowed.add("lifecycle_refresh_optional")
    actions = []
    for item in plan.get("actions") or []:
        if not isinstance(item, dict):
            continue
        if item.get("action") in allowed:
            actions.append(item)
    return actions


def filter_actions(actions: list[dict[str, Any]], datasets: set[str], task_types: set[str]) -> list[dict[str, Any]]:
    output = []
    for item in actions:
        if datasets and str(item.get("dataset_key") or "") not in datasets:
            continue
        if task_types and str(item.get("task_type") or "") not in task_types:
            continue
        output.append(item)
    return output


def build_submission_plan(
    export_plan: dict[str, Any],
    *,
    include_optional_refresh: bool = False,
    datasets: set[str] | None = None,
    task_types: set[str] | None = None,
    priority: int = 900,
    max_attempts: int = 1,
    apply: bool = False,
) -> dict[str, Any]:
    actions = selectable_actions(export_plan, include_optional_refresh=include_optional_refresh)
    actions = filter_actions(actions, datasets or set(), task_types or set())
    tasks = []
    for item in actions:
        payload = dict(item.get("payload") or {})
        idempotency_key = str(payload.get("idempotency_key") or f"analytics-export:{item.get('dataset_key')}")
        tasks.append(
            {
                "dataset_key": item.get("dataset_key"),
                "action": item.get("action"),
                "task_type": item.get("task_type"),
                "priority": priority,
                "max_attempts": max_attempts,
                "idempotency_key": idempotency_key,
                "payload": payload,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_export_plan": export_plan.get("source_export_plan") or "",
        "mode": "apply" if apply else "dry-run",
        "safety": {
            "dry_run_default": True,
            "requires_apply_flag": True,
            "requires_confirm_apply": True,
            "does_run_exporters": False,
            "does_clean_source_tables": False,
            "does_modify_mysql_source_tables": False,
            "writes_runtime_tasks_only_when_apply": bool(apply),
        },
        "summary": {
            "selected_task_count": len(tasks),
            "selected_datasets": [str(item["dataset_key"]) for item in tasks],
            "selected_task_types": [str(item["task_type"]) for item in tasks],
        },
        "tasks": tasks,
        "evaluation": {
            "status": "ready_to_submit" if tasks else "empty",
            "warnings": [] if tasks else ["no_tasks_selected"],
            "blocking": [],
        },
    }


def submit_tasks(submission_plan: dict[str, Any], enqueue_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    submitted = []
    for task in submission_plan.get("tasks") or []:
        submitted.append(enqueue_fn(task))
    submission_plan["submitted"] = submitted
    submission_plan["summary"]["submitted_task_count"] = len(submitted)
    submission_plan["evaluation"]["status"] = "submitted"
    return submission_plan


def enqueue_runtime_task(task: dict[str, Any]) -> dict[str, Any]:
    from app.core.database import SessionLocal
    from app.models.schema_defs.phase4 import RuntimeTaskCreate
    from app.services.tasks import RuntimeTaskQueue

    with SessionLocal() as db:
        queued = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type=str(task["task_type"]),
                payload=dict(task.get("payload") or {}),
                priority=int(task.get("priority") or 900),
                idempotency_key=str(task.get("idempotency_key") or ""),
                max_attempts=int(task.get("max_attempts") or 1),
            )
        )
        return {
            "dataset_key": task.get("dataset_key"),
            "task_type": queued.task_type,
            "task_id": queued.id,
            "status": queued.status,
            "idempotency_key": task.get("idempotency_key"),
        }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Analytics Manifest 导出任务提交预览",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 模式：`{report.get('mode', 'dry-run')}`",
        "- 安全边界：默认 dry-run；不执行 exporter；不清 MySQL 源表；apply 模式只写 runtime task 队列。",
        "",
        "## 汇总",
        "",
        "| 指标 | 当前值 |",
        "| --- | ---: |",
        f"| selected tasks | {(report.get('summary') or {}).get('selected_task_count', 0)} |",
        f"| submitted tasks | {(report.get('summary') or {}).get('submitted_task_count', 0)} |",
        "",
        "## 任务",
        "",
        "| Dataset | Action | Task | Priority | Idempotency |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for task in report.get("tasks") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(task.get("dataset_key") or ""),
                    str(task.get("action") or ""),
                    str(task.get("task_type") or ""),
                    str(task.get("priority") or ""),
                    str(task.get("idempotency_key") or ""),
                ]
            )
            + " |"
        )
    if report.get("submitted"):
        lines.extend(["", "## 已提交", "", "| Dataset | Task | ID | Status |", "| --- | --- | ---: | --- |"])
        for item in report.get("submitted") or []:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item.get("dataset_key") or ""),
                        str(item.get("task_type") or ""),
                        str(item.get("task_id") or ""),
                        str(item.get("status") or ""),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def parse_csv(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit analytics manifest export tasks from a reviewed plan.")
    parser.add_argument("--export-plan", type=Path, required=True)
    parser.add_argument("--datasets", help="Comma separated dataset keys to submit.")
    parser.add_argument("--task-types", help="Comma separated task types to submit.")
    parser.add_argument("--include-optional-refresh", action="store_true")
    parser.add_argument("--priority", type=int, default=900)
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-apply", default="")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    export_plan = load_export_plan(args.export_plan)
    export_plan["source_export_plan"] = str(args.export_plan)
    report = build_submission_plan(
        export_plan,
        include_optional_refresh=bool(args.include_optional_refresh),
        datasets=parse_csv(args.datasets),
        task_types=parse_csv(args.task_types),
        priority=int(args.priority),
        max_attempts=int(args.max_attempts),
        apply=bool(args.apply),
    )
    if args.apply:
        if args.confirm_apply != "submit-analytics-manifest-exports":
            report["evaluation"] = {
                "status": "blocked",
                "warnings": [],
                "blocking": ["confirm_apply_required"],
            }
            write_outputs(report, args.json_output, args.markdown_output)
            print(json.dumps(report["evaluation"], ensure_ascii=False))
            return 64
        report = submit_tasks(report, enqueue_runtime_task)
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report["evaluation"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
