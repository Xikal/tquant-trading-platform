from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_OUTPUT = ROOT_DIR / "docs" / "reports" / "etf-execution-metadata-backfill-latest.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import MinuteBarSnapshot
from app.models.schemas import KlineBar
from app.services.etf.universe import EtfProfile, list_etf_profiles
from app.services.market.minute_bar_store import minute_bar_checksum

try:
    from .etf_minute_backfill_helpers import enrich_etf_bars, minute_data_quality
except ImportError:  # pragma: no cover
    from etf_minute_backfill_helpers import enrich_etf_bars, minute_data_quality


@dataclass(frozen=True)
class MetadataBackfillResult:
    symbol: str
    scanned_rows: int
    updated_rows: int
    tracking_index_rows: int
    liquidity_tier_rows: int
    bid_ask_spread_positive_rows: int
    premium_discount_rows: int
    fresh_or_verified_rows: int
    partial_metadata_rows: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="补齐 ETF T0 分钟线可推导执行元数据")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--period", default="", choices=("", "1m", "5m", "15m", "30m", "60m"))
    parser.add_argument("--scope", choices=("t0-etf", "symbols"), default="t0-etf")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    profiles = resolve_profiles(scope=args.scope, raw_symbols=args.symbols)
    with SessionLocal() as db:
        results = backfill_execution_metadata(
            db,
            profiles=profiles,
            start_date=args.start_date,
            end_date=args.end_date,
            period=args.period,
            dry_run=args.dry_run,
        )
    report = build_report(args=args, profiles=profiles, results=results)
    write_report(Path(args.report_output), report)
    print(json.dumps({"report": str(args.report_output), "status": report["status"], "totals": report["totals"]}, ensure_ascii=False, indent=2), flush=True)
    return 0


def resolve_profiles(*, scope: str, raw_symbols: str) -> list[EtfProfile]:
    profiles = [item for item in list_etf_profiles() if item.same_day_sell_allowed]
    if scope == "symbols":
        wanted = {item.strip() for item in raw_symbols.split(",") if item.strip()}
        if not wanted:
            raise SystemExit("scope=symbols 时必须提供 --symbols")
        profiles = [item for item in profiles if item.symbol in wanted]
    return sorted(profiles, key=lambda item: item.symbol)


def backfill_execution_metadata(
    db,
    *,
    profiles: list[EtfProfile],
    start_date: str = "",
    end_date: str = "",
    period: str = "",
    dry_run: bool = False,
) -> list[MetadataBackfillResult]:
    results: list[MetadataBackfillResult] = []
    now = datetime.utcnow().isoformat(timespec="seconds")
    for profile in profiles:
        rows = _rows_for_profile(db, profile=profile, start_date=start_date, end_date=end_date, period=period)
        updated = 0
        for row in rows:
            before = _row_state(row)
            bar = _bar_from_row(row)
            enrich_etf_bars(profile, [bar])
            row.tracking_index_symbol = bar.tracking_index_symbol or ""
            row.liquidity_tier = bar.liquidity_tier or "unknown"
            row.data_quality = minute_data_quality(profile=profile, bar=bar)
            row.checksum = minute_bar_checksum(row.symbol, bar, source=row.source or "unknown", data_quality=row.data_quality)
            row.fetch_time = row.fetch_time or now
            if before != _row_state(row):
                updated += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
        results.append(_result_for(profile.symbol, rows, updated))
    return results


def _rows_for_profile(db, *, profile: EtfProfile, start_date: str, end_date: str, period: str) -> list[MinuteBarSnapshot]:
    query = db.query(MinuteBarSnapshot).filter(MinuteBarSnapshot.symbol == profile.symbol, MinuteBarSnapshot.instrument_type == "etf")
    if start_date:
        query = query.filter(MinuteBarSnapshot.trade_date >= start_date)
    if end_date:
        query = query.filter(MinuteBarSnapshot.trade_date <= end_date)
    if period:
        query = query.filter(MinuteBarSnapshot.bar_period == period)
    return list(query.order_by(MinuteBarSnapshot.symbol.asc(), MinuteBarSnapshot.bar_timestamp.asc()).all())


def _bar_from_row(row: MinuteBarSnapshot) -> KlineBar:
    return KlineBar(
        timestamp=row.bar_timestamp,
        open=float(row.open_price or 0.0),
        high=float(row.high_price or 0.0),
        low=float(row.low_price or 0.0),
        close=float(row.close_price or 0.0),
        volume=float(row.volume or 0.0),
        amount=float(row.amount or 0.0),
        bid_ask_spread=float(row.bid_ask_spread or 0.0),
        premium_discount_pct=row.premium_discount_pct,
        tracking_index_symbol=row.tracking_index_symbol or "",
        liquidity_tier=row.liquidity_tier or "unknown",
    )


def _row_state(row: MinuteBarSnapshot) -> tuple[Any, ...]:
    return (row.tracking_index_symbol, row.liquidity_tier, row.data_quality, row.checksum)


def _result_for(symbol: str, rows: list[MinuteBarSnapshot], updated_rows: int) -> MetadataBackfillResult:
    return MetadataBackfillResult(
        symbol=symbol,
        scanned_rows=len(rows),
        updated_rows=updated_rows,
        tracking_index_rows=sum(1 for row in rows if row.tracking_index_symbol),
        liquidity_tier_rows=sum(1 for row in rows if row.liquidity_tier not in ("", "unknown")),
        bid_ask_spread_positive_rows=sum(1 for row in rows if float(row.bid_ask_spread or 0.0) > 0),
        premium_discount_rows=sum(1 for row in rows if row.premium_discount_pct is not None),
        fresh_or_verified_rows=sum(1 for row in rows if row.data_quality in ("fresh", "verified")),
        partial_metadata_rows=sum(1 for row in rows if row.data_quality == "partial_metadata"),
    )


def build_report(*, args: argparse.Namespace, profiles: list[EtfProfile], results: list[MetadataBackfillResult]) -> dict[str, Any]:
    totals = {
        "symbols": len(profiles),
        "scanned_rows": sum(item.scanned_rows for item in results),
        "updated_rows": sum(item.updated_rows for item in results),
        "tracking_index_rows": sum(item.tracking_index_rows for item in results),
        "liquidity_tier_rows": sum(item.liquidity_tier_rows for item in results),
        "bid_ask_spread_positive_rows": sum(item.bid_ask_spread_positive_rows for item in results),
        "premium_discount_rows": sum(item.premium_discount_rows for item in results),
        "fresh_or_verified_rows": sum(item.fresh_or_verified_rows for item in results),
        "partial_metadata_rows": sum(item.partial_metadata_rows for item in results),
    }
    blocking = totals["scanned_rows"] > 0 and (
        totals["bid_ask_spread_positive_rows"] < totals["scanned_rows"]
        or totals["premium_discount_rows"] < totals["scanned_rows"]
        or totals["fresh_or_verified_rows"] < totals["scanned_rows"]
    )
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": "completed_with_blocking_metadata_gaps" if blocking else "completed",
        "config": {"scope": args.scope, "symbols": args.symbols, "start_date": args.start_date, "end_date": args.end_date, "period": args.period or "all", "dry_run": args.dry_run},
        "totals": totals,
        "results": [asdict(item) for item in results],
        "notes": [
            "本脚本只补 ETF universe 跟踪指数与基于成交额的流动性等级。",
            "不伪造 bid/ask spread、折溢价或 fresh/verified 状态；这些字段缺失时继续阻断生产门禁。",
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
