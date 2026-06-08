#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DATASETS = [
    "daily_bars",
    "strategy_tracking_snapshots",
    "key_level_snapshots",
    "low_buy_result_snapshots",
    "backtest_runs",
    "backtest_trades",
    "backtest_daily_snapshots",
    "analysis_logs",
    "market_review_reports",
    "paper_review_reports",
]


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: int = 60) -> CommandResult:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return CommandResult(" ".join(command), 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(" ".join(command), 124, exc.stdout or "", exc.stderr or "command timed out")
    return CommandResult(" ".join(command), completed.returncode, completed.stdout, completed.stderr)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest_root(root: Path, datasets: list[str] | None = None) -> dict[str, Any]:
    dataset_keys = datasets or DATASETS
    manifests_dir = root / "manifests"
    results: dict[str, Any] = {}
    for dataset_key in dataset_keys:
        manifest_path = manifests_dir / f"{dataset_key}.latest.json"
        results[dataset_key] = verify_manifest_file(root, dataset_key, manifest_path)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_root": str(root),
        "dataset_count": len(dataset_keys),
        "datasets": results,
    }
    report["summary"] = summarize(report)
    report["evaluation"] = evaluate(report)
    return report


def verify_manifest_file(root: Path, dataset_key: str, manifest_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "dataset_key": dataset_key,
        "manifest_path": str(manifest_path),
        "present": manifest_path.exists(),
        "valid_json": False,
        "row_count": 0,
        "quality_status": "",
        "status": "",
        "file_count": 0,
        "verified_file_count": 0,
        "missing_file_count": 0,
        "hash_mismatch_count": 0,
        "warnings": [],
        "blockers": [],
    }
    if not manifest_path.exists():
        result["blockers"].append("manifest_missing")
        return result
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result["blockers"].append("manifest_invalid_json")
        return result
    result["valid_json"] = True
    result["manifest_id"] = payload.get("manifest_id")
    result["dataset_version"] = payload.get("dataset_version")
    result["generated_at"] = payload.get("generated_at")
    result["period_start"] = payload.get("period_start")
    result["period_end"] = payload.get("period_end")
    result["row_count"] = int(payload.get("row_count") or 0)
    result["status"] = str(payload.get("status") or "")
    result["quality_status"] = str(payload.get("quality_status") or (payload.get("quality") or {}).get("status") or "")
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    result["source_table"] = source.get("source_table")
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    result["file_count"] = len(files)
    if str(payload.get("dataset_key") or payload.get("dataset") or "") != dataset_key:
        result["blockers"].append("dataset_key_mismatch")
    if not result["manifest_id"]:
        result["warnings"].append("manifest_id_missing")
    if not result["dataset_version"]:
        result["blockers"].append("dataset_version_missing")
    if not result["period_start"] or not result["period_end"]:
        result["blockers"].append("period_missing")
    if result["row_count"] > 0 and not files:
        result["blockers"].append("manifest_files_missing")
    result["files"] = [_verify_manifest_file_entry(root, item) for item in files]
    result["verified_file_count"] = sum(1 for item in result["files"] if item["exists"] and item["hash_ok"])
    result["missing_file_count"] = sum(1 for item in result["files"] if not item["exists"])
    result["hash_mismatch_count"] = sum(1 for item in result["files"] if item["exists"] and item.get("hash_ok") is False)
    if result["missing_file_count"]:
        result["blockers"].append(f"artifact_file_missing:{result['missing_file_count']}")
    if result["hash_mismatch_count"]:
        result["blockers"].append(f"artifact_hash_mismatch:{result['hash_mismatch_count']}")
    return result


def _verify_manifest_file_entry(root: Path, item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"path": "", "exists": False, "hash_ok": False, "blocker": "file_entry_invalid"}
    raw_path = str(item.get("path") or "")
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    expected = str(item.get("sha256") or "")
    exists = path.exists()
    actual = file_sha256(path) if exists else ""
    return {
        "path": raw_path,
        "exists": exists,
        "rows": item.get("rows"),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "hash_ok": bool(expected and actual == expected) if exists else False,
    }


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    datasets = report.get("datasets", {})
    ready = [key for key, item in datasets.items() if item.get("present") and not item.get("blockers")]
    no_data = [key for key, item in datasets.items() if item.get("quality_status") == "no_data"]
    missing = [key for key, item in datasets.items() if not item.get("present")]
    blocked = [key for key, item in datasets.items() if item.get("blockers")]
    warned = [key for key, item in datasets.items() if item.get("warnings")]
    return {
        "ready_count": len(ready),
        "no_data_count": len(no_data),
        "missing_count": len(missing),
        "blocked_count": len(blocked),
        "warning_dataset_count": len(warned),
        "ready_datasets": ready,
        "missing_datasets": missing,
        "blocked_datasets": blocked,
        "warning_datasets": warned,
        "total_rows": sum(int(item.get("row_count") or 0) for item in datasets.values()),
        "verified_files": sum(int(item.get("verified_file_count") or 0) for item in datasets.values()),
    }


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {})
    warnings: list[str] = []
    blocking: list[str] = []
    if summary.get("missing_count"):
        warnings.append(f"manifest_missing_count={summary['missing_count']}")
    if summary.get("warning_dataset_count"):
        warnings.append(f"manifest_warning_dataset_count={summary['warning_dataset_count']}")
    if summary.get("blocked_count"):
        blocking.append(f"manifest_blocked_count={summary['blocked_count']}")
    return {
        "ok": not blocking,
        "status": "blocking" if blocking else ("warning" if warnings else "ok"),
        "warnings": warnings,
        "blocking": blocking,
    }


def collect_remote(host: str, user: str, ssh_key: Path | None, analytics_root: str, datasets: list[str]) -> dict[str, Any]:
    dataset_args = " ".join(shell_quote(item) for item in datasets)
    remote_script = f"""
set -eu
sudo python3 - {shell_quote(analytics_root)} {dataset_args} <<'PY'
import datetime
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
datasets = sys.argv[2:]

def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def verify_file(item):
    if not isinstance(item, dict):
        return {{"path": "", "exists": False, "hash_ok": False, "blocker": "file_entry_invalid"}}
    raw = str(item.get("path") or "")
    path = pathlib.Path(raw)
    if not path.is_absolute():
        path = root / path
    exists = path.exists()
    actual = file_hash(path) if exists else ""
    expected = str(item.get("sha256") or "")
    return {{
        "path": raw,
        "exists": exists,
        "rows": item.get("rows"),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "hash_ok": bool(expected and actual == expected) if exists else False,
    }}

def verify_dataset(dataset_key):
    manifest_path = root / "manifests" / f"{{dataset_key}}.latest.json"
    result = {{
        "dataset_key": dataset_key,
        "manifest_path": str(manifest_path),
        "present": manifest_path.exists(),
        "valid_json": False,
        "row_count": 0,
        "quality_status": "",
        "status": "",
        "file_count": 0,
        "verified_file_count": 0,
        "missing_file_count": 0,
        "hash_mismatch_count": 0,
        "warnings": [],
        "blockers": [],
    }}
    if not manifest_path.exists():
        result["blockers"].append("manifest_missing")
        return result
    try:
        payload = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        result["blockers"].append("manifest_invalid_json")
        return result
    result["valid_json"] = True
    result["manifest_id"] = payload.get("manifest_id")
    result["dataset_version"] = payload.get("dataset_version")
    result["generated_at"] = payload.get("generated_at")
    result["period_start"] = payload.get("period_start")
    result["period_end"] = payload.get("period_end")
    result["row_count"] = int(payload.get("row_count") or 0)
    result["status"] = str(payload.get("status") or "")
    result["quality_status"] = str(payload.get("quality_status") or (payload.get("quality") or {{}}).get("status") or "")
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {{}}
    result["source_table"] = source.get("source_table")
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    result["file_count"] = len(files)
    if str(payload.get("dataset_key") or payload.get("dataset") or "") != dataset_key:
        result["blockers"].append("dataset_key_mismatch")
    if not result["manifest_id"]:
        result["warnings"].append("manifest_id_missing")
    if not result["dataset_version"]:
        result["blockers"].append("dataset_version_missing")
    if not result["period_start"] or not result["period_end"]:
        result["blockers"].append("period_missing")
    if result["row_count"] > 0 and not files:
        result["blockers"].append("manifest_files_missing")
    result["files"] = [verify_file(item) for item in files]
    result["verified_file_count"] = sum(1 for item in result["files"] if item["exists"] and item["hash_ok"])
    result["missing_file_count"] = sum(1 for item in result["files"] if not item["exists"])
    result["hash_mismatch_count"] = sum(1 for item in result["files"] if item["exists"] and item.get("hash_ok") is False)
    if result["missing_file_count"]:
        result["blockers"].append(f"artifact_file_missing:{{result['missing_file_count']}}")
    if result["hash_mismatch_count"]:
        result["blockers"].append(f"artifact_hash_mismatch:{{result['hash_mismatch_count']}}")
    return result

def summarize(report):
    datasets_payload = report.get("datasets", {{}})
    ready = [key for key, item in datasets_payload.items() if item.get("present") and not item.get("blockers")]
    no_data = [key for key, item in datasets_payload.items() if item.get("quality_status") == "no_data"]
    missing = [key for key, item in datasets_payload.items() if not item.get("present")]
    blocked = [key for key, item in datasets_payload.items() if item.get("blockers")]
    warned = [key for key, item in datasets_payload.items() if item.get("warnings")]
    return {{
        "ready_count": len(ready),
        "no_data_count": len(no_data),
        "missing_count": len(missing),
        "blocked_count": len(blocked),
        "warning_dataset_count": len(warned),
        "ready_datasets": ready,
        "missing_datasets": missing,
        "blocked_datasets": blocked,
        "warning_datasets": warned,
        "total_rows": sum(int(item.get("row_count") or 0) for item in datasets_payload.values()),
        "verified_files": sum(int(item.get("verified_file_count") or 0) for item in datasets_payload.values()),
    }}

report = {{
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "analytics_root": str(root),
    "dataset_count": len(datasets),
    "datasets": {{dataset: verify_dataset(dataset) for dataset in datasets}},
}}
report["summary"] = summarize(report)
print(json.dumps(report, ensure_ascii=False))
PY
"""
    command = ["ssh", "-o", "StrictHostKeyChecking=no", f"{user}@{host}", remote_script]
    if ssh_key:
        command[1:1] = ["-i", str(ssh_key)]
    result = run_command(command, timeout=120)
    if result.returncode != 0:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analytics_root": analytics_root,
            "dataset_count": len(datasets),
            "datasets": {},
            "summary": {
                "ready_count": 0,
                "no_data_count": 0,
                "missing_count": 0,
                "blocked_count": len(datasets),
                "warning_dataset_count": 0,
                "ready_datasets": [],
                "missing_datasets": [],
                "blocked_datasets": datasets,
                "warning_datasets": [],
                "total_rows": 0,
                "verified_files": 0,
            },
        }
    else:
        report = json.loads(result.stdout or "{}")
    report["source"] = {"remote_host": host, "remote_user": user, "analytics_root": analytics_root}
    report["commands"] = {
        "ssh": {
            "command": "ssh <redacted>",
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }
    }
    report["evaluation"] = evaluate(report)
    return report


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def load_fixture(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    report["evaluation"] = evaluate(report)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    evaluation = report.get("evaluation", {})
    summary = report.get("summary", {})
    lines = [
        "# Analytics Manifest 只读复验报告",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- Analytics root：`{report.get('analytics_root', '')}`",
        f"- 状态：`{evaluation.get('status', 'unknown')}`",
        f"- 阻断项：{', '.join(evaluation.get('blocking', [])) or '无'}",
        f"- 警告项：{', '.join(evaluation.get('warnings', [])) or '无'}",
        "",
        "## 汇总",
        "",
        "| 指标 | 当前值 |",
        "| --- | ---: |",
        f"| 数据集数量 | {report.get('dataset_count', 'unknown')} |",
        f"| ready datasets | {summary.get('ready_count', 0)} |",
        f"| missing manifests | {summary.get('missing_count', 0)} |",
        f"| blocked datasets | {summary.get('blocked_count', 0)} |",
        f"| warning datasets | {summary.get('warning_dataset_count', 0)} |",
        f"| total rows | {summary.get('total_rows', 0)} |",
        f"| verified files | {summary.get('verified_files', 0)} |",
        "",
        "## 数据集",
        "",
        "| Dataset | Manifest | Rows | Quality | Files | Warnings | Blockers |",
        "| --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for dataset_key, item in report.get("datasets", {}).items():
        lines.append(
            "| "
            + " | ".join(
                [
                    dataset_key,
                    "present" if item.get("present") else "missing",
                    str(item.get("row_count", 0)),
                    str(item.get("quality_status") or item.get("status") or ""),
                    str(item.get("verified_file_count", 0)),
                    ", ".join(item.get("warnings") or []) or "-",
                    ", ".join(item.get("blockers") or []) or "-",
                ]
            )
            + " |"
        )
    lines.extend(["", "## 结论", ""])
    if evaluation.get("blocking"):
        lines.append("当前 manifest 复验存在 blocking 项，不能作为 MySQL 热库清理依据。")
    elif evaluation.get("warnings"):
        lines.append("当前 manifest 复验无 blocking，但有缺失项，需要继续生成/校验真实 manifest。")
    else:
        lines.append("当前 manifest 复验通过；仍需独立授权后才能执行任何 MySQL 源数据清理。")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def parse_dataset_args(raw: str | None) -> list[str]:
    if not raw:
        return list(DATASETS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only analytics manifest verifier.")
    parser.add_argument("--analytics-root", type=Path, default=Path("backend/data/analytics"))
    parser.add_argument("--datasets")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--ssh-host")
    parser.add_argument("--ssh-user", default="ubuntu")
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-blocking", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    datasets = parse_dataset_args(args.datasets)
    if args.fixture:
        report = load_fixture(args.fixture)
    elif args.ssh_host:
        report = collect_remote(args.ssh_host, args.ssh_user, args.ssh_key, str(args.analytics_root), datasets)
    else:
        report = verify_manifest_root(args.analytics_root, datasets)
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report["evaluation"], ensure_ascii=False))
    if args.fail_on_blocking and report["evaluation"]["blocking"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
