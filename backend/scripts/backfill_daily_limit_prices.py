from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_OUTPUT = ROOT_DIR / "docs" / "reports" / "daily-limit-price-backfill-2026-05-28.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot, Instrument
from app.repositories.low_buy.daily_history import DailyBarRow, daily_bar_checksum

SOURCE_MARKER = "limit_rules_v1"
CHINEXT_REFORM_DATE = date(2020, 8, 24)


@dataclass(frozen=True)
class DerivedLimit:
    limit_up_price: float
    limit_down_price: float
    ratio_pct: float
    rule: str


@dataclass(frozen=True)
class SkipRecord:
    symbol: str
    trade_date: str
    reason: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按可审计 A 股交易规则补齐日线涨跌停价元数据")
    parser.add_argument("--start-date", default="2024-05-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--force", action="store_true", help="重算已有涨跌停价")
    parser.add_argument("--derive-pre-close", action="store_true", help="用同一标的上一条真实收盘价补齐缺失 pre_close 后再推导涨跌停价")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    with SessionLocal() as db:
        report = backfill_daily_limit_prices(
            db,
            start_date=args.start_date,
            end_date=args.end_date,
            force=args.force,
            limit=args.limit,
            batch_size=args.batch_size,
            derive_pre_close=args.derive_pre_close,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            db.commit()
    output = Path(args.report_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "status": report["status"], "updated_rows": report["updated_rows"]}, ensure_ascii=False, indent=2))
    return 0


def backfill_daily_limit_prices(
    db,
    *,
    start_date: str,
    end_date: str,
    force: bool = False,
    limit: int = 0,
    batch_size: int = 1000,
    derive_pre_close: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    totals: dict[str, int] = {
        "scanned_rows": 0,
        "eligible_rows": 0,
        "updated_rows": 0,
        "skipped_no_pre_close": 0,
        "skipped_no_previous_close": 0,
        "derived_pre_close_rows": 0,
        "skipped_listing_exempt": 0,
        "skipped_non_stock": 0,
        "skipped_rule_unavailable": 0,
        "metadata_missing": 0,
        "missing_listing_date": 0,
        "st_current_only_rows": 0,
    }
    ratio_counts: dict[str, int] = {}
    skip_samples: list[SkipRecord] = []
    update_rows: list[dict[str, object]] = []
    last_close_by_symbol: dict[str, float] = {}

    query = (
        select(DailyBarSnapshot, Instrument)
        .outerjoin(Instrument, DailyBarSnapshot.symbol == Instrument.symbol)
        .where(
            DailyBarSnapshot.trade_date >= start_date,
            DailyBarSnapshot.trade_date <= end_date,
            DailyBarSnapshot.instrument_type == "stock",
        )
        .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
    )
    if not force and not derive_pre_close:
        query = query.where(
            or_(
                DailyBarSnapshot.limit_up_price.is_(None),
                DailyBarSnapshot.limit_down_price.is_(None),
                DailyBarSnapshot.limit_up_price <= 0,
                DailyBarSnapshot.limit_down_price <= 0,
            )
        )
    if limit > 0:
        query = query.limit(limit)

    rows = db.execute(query).yield_per(max(batch_size, 1))
    for snapshot, instrument in rows:
        totals["scanned_rows"] += 1
        symbol = str(snapshot.symbol or "")
        trade_date = parse_date(snapshot.trade_date)
        if trade_date is None:
            add_skip(skip_samples, symbol, snapshot.trade_date, "invalid_trade_date")
            totals["skipped_rule_unavailable"] += 1
            continue
        has_limit_prices = float(snapshot.limit_up_price or 0.0) > 0 and float(snapshot.limit_down_price or 0.0) > 0
        pre_close = float(snapshot.pre_close or 0.0)
        pre_close_derived = False
        should_update = force or not has_limit_prices or pre_close <= 0
        if not should_update:
            remember_close(last_close_by_symbol, symbol, snapshot.close_price)
            continue
        if pre_close <= 0:
            if derive_pre_close and last_close_by_symbol.get(symbol, 0.0) > 0:
                pre_close = last_close_by_symbol[symbol]
                pre_close_derived = True
            else:
                reason = "missing_pre_close" if not derive_pre_close else "missing_previous_close"
                add_skip(skip_samples, symbol, trade_date, reason)
                totals["skipped_no_pre_close"] += 1
                if derive_pre_close:
                    totals["skipped_no_previous_close"] += 1
                remember_close(last_close_by_symbol, symbol, snapshot.close_price)
                continue

        instrument_type = str(snapshot.instrument_type or getattr(instrument, "instrument_type", "") or "stock")
        listing_date = parse_date(getattr(instrument, "listing_date", None))
        if instrument is None:
            totals["metadata_missing"] += 1
        elif listing_date is None:
            totals["missing_listing_date"] += 1
        current_st = bool(getattr(instrument, "is_st", False)) or is_st_name(getattr(instrument, "name", ""))
        row_st = bool(snapshot.is_st)
        is_st = row_st or current_st
        if current_st and not row_st:
            totals["st_current_only_rows"] += 1

        derived = derive_limit_prices(
            symbol=symbol,
            pre_close=pre_close,
            trade_date=trade_date,
            instrument_type=instrument_type,
            is_st=is_st,
            listing_date=listing_date,
        )
        if derived is None:
            reason = "listing_exempt" if is_listing_exempt(trade_date, listing_date) else "rule_unavailable"
            totals["skipped_listing_exempt" if reason == "listing_exempt" else "skipped_rule_unavailable"] += 1
            add_skip(skip_samples, symbol, trade_date, reason)
            remember_close(last_close_by_symbol, symbol, snapshot.close_price)
            continue
        totals["eligible_rows"] += 1
        ratio_counts[f"{derived.ratio_pct:.1f}%"] = ratio_counts.get(f"{derived.ratio_pct:.1f}%", 0) + 1
        if is_fund_like(symbol, instrument_type):
            totals["skipped_non_stock"] += 1
            add_skip(skip_samples, symbol, trade_date, "non_stock")
            remember_close(last_close_by_symbol, symbol, snapshot.close_price)
            continue
        if pre_close_derived:
            totals["derived_pre_close_rows"] += 1
        update_rows.append(build_update_payload(snapshot, derived, pre_close=pre_close, verified=listing_date is not None))
        if len(update_rows) >= max(batch_size, 1):
            totals["updated_rows"] += flush_updates(db, update_rows, dry_run=dry_run)
            update_rows.clear()
        remember_close(last_close_by_symbol, symbol, snapshot.close_price)

    totals["updated_rows"] += flush_updates(db, update_rows, dry_run=dry_run)
    report = build_report(
        start_date=start_date,
        end_date=end_date,
        force=force,
        derive_pre_close=derive_pre_close,
        dry_run=dry_run,
        totals=totals,
        ratio_counts=ratio_counts,
        skip_samples=skip_samples,
    )
    return report


def derive_limit_prices(
    *,
    symbol: str,
    pre_close: float,
    trade_date: date | str,
    instrument_type: str = "stock",
    is_st: bool = False,
    listing_date: date | str | None = None,
) -> DerivedLimit | None:
    parsed_trade_date = parse_date(trade_date)
    parsed_listing_date = parse_date(listing_date)
    if parsed_trade_date is None or pre_close <= 0:
        return None
    if is_fund_like(symbol, instrument_type) or is_listing_exempt(parsed_trade_date, parsed_listing_date):
        return None
    ratio, rule = price_limit_ratio(symbol=symbol, trade_date=parsed_trade_date, instrument_type=instrument_type, is_st=is_st)
    if ratio <= 0:
        return None
    return DerivedLimit(
        limit_up_price=round_price(pre_close * (1 + ratio)),
        limit_down_price=round_price(pre_close * (1 - ratio)),
        ratio_pct=ratio * 100.0,
        rule=rule,
    )


def price_limit_ratio(*, symbol: str, trade_date: date, instrument_type: str, is_st: bool) -> tuple[float, str]:
    normalized_type = str(instrument_type or "stock").strip().lower()
    if normalized_type not in {"stock", "equity", "a_share", "ashare"}:
        return 0.0, "not_stock"
    code = str(symbol or "").strip()
    if is_st:
        return 0.05, "st_5pct"
    if code.startswith(("688", "689")):
        return 0.20, "star_market_20pct"
    if code.startswith(("300", "301")):
        return (0.20, "chinext_20pct_post_2020_08_24") if trade_date >= CHINEXT_REFORM_DATE else (0.10, "chinext_10pct_pre_2020_08_24")
    if code.startswith(("920", "8", "4")):
        return 0.30, "beijing_exchange_30pct"
    return 0.10, "main_board_10pct"


def is_listing_exempt(trade_date: date, listing_date: date | None) -> bool:
    if listing_date is None:
        return False
    days = (trade_date - listing_date).days
    return 0 <= days <= 7


def build_update_payload(snapshot: DailyBarSnapshot, derived: DerivedLimit, *, pre_close: float, verified: bool) -> dict[str, object]:
    source_known = str(snapshot.source or "").strip() not in {"", "unknown", "None"}
    row = DailyBarRow(
        trade_date=str(snapshot.trade_date)[:10],
        open_price=float(snapshot.open_price or 0.0),
        close_price=float(snapshot.close_price or 0.0),
        high_price=float(snapshot.high_price or 0.0),
        low_price=float(snapshot.low_price or 0.0),
        volume=float(snapshot.volume or 0.0),
        amount=float(snapshot.amount or 0.0),
        pct_chg=float(snapshot.pct_chg or 0.0),
        pre_close=pre_close,
        limit_up_price=derived.limit_up_price,
        limit_down_price=derived.limit_down_price,
        is_suspended=bool(snapshot.is_suspended),
        is_st=bool(snapshot.is_st),
        is_delisted=bool(snapshot.is_delisted),
        source=merge_source(snapshot.source),
        fetch_time=str(snapshot.fetch_time or ""),
        adjusted_mode=str(snapshot.adjusted_mode or "unknown"),
        data_quality=next_quality(snapshot.data_quality, verified=verified, source_known=source_known),
    )
    return {
        "id": snapshot.id,
        "pre_close": pre_close,
        "limit_up_price": derived.limit_up_price,
        "limit_down_price": derived.limit_down_price,
        "source": row.source,
        "checksum": daily_bar_checksum(snapshot.symbol, row),
        "data_quality": row.data_quality,
    }


def flush_updates(db, update_rows: list[dict[str, object]], *, dry_run: bool) -> int:  # noqa: ANN001
    if not update_rows:
        return 0
    if not dry_run:
        db.bulk_update_mappings(DailyBarSnapshot, update_rows)
    return len(update_rows)


def build_report(
    *,
    start_date: str,
    end_date: str,
    force: bool,
    derive_pre_close: bool,
    dry_run: bool,
    totals: dict[str, int],
    ratio_counts: dict[str, int],
    skip_samples: list[SkipRecord],
) -> dict[str, Any]:
    status = "dry_run" if dry_run else "completed"
    if totals["updated_rows"] == 0 and totals["scanned_rows"] > 0:
        status = "no_updates" if not dry_run else "dry_run"
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": status,
        "source": SOURCE_MARKER,
        "window": {"start_date": start_date, "end_date": end_date},
        "force": force,
        "derive_pre_close": derive_pre_close,
        "dry_run": dry_run,
        **totals,
        "ratio_counts": dict(sorted(ratio_counts.items())),
        "skip_samples": [asdict(item) for item in skip_samples[:20]],
        "warnings": [
            "涨跌停价由 pre_close、板块代码、ST 标记和上市日期按交易所规则推导；不生成或插值任何 OHLCV 价格。",
            "启用 derive_pre_close 时，pre_close 只来自同一标的上一条已落库真实 close_price；无上一条收盘价的记录继续跳过。",
            "上市后 7 个自然日内按首发无涨跌幅限制保守跳过，避免把常规涨跌停误写到新股豁免日。",
            "若只有 instruments.is_st 当前状态而无历史 ST 快照，报告 st_current_only_rows；正式验收仍应补历史 ST 状态源。",
        ],
    }


def add_skip(samples: list[SkipRecord], symbol: str, trade_date: object, reason: str) -> None:
    if len(samples) >= 20:
        return
    samples.append(SkipRecord(symbol=str(symbol or ""), trade_date=str(trade_date)[:10], reason=reason))


def next_quality(value: object, *, verified: bool, source_known: bool = True) -> str:
    current = str(value or "").strip()
    if current in {"fresh", "verified"}:
        return current
    if not source_known:
        return "partial_metadata"
    return "verified" if verified else "partial_metadata"


def merge_source(value: object) -> str:
    current = str(value or "").strip() or "unknown"
    if SOURCE_MARKER in current:
        return current[:48]
    if current == "unknown":
        return f"unknown|{SOURCE_MARKER}"
    return f"{current}|{SOURCE_MARKER}"[:48]


def parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def round_price(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def remember_close(cache: dict[str, float], symbol: str, close_price: object) -> None:
    value = float(close_price or 0.0)
    if value > 0:
        cache[symbol] = value


def is_st_name(name: object) -> bool:
    text = str(name or "").upper()
    return "ST" in text or str(name or "").startswith("退市")


def is_fund_like(symbol: str, instrument_type: str = "") -> bool:
    normalized_type = str(instrument_type or "").strip().lower()
    if normalized_type in {"etf", "fund", "lof", "index_fund", "money_fund"}:
        return True
    code = str(symbol or "").strip()
    return code.startswith(("15", "16", "50", "51", "52", "56", "58"))


if __name__ == "__main__":
    raise SystemExit(main())
