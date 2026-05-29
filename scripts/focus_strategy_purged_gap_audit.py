#!/usr/bin/env python3
"""Audit focused strategy walk-forward windows for temporal and purged-gap evidence."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = "2026-05-28"
PURGED_GAP_DAYS = 10
SQLITE_DB_URL = "sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db"
SCOPES = {
    "combined_first_board_volume_shrink": "matrix-windows",
    "first_board": "strategy-matrix-windows/first_board",
    "volume_shrink": "strategy-matrix-windows/volume_shrink",
}


def build_report(*, report_date: str = REPORT_DATE, root: Path = ROOT) -> dict[str, Any]:
    base = root / "docs" / "reports" / f"focus-strategy-parameter-walk-forward-{report_date}"
    scopes = [_scope_audit(scope_key, base / rel_dir, root=root) for scope_key, rel_dir in SCOPES.items()]
    window_count = sum(item["window_count"] for item in scopes)
    missing_temporal = [item["scope_key"] for item in scopes if not item["temporal_order_passed"]]
    rerun_manifest = _rerun_manifest(scopes, report_date=report_date, root=root)
    rerun_smoke = _rerun_smoke(report_date=report_date, root=root, manifest=rerun_manifest)
    rerun_full = _rerun_full(report_date=report_date, root=root, manifest=rerun_manifest)
    if rerun_full["complete"]:
        rerun_manifest["status"] = "executed_complete"
    elif rerun_full["executed_or_existing_count"] > 0:
        rerun_manifest["status"] = "partially_executed"
    daily_data_coverage = _daily_data_coverage(scopes, root=root)
    return {
        "title": "P1 重点策略矩阵 purged-gap 审计",
        "report_date": report_date,
        "source_dir": str(base.relative_to(root)),
        "status": "partial_oos_evidence_purged_gap_not_proven",
        "production_ready": False,
        "purged_gap_days_required": PURGED_GAP_DAYS,
        "total_matrix_window_count": window_count,
        "temporal_order_passed": not missing_temporal and window_count >= 21,
        "explicit_train_validation_split_present": all(item["explicit_train_validation_split_present"] for item in scopes) or rerun_full.get("explicit_train_validation_split_present") is True,
        "proposed_split_plan_present": all(item["proposed_split_plan_present"] for item in scopes),
        "explicit_purged_gap_encoded": all(item["explicit_purged_gap_encoded"] for item in scopes) or rerun_full.get("explicit_purged_gap_encoded") is True,
        "purged_gap_passed": False,
        "purged_gap_plan_ready": all(item["purged_gap_plan_ready"] for item in scopes),
        "production_blockers": [
            *([] if all(item["explicit_train_validation_split_present"] for item in scopes) or rerun_full.get("explicit_train_validation_split_present") is True else ["explicit_train_validation_split_missing"]),
            *([] if all(item["explicit_purged_gap_encoded"] for item in scopes) or rerun_full.get("explicit_purged_gap_encoded") is True else ["purged_gap_not_encoded_in_source_matrices"]),
            *(["execution_matrix_coverage_partial_only"] if rerun_full.get("partial_coverage_only") else []),
            "online_shadow_settled_sample_lt_required",
        ],
        "scopes": scopes,
        "daily_data_coverage": daily_data_coverage,
        "rerun_manifest": rerun_manifest,
        "rerun_smoke": rerun_smoke,
        "rerun_full": rerun_full,
    }


def write_report(report: dict[str, Any], root: Path = ROOT) -> tuple[Path, Path]:
    out_dir = root / "docs" / "reports" / f"focus-strategy-purged-gap-audit-{report['report_date']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"- 报告日期：{report['report_date']}",
        f"- 状态：{report['status']}",
        f"- 矩阵窗口：{report['total_matrix_window_count']}",
        f"- 时间顺序通过：{'是' if report['temporal_order_passed'] else '否'}",
        f"- 显式训练/验证切分：{'是' if report['explicit_train_validation_split_present'] else '否'}",
        f"- 建议切分计划：{'是' if report['proposed_split_plan_present'] else '否'}",
        f"- purged-gap 已编码/通过：{'是' if report['explicit_purged_gap_encoded'] else '否'} / {'是' if report['purged_gap_passed'] else '否'}",
        f"- purged-gap 计划可执行：{'是' if report['purged_gap_plan_ready'] else '否'}",
        f"- 生产可用：{'是' if report['production_ready'] else '否'}",
        "",
        "| 范围 | 窗口 | 起始 | 结束 | 时间顺序 | 缺口 |",
        "|---|---:|---|---|---|---|",
    ]
    for row in report["scopes"]:
        lines.append(
            f"| {row['scope_key']} | {row['window_count']} | {row['first_oos_start']} | {row['last_oos_end']} | "
            f"{'是' if row['temporal_order_passed'] else '否'} | {', '.join(row['missing_for_production'])} |"
        )
    lines.extend(["", "## 生产阻断", ""])
    lines.extend(f"- {item}" for item in report["production_blockers"])
    lines.extend(["", "## 复跑清单", ""])
    lines.append(f"- 状态：{report['rerun_manifest']['status']}")
    lines.append(f"- 命令数：{report['rerun_manifest']['command_count']}")
    lines.append(f"- 输出目录：`{report['rerun_manifest']['output_dir']}`")
    lines.append(f"- 数据库：`{report['rerun_manifest'].get('database_url', '')}`")
    coverage = report.get("daily_data_coverage") or {}
    lines.extend(["", "## 本地日线覆盖", ""])
    lines.append(f"- 状态：{coverage.get('status', '')}")
    lines.append(f"- 日期范围：{coverage.get('first_trade_date', '')} 至 {coverage.get('last_trade_date', '')}")
    lines.append(f"- 覆盖窗口：{coverage.get('covered_window_count', 0)} / {coverage.get('manifest_window_count', 0)}")
    lines.append(f"- 单窗口交易日：{coverage.get('min_window_trade_dates', 0)} 至 {coverage.get('max_window_trade_dates', 0)}")
    smoke = report.get("rerun_smoke") or {}
    lines.extend(["", "## 复跑 smoke", ""])
    lines.append(f"- 状态：{smoke.get('status', '')}")
    lines.append(f"- 输出结构通过：{'是' if smoke.get('output_structure_passed') else '否'}")
    lines.append(f"- 有效样本：{'是' if smoke.get('data_sample_available') else '否'}")
    lines.append(f"- 矩阵文件：{smoke.get('matrix_count', 0)}")
    lines.append(f"- 评估样本：{smoke.get('total_evaluated_count', 0)}")
    lines.append(f"- 成交样本：{smoke.get('total_filled_count', 0)}")
    lines.append(f"- 覆盖状态：{', '.join(smoke.get('coverage_statuses') or [])}")
    lines.append(f"- 仍为部分覆盖：{'是' if smoke.get('partial_coverage_only') else '否'}")
    if smoke.get("reason"):
        lines.append(f"- 说明：{smoke['reason']}")
    full = report.get("rerun_full") or {}
    lines.extend(["", "## 全量复跑", ""])
    lines.append(f"- 状态：{full.get('status', '')}")
    lines.append(f"- 完成：{'是' if full.get('complete') else '否'}")
    lines.append(f"- 矩阵文件：{full.get('matrix_count', 0)} / {full.get('expected_manifest_command_count', 0)}")
    lines.append(f"- 评估样本：{full.get('total_evaluated_count', 0)}")
    lines.append(f"- 成交样本：{full.get('total_filled_count', 0)}")
    lines.append(f"- 覆盖状态：{', '.join(full.get('coverage_statuses') or [])}")
    lines.append(f"- 仍为部分覆盖：{'是' if full.get('partial_coverage_only') else '否'}")
    return "\n".join(lines) + "\n"


def _scope_audit(scope_key: str, source_dir: Path, *, root: Path) -> dict[str, Any]:
    windows = [_window_row(path, root=root) for path in sorted(source_dir.glob("*.json"))]
    starts = [item["oos_start"] for item in windows if item["oos_start"]]
    ends = [item["oos_end"] for item in windows if item["oos_end"]]
    ordered = all(starts[index] < starts[index + 1] for index in range(len(starts) - 1))
    return {
        "scope_key": scope_key,
        "source_dir": str(source_dir.relative_to(root)),
        "window_count": len(windows),
        "first_oos_start": starts[0] if starts else "",
        "last_oos_end": ends[-1] if ends else "",
        "temporal_order_passed": len(windows) >= 7 and ordered,
        "explicit_train_validation_split_present": all(item["train_start"] and item["validation_start"] for item in windows),
        "explicit_purged_gap_encoded": all(item["split_plan_encoded"] and item["purged_gap_temporal_order_passed"] for item in windows),
        "proposed_split_plan_present": all(item["proposed_train_start"] for item in windows),
        "purged_gap_passed": False,
        "purged_gap_plan_ready": all(item["proposed_gap_days"] >= PURGED_GAP_DAYS for item in windows),
        "missing_for_production": [
            "explicit_train_validation_split_missing",
            "purged_gap_not_encoded_in_source_matrices",
            "online_shadow_settled_sample_lt_required",
        ],
        "windows": windows,
    }


def _window_row(path: Path, *, root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scope = payload.get("scope") or {}
    rows = payload.get("rows") or []
    first_row = rows[0] if rows else {}
    start = first_row.get("evaluation_start") or scope.get("start") or ""
    end = first_row.get("evaluation_end") or scope.get("end") or ""
    proposed = _proposed_split(start)
    return {
        "source_path": str(path.relative_to(root)),
        "oos_start": start,
        "oos_end": end,
        "oos_start_ordinal": _ordinal(start),
        "oos_end_ordinal": _ordinal(end),
        "train_start": scope.get("train_start") or "",
        "train_end": scope.get("train_end") or "",
        "validation_start": scope.get("validation_start") or "",
        "validation_end": scope.get("validation_end") or "",
        "purged_gap_start": scope.get("purged_gap_start") or "",
        "purged_gap_end": scope.get("purged_gap_end") or "",
        "split_plan_encoded": scope.get("split_plan_encoded") is True,
        "purged_gap_temporal_order_passed": scope.get("purged_gap_temporal_order_passed") is True,
        **proposed,
        "variant_count": len(rows),
        "materialization_mode": scope.get("materialization_mode") or "",
    }


def _ordinal(value: str) -> int | None:
    if not value:
        return None
    return date.fromisoformat(value).toordinal()


def _proposed_split(oos_start: str) -> dict[str, Any]:
    if not oos_start:
        return {
            "proposed_train_start": "",
            "proposed_train_end": "",
            "proposed_validation_start": "",
            "proposed_validation_end": "",
            "proposed_purged_gap_start": "",
            "proposed_purged_gap_end": "",
            "proposed_gap_days": 0,
        }
    oos = date.fromisoformat(oos_start)
    gap_start = oos - timedelta(days=PURGED_GAP_DAYS)
    validation_end = gap_start - timedelta(days=1)
    validation_start = validation_end - timedelta(days=59)
    train_end = validation_start - timedelta(days=1)
    train_start = train_end - timedelta(days=364)
    return {
        "proposed_train_start": train_start.isoformat(),
        "proposed_train_end": train_end.isoformat(),
        "proposed_validation_start": validation_start.isoformat(),
        "proposed_validation_end": validation_end.isoformat(),
        "proposed_purged_gap_start": gap_start.isoformat(),
        "proposed_purged_gap_end": (oos - timedelta(days=1)).isoformat(),
        "proposed_gap_days": PURGED_GAP_DAYS,
    }


def _rerun_manifest(scopes: list[dict[str, Any]], *, report_date: str, root: Path) -> dict[str, Any]:
    output_dir = root / "docs" / "reports" / f"focus-strategy-purged-gap-rerun-{report_date}" / "matrix-windows"
    rel_output_dir = output_dir.relative_to(root)
    commands = []
    for scope in scopes:
        for index, window in enumerate(scope["windows"], start=1):
            commands.append(
                {
                    "scope_key": scope["scope_key"],
                    "window_id": index,
                    "train_start": window["proposed_train_start"],
                    "train_end": window["proposed_train_end"],
                    "validation_start": window["proposed_validation_start"],
                    "validation_end": window["proposed_validation_end"],
                    "purged_gap_start": window["proposed_purged_gap_start"],
                    "purged_gap_end": window["proposed_purged_gap_end"],
                    "oos_start": window["oos_start"],
                    "oos_end": window["oos_end"],
                    "command": _rerun_command(scope["scope_key"], window, rel_output_dir),
                }
            )
    return {
        "status": "ready_not_executed",
        "command_count": len(commands),
        "output_dir": str(output_dir.relative_to(root)),
        "variants": ["default_exit", "quick_tp3_trailing1"],
        "database_url": SQLITE_DB_URL,
        "commands": commands,
        "execution_policy": "Run manually or in batches with the pinned SQLite DATABASE_URL; generated commands do not write production parameters.",
    }


def _daily_data_coverage(scopes: list[dict[str, Any]], *, root: Path) -> dict[str, Any]:
    db_path = Path(SQLITE_DB_URL.replace("sqlite:///", "", 1))
    if not db_path.exists():
        return {
            "status": "missing_database",
            "database_url": SQLITE_DB_URL,
            "database_path": str(db_path),
            "manifest_window_count": sum(len(item["windows"]) for item in scopes),
            "covered_window_count": 0,
        }
    rows: list[tuple[str, int]] = []
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        summary = cursor.execute(
            "select count(distinct trade_date), min(trade_date), max(trade_date) from daily_bar_snapshots"
        ).fetchone()
        stock_counts = dict(
            cursor.execute(
                "select trade_date, count(distinct symbol) from daily_bar_snapshots group by trade_date"
            ).fetchall()
        )
        for scope in scopes:
            for window in scope["windows"]:
                count = cursor.execute(
                    "select count(distinct trade_date) from daily_bar_snapshots where trade_date >= ? and trade_date <= ?",
                    (window["oos_start"], window["oos_end"]),
                ).fetchone()[0]
                rows.append((f"{scope['scope_key']}#{len(rows) + 1}", int(count or 0)))
    total_dates, first_date, last_date = summary or (0, "", "")
    counts = [count for _, count in rows]
    return {
        "status": "covered" if rows and all(count > 0 for count in counts) else "partial_or_missing",
        "database_url": SQLITE_DB_URL,
        "database_path": str(db_path.relative_to(root)) if db_path.is_relative_to(root) else str(db_path),
        "total_trade_dates": int(total_dates or 0),
        "first_trade_date": str(first_date or ""),
        "last_trade_date": str(last_date or ""),
        "first_trade_date_stock_count": int(stock_counts.get(first_date, 0) or 0),
        "last_trade_date_stock_count": int(stock_counts.get(last_date, 0) or 0),
        "manifest_window_count": len(rows),
        "covered_window_count": sum(1 for count in counts if count > 0),
        "min_window_trade_dates": min(counts) if counts else 0,
        "max_window_trade_dates": max(counts) if counts else 0,
        "window_trade_dates": [{"window": key, "trade_dates": count} for key, count in rows],
    }


def _rerun_smoke(*, report_date: str, root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    smoke_dir = root / "docs" / "reports" / f"focus-strategy-purged-gap-rerun-{report_date}" / "smoke"
    files = sorted(smoke_dir.glob("*.json"))
    if not files:
        return {
            "status": "not_run",
            "source_dir": str(smoke_dir.relative_to(root)),
            "matrix_count": 0,
            "expected_manifest_command_count": manifest.get("command_count"),
            "full_manifest_executed": False,
            "output_structure_passed": False,
            "data_sample_available": False,
            "purged_gap_passed": False,
            "production_parameter_write": False,
            "reason": "Smoke rerun output was not found.",
        }

    expected_variants = set(manifest.get("variants") or [])
    variant_keys: set[str] = set()
    coverage_statuses: set[str] = set()
    total_evaluated = 0
    total_filled = 0
    production_write = False
    scopes: list[dict[str, Any]] = []
    warnings: list[str] = []
    source_files: list[str] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_files.append(str(path.relative_to(root)))
        scope = payload.get("scope") or {}
        rows = payload.get("rows") or []
        scopes.append(
            {
                "start": scope.get("start"),
                "end": scope.get("end"),
                "strategies": scope.get("strategies"),
                "states": scope.get("states"),
                "engine": scope.get("engine"),
                "materialization_mode": scope.get("materialization_mode"),
            }
        )
        if scope.get("materialization_mode") == "production":
            production_write = True
        if payload.get("warning"):
            warnings.append(str(payload["warning"]))
        for row in rows:
            variant_keys.add(str(row.get("variant_key") or ""))
            coverage_statuses.add(str(row.get("coverage_status") or ""))
            total_evaluated += int(row.get("evaluated_count") or 0)
            total_filled += int(row.get("filled_count") or 0)

    mode_ok = bool(scopes) and all(item.get("materialization_mode") == "isolated" for item in scopes)
    output_ok = bool(files) and expected_variants.issubset(variant_keys) and mode_ok
    data_available = total_evaluated > 0
    status = "failed"
    reason = "Smoke output exists, but expected variants or isolated mode did not match."
    if output_ok and data_available:
        status = "executed_with_samples"
        reason = "Smoke command and output structure passed with evaluated samples."
    elif output_ok:
        status = "executed_empty_sample"
        reason = "Smoke command and output structure passed, but current local data produced zero evaluated samples."
    return {
        "status": status,
        "source_dir": str(smoke_dir.relative_to(root)),
        "source_files": source_files,
        "matrix_count": len(files),
        "expected_manifest_command_count": manifest.get("command_count"),
        "full_manifest_executed": len(files) >= int(manifest.get("command_count") or 0),
        "variant_keys": sorted(item for item in variant_keys if item),
        "coverage_statuses": sorted(item for item in coverage_statuses if item),
        "total_evaluated_count": total_evaluated,
        "total_filled_count": total_filled,
        "scope_samples": scopes,
        "warnings": sorted(set(warnings)),
        "output_structure_passed": output_ok,
        "data_sample_available": data_available,
        "partial_coverage_only": "partial" in coverage_statuses,
        "purged_gap_passed": False,
        "production_parameter_write": production_write,
        "reason": reason,
    }


def _rerun_full(*, report_date: str, root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    run_dir = root / "docs" / "reports" / f"focus-strategy-purged-gap-rerun-{report_date}"
    summary_path = run_dir / "run-summary.json"
    matrix_dir = run_dir / "matrix-windows"
    matrix_files = sorted(matrix_dir.glob("*.json"))
    run_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    expected_count = int(manifest.get("command_count") or 0)
    matrix_summary = _matrix_outputs_summary(matrix_files, root=root)
    complete = (
        run_summary.get("complete") is True
        and int(run_summary.get("executed_or_existing_count") or 0) == expected_count
        and len(matrix_files) == expected_count
    )
    if complete:
        status = "executed_complete"
        reason = "All manifest commands completed or were already present; outputs remain research-only evidence."
    elif run_summary or matrix_files:
        status = "partially_executed"
        reason = "Some rerun outputs exist, but the full manifest has not completed."
    else:
        status = "not_run"
        reason = "Full rerun output was not found."
    return {
        "status": status,
        "complete": complete,
        "source_dir": str(matrix_dir.relative_to(root)),
        "run_summary_path": str(summary_path.relative_to(root)),
        "expected_manifest_command_count": expected_count,
        "matrix_count": len(matrix_files),
        "executed_or_existing_count": int(run_summary.get("executed_or_existing_count") or 0),
        "passed_count": int(run_summary.get("passed_count") or 0),
        "skipped_existing_count": int(run_summary.get("skipped_existing_count") or 0),
        "failed_count": int(run_summary.get("failed_count") or 0),
        "seconds": float(run_summary.get("seconds") or 0.0),
        **matrix_summary,
        "output_structure_passed": complete and matrix_summary["expected_variants_present"],
        "data_sample_available": matrix_summary["total_evaluated_count"] > 0,
        "partial_coverage_only": "partial" in matrix_summary["coverage_statuses"],
        "purged_gap_passed": False,
        "production_parameter_write": False,
        "reason": reason,
    }


def _matrix_outputs_summary(files: list[Path], *, root: Path) -> dict[str, Any]:
    coverage_statuses: set[str] = set(); variant_keys: set[str] = set()
    encoded = ordered = 0
    total_evaluated = total_filled = 0
    min_evaluated: int | None = None
    max_evaluated = 0
    source_files: list[str] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        scope = payload.get("scope") or {}
        encoded += scope.get("split_plan_encoded") is True
        ordered += scope.get("purged_gap_temporal_order_passed") is True
        source_files.append(str(path.relative_to(root)))
        file_evaluated = 0
        for row in payload.get("rows") or []:
            variant_keys.add(str(row.get("variant_key") or ""))
            coverage_statuses.add(str(row.get("coverage_status") or ""))
            evaluated = int(row.get("evaluated_count") or 0)
            filled = int(row.get("filled_count") or 0)
            file_evaluated += evaluated
            total_evaluated += evaluated
            total_filled += filled
        min_evaluated = file_evaluated if min_evaluated is None else min(min_evaluated, file_evaluated)
        max_evaluated = max(max_evaluated, file_evaluated)
    expected_variants = {"default_exit", "quick_tp3_trailing1"}
    return {
        "source_files": source_files,
        "variant_keys": sorted(item for item in variant_keys if item),
        "coverage_statuses": sorted(item for item in coverage_statuses if item),
        "total_evaluated_count": total_evaluated,
        "total_filled_count": total_filled,
        "min_matrix_evaluated_count": min_evaluated or 0,
        "max_matrix_evaluated_count": max_evaluated,
        "expected_variants_present": expected_variants.issubset(variant_keys),
        "explicit_train_validation_split_present": bool(files) and encoded == len(files),
        "explicit_purged_gap_encoded": bool(files) and encoded == ordered == len(files),
    }


def _rerun_command(scope_key: str, window: dict[str, Any], output_dir: Path) -> str:
    strategies = {
        "combined_first_board_volume_shrink": "first_board,volume_shrink",
        "first_board": "first_board",
        "volume_shrink": "volume_shrink",
    }[scope_key]
    return (
        f"DATABASE_URL={SQLITE_DB_URL} "
        "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py "
        f"--train-start {window['proposed_train_start']} --train-end {window['proposed_train_end']} "
        f"--validation-start {window['proposed_validation_start']} --validation-end {window['proposed_validation_end']} "
        f"--purged-gap-start {window['proposed_purged_gap_start']} --purged-gap-end {window['proposed_purged_gap_end']} "
        f"--start {window['oos_start']} --end {window['oos_end']} "
        f"--strategies {strategies} --states confirmed --engine fast --materialization-mode isolated "
        "--variants default_exit,quick_tp3_trailing1 "
        f"--matrix-output-dir {output_dir} --output-dir {output_dir}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit focused walk-forward matrices for purged-gap evidence.")
    parser.add_argument("--date", default=REPORT_DATE)
    args = parser.parse_args()
    report = build_report(report_date=args.date, root=ROOT)
    json_path, md_path = write_report(report, ROOT)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "status": report["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
