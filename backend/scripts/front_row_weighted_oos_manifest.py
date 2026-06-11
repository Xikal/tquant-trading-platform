from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot
from app.services.low_buy.oos_validation_manifest import build_freeze_manifest, today_iso, validate_freeze_manifest


def _default_input_report(filename: str) -> Path:
    artifact_path = ROOT_DIR / "backend" / "data" / "reports" / filename
    if artifact_path.exists():
        return artifact_path
    return ROOT_DIR / "docs" / "reports" / filename


DEFAULT_SOURCE_REPORT = _default_input_report("front-row-weighted-production-scoring-backtest-2026-05-29.json")
DEFAULT_OUTPUT = ROOT_DIR / "backend" / "data" / "reports" / "front-row-weighted-validation-freeze-2026-05-30.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze front-row weighted OOS validation manifest")
    parser.add_argument("--freeze-date", default=today_iso())
    parser.add_argument("--source-report", default=str(DEFAULT_SOURCE_REPORT))
    parser.add_argument("--json-output", default=str(DEFAULT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    with SessionLocal() as db:
        trade_dates = [
            str(item)
            for item in db.execute(select(DailyBarSnapshot.trade_date).distinct().order_by(DailyBarSnapshot.trade_date.asc())).scalars().all()
        ]
    manifest = build_freeze_manifest(
        freeze_date=args.freeze_date,
        source_report_json=args.source_report,
        trade_dates=trade_dates,
        git_commit=_git_commit(),
    )
    validation = validate_freeze_manifest(manifest, root_dir=ROOT_DIR)
    manifest["validation"] = validation.as_dict()
    output = Path(args.json_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"json": str(output), "status": manifest["status"], "blockers": manifest["blockers"]}, ensure_ascii=False, indent=2))
    return 0


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
