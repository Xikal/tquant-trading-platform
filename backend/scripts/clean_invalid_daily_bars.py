from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, or_, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_OUTPUT = ROOT_DIR / "docs" / "reports" / "invalid-daily-bar-cleanup-2026-05-28.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="删除本地无效 OHLC 日线行，不做价格修补")
    parser.add_argument("--start-date", default="2024-05-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    with SessionLocal() as db:
        report = clean_invalid_daily_bars(db, start_date=args.start_date, end_date=args.end_date, dry_run=args.dry_run)
        if not args.dry_run:
            db.commit()
    output = Path(args.report_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "status": report["status"], "deleted_rows": report["deleted_rows"]}, ensure_ascii=False, indent=2))
    return 0


def clean_invalid_daily_bars(db, *, start_date: str, end_date: str, dry_run: bool = False) -> dict[str, Any]:  # noqa: ANN001
    condition = invalid_condition(start_date=start_date, end_date=end_date)
    rows = db.execute(
        select(
            DailyBarSnapshot.id,
            DailyBarSnapshot.symbol,
            DailyBarSnapshot.trade_date,
            DailyBarSnapshot.open_price,
            DailyBarSnapshot.close_price,
            DailyBarSnapshot.high_price,
            DailyBarSnapshot.low_price,
            DailyBarSnapshot.volume,
            DailyBarSnapshot.amount,
            DailyBarSnapshot.source,
            DailyBarSnapshot.data_quality,
        ).where(condition)
    ).mappings().all()
    ids = [int(row["id"]) for row in rows]
    if ids and not dry_run:
        db.execute(delete(DailyBarSnapshot).where(DailyBarSnapshot.id.in_(ids)))
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": "dry_run" if dry_run else "completed",
        "window": {"start_date": start_date, "end_date": end_date},
        "deleted_rows": 0 if dry_run else len(ids),
        "matched_rows": len(ids),
        "sample": [serializable_row(row) for row in rows[:20]],
        "notes": [
            "仅删除 open/close/high/low 非法或负成交量/成交额的本地日线行。",
            "不使用插值、前收盘、后复权或任何替代价格修补 K 线。",
            "删除后正式覆盖率必须由闭环报告重新计算，不能假定仍达标。",
        ],
    }


def invalid_condition(*, start_date: str, end_date: str):
    return (
        (DailyBarSnapshot.trade_date >= start_date)
        & (DailyBarSnapshot.trade_date <= end_date)
        & (DailyBarSnapshot.instrument_type == "stock")
        & or_(
            DailyBarSnapshot.open_price <= 0,
            DailyBarSnapshot.close_price <= 0,
            DailyBarSnapshot.high_price < DailyBarSnapshot.low_price,
            DailyBarSnapshot.high_price < DailyBarSnapshot.open_price,
            DailyBarSnapshot.high_price < DailyBarSnapshot.close_price,
            DailyBarSnapshot.low_price > DailyBarSnapshot.open_price,
            DailyBarSnapshot.low_price > DailyBarSnapshot.close_price,
            DailyBarSnapshot.volume < 0,
            DailyBarSnapshot.amount < 0,
        )
    )


def serializable_row(row) -> dict[str, object]:  # noqa: ANN001
    result: dict[str, object] = {}
    for key, value in dict(row).items():
        result[str(key)] = value.isoformat() if hasattr(value, "isoformat") else value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
