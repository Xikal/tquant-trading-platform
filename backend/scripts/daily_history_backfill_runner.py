from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RUN_DIR = ROOT_DIR / "docs" / "reports" / "daily-history-backfill-runs"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.scripts import backfill_daily_history


@dataclass(frozen=True)
class BatchSpec:
    batch_id: str
    symbols: list[str]
    report_path: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="可恢复的 A 股日线批量补数运行器")
    parser.add_argument("--scope", choices=("all-stock", "pool", "symbols"), default="symbols")
    parser.add_argument("--symbols", default="", help="scope=symbols 时使用，逗号分隔证券代码")
    parser.add_argument("--limit", type=int, default=0, help="调试用，最多处理 N 只")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_id = args.run_id or f"daily-history-{args.start_date}-{args.end_date}"
    run_dir = Path(args.run_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    batches = build_batches(
        symbols=resolve_symbols(args),
        batch_size=max(1, args.batch_size),
        run_dir=run_dir,
    )
    results = []
    for batch in batches:
        if args.resume and _batch_completed(batch.report_path):
            results.append(_load_batch_summary(batch, skipped=True))
            continue
        result = run_batch(batch, args=args)
        results.append(result)
        write_manifest(run_dir, run_id=run_id, args=args, batches=batches, results=results)
    manifest = write_manifest(run_dir, run_id=run_id, args=args, batches=batches, results=results)
    print(json.dumps({"manifest": str(manifest), "totals": manifest_summary(results)}, ensure_ascii=False, indent=2))
    return 0 if not any(item["status"] == "failed" for item in results) else 2


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    raw_symbols = str(getattr(args, "symbols", "") or "")
    scope = str(getattr(args, "scope", "symbols") or "symbols")
    if scope == "symbols" and not raw_symbols.strip():
        raise SystemExit("scope=symbols 时必须提供 --symbols")
    loaded = backfill_daily_history._load_symbols(scope=scope, raw_symbols=raw_symbols)
    symbols = [item.symbol for item in loaded if item.symbol]
    limit = int(getattr(args, "limit", 0) or 0)
    if limit > 0:
        symbols = symbols[:limit]
    if not symbols:
        raise SystemExit(f"未解析到可补数标的：scope={scope}")
    return symbols


def build_batches(*, symbols: list[str], batch_size: int, run_dir: Path) -> list[BatchSpec]:
    batches = []
    for index in range(0, len(symbols), batch_size):
        batch_no = len(batches) + 1
        batch_id = f"batch-{batch_no:04d}"
        batches.append(
            BatchSpec(
                batch_id=batch_id,
                symbols=symbols[index : index + batch_size],
                report_path=str(run_dir / f"{batch_id}.json"),
            )
        )
    return batches


def run_batch(batch: BatchSpec, *, args: argparse.Namespace) -> dict:
    command = [
        sys.executable,
        str(ROOT_DIR / "backend" / "scripts" / "backfill_daily_history.py"),
        "--scope",
        "symbols",
        "--symbols",
        ",".join(batch.symbols),
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--workers",
        str(args.workers),
        "--batch-size",
        str(len(batch.symbols)),
        "--sleep",
        str(args.sleep),
        "--report-output",
        batch.report_path,
    ]
    if args.force:
        command.append("--force")
    completed = subprocess.run(command, cwd=str(ROOT_DIR), text=True, capture_output=True, check=False)
    report = _load_json(Path(batch.report_path))
    return {
        "batch_id": batch.batch_id,
        "symbols": batch.symbols,
        "status": "completed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "report_path": batch.report_path,
        "totals": report.get("totals", {}),
        "failed_symbols": report.get("failed_symbols", []),
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }


def write_manifest(run_dir: Path, *, run_id: str, args: argparse.Namespace, batches: list[BatchSpec], results: list[dict]) -> Path:
    manifest = {
        "run_id": run_id,
        "status": "completed" if len(results) == len(batches) and not any(item["status"] == "failed" for item in results) else "partial_data",
        "config": {
            "scope": getattr(args, "scope", "symbols"),
            "symbol_count": sum(len(item.symbols) for item in batches),
            "limit": getattr(args, "limit", 0),
            "start_date": args.start_date,
            "end_date": args.end_date,
            "batch_size": args.batch_size,
            "workers": args.workers,
            "resume": args.resume,
            "force": args.force,
        },
        "batch_count": len(batches),
        "completed_batch_count": sum(1 for item in results if item["status"] == "completed"),
        "totals": manifest_summary(results),
        "batches": [asdict(item) for item in batches],
        "results": results,
    }
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def manifest_summary(results: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {"ok": 0, "skip": 0, "empty": 0, "error": 0}
    for result in results:
        for key, value in dict(result.get("totals") or {}).items():
            totals[key] = totals.get(key, 0) + int(value or 0)
    return totals


def _batch_completed(report_path: str) -> bool:
    payload = _load_json(Path(report_path))
    return bool(payload) and payload.get("status") == "completed"


def _load_batch_summary(batch: BatchSpec, *, skipped: bool) -> dict:
    report = _load_json(Path(batch.report_path))
    return {
        "batch_id": batch.batch_id,
        "symbols": batch.symbols,
        "status": "completed",
        "resume_skipped": skipped,
        "exit_code": 0,
        "report_path": batch.report_path,
        "totals": report.get("totals", {}),
        "failed_symbols": report.get("failed_symbols", []),
        "stdout_tail": "",
        "stderr_tail": "",
    }


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
