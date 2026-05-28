from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_OUTPUT = ROOT_DIR / "docs" / "reports" / "instrument-metadata-backfill-2026-05-28.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import Instrument, InstrumentIndustryHistory
from app.services.market.providers.akshare_utils import resolve_sw_industry_name
from app.services.market.shared import guess_market

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None


@dataclass(frozen=True)
class MetadataRow:
    symbol: str
    name: str
    sector_name: str = ""
    listing_date: str = ""
    status: str = "active"
    is_st: bool = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="补齐 instruments 行业、上市日期和状态元数据")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    rows, provider_errors = fetch_metadata_rows()
    if args.limit > 0:
        rows = rows[: args.limit]
    with SessionLocal() as db:
        totals = upsert_metadata_rows(db, rows)
        db.commit()
        coverage = coverage_report(db)
    report = build_report(rows=rows, provider_errors=provider_errors, totals=totals, coverage=coverage)
    output = Path(args.report_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "status": report["status"], "coverage": coverage}, ensure_ascii=False, indent=2))
    return 0


def fetch_metadata_rows() -> tuple[list[MetadataRow], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    rows = fetch_exchange_listing_rows(errors)
    if rows:
        rows = merge_metadata_rows(rows, fetch_sw_industry_rows(errors))
        return rows, errors
    rows = fetch_akshare_spot_rows(errors)
    if rows:
        return rows, errors
    rows = fetch_eastmoney_spot_rows(errors)
    return rows, errors


def fetch_exchange_listing_rows(errors: list[dict[str, str]]) -> list[MetadataRow]:
    if ak is None:
        errors.append({"source": "akshare.exchange_listing", "message": "akshare unavailable"})
        return []
    rows: list[MetadataRow] = []
    try:
        sz_frame = ak.stock_info_sz_name_code()
        rows.extend(parse_spot_records(sz_frame.to_dict("records"), source="akshare.stock_info_sz_name_code"))
    except Exception as exc:
        errors.append({"source": "akshare.stock_info_sz_name_code", "message": str(exc)[:180]})
    for board in ("主板A股", "科创板", "沪市B股"):
        try:
            sh_frame = ak.stock_info_sh_name_code(symbol=board)
            rows.extend(parse_spot_records(sh_frame.to_dict("records"), source=f"akshare.stock_info_sh_name_code:{board}"))
        except Exception as exc:
            errors.append({"source": f"akshare.stock_info_sh_name_code:{board}", "message": str(exc)[:180]})
    try:
        bj_frame = ak.stock_info_bj_name_code()
        rows.extend(parse_spot_records(bj_frame.to_dict("records"), source="akshare.stock_info_bj_name_code"))
    except Exception as exc:
        errors.append({"source": "akshare.stock_info_bj_name_code", "message": str(exc)[:180]})
    return dedupe_rows(rows)


def fetch_sw_industry_rows(errors: list[dict[str, str]]) -> list[MetadataRow]:
    if ak is None:
        return []
    try:
        history_frame = ak.stock_industry_clf_hist_sw()
        category_frame = ak.stock_industry_category_cninfo(symbol="申银万国行业分类标准")
    except Exception as exc:
        errors.append({"source": "akshare.stock_industry_clf_hist_sw", "message": str(exc)[:180]})
        return []
    category_map = {
        text_value(row, "类目编码", "industry_code").removeprefix("S"): text_value(row, "类目名称", "industry_name")
        for row in category_frame.to_dict("records")
    }
    latest: dict[str, tuple[str, str, str]] = {}
    for row in history_frame.to_dict("records"):
        symbol = text_value(row, "symbol", "股票代码", "代码")
        industry_code = text_value(row, "industry_code", "行业代码", "类目编码")
        if not symbol or not industry_code:
            continue
        marker = (text_value(row, "start_date", "开始日期"), text_value(row, "update_time", "更新时间"))
        current = latest.get(symbol)
        if current is None or marker >= (current[1], current[2]):
            latest[symbol] = (industry_code, marker[0], marker[1])
    return [
        MetadataRow(symbol=symbol, name="", sector_name=resolve_sw_industry_name(industry_code, category_map))
        for symbol, (industry_code, _, _) in latest.items()
        if resolve_sw_industry_name(industry_code, category_map)
    ]


def fetch_akshare_spot_rows(errors: list[dict[str, str]]) -> list[MetadataRow]:
    if ak is None:
        errors.append({"source": "akshare.stock_zh_a_spot_em", "message": "akshare unavailable"})
        return []
    try:
        frame = ak.stock_zh_a_spot_em()
    except Exception as exc:
        errors.append({"source": "akshare.stock_zh_a_spot_em", "message": str(exc)[:180]})
        return []
    records = frame.to_dict("records") if frame is not None and not getattr(frame, "empty", False) else []
    return parse_spot_records(records, source="akshare.stock_zh_a_spot_em")


def fetch_eastmoney_spot_rows(errors: list[dict[str, str]]) -> list[MetadataRow]:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
    params = {
        "pn": "1",
        "pz": "6000",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f12,f14,f26,f100",
    }
    try:
        response = session.get("https://82.push2.eastmoney.com/api/qt/clist/get", params=params, timeout=20)
        response.raise_for_status()
        records = ((response.json().get("data") or {}).get("diff") or [])
    except Exception as exc:
        errors.append({"source": "eastmoney.clist", "message": str(exc)[:180]})
        return []
    return parse_spot_records(records, source="eastmoney.clist")


def parse_spot_records(records: list[dict[str, Any]], *, source: str) -> list[MetadataRow]:
    rows: list[MetadataRow] = []
    for record in records:
        symbol = text_value(record, "代码", "证券代码", "A股代码", "f12", "symbol", "code")
        name = text_value(record, "名称", "证券简称", "A股简称", "f14", "name")
        if not symbol or not name:
            continue
        rows.append(
            MetadataRow(
                symbol=symbol,
                name=name,
                sector_name=text_value(record, "行业", "所属行业", "所属行业", "f100", "industry"),
                listing_date=normalize_date(text_value(record, "上市时间", "上市日期", "A股上市日期", "f26", "listing_date")),
                status="delisted" if str(name).startswith("退市") else "active",
                is_st=is_st_name(name),
            )
        )
    return [row for row in rows if row.symbol]


def merge_metadata_rows(primary: list[MetadataRow], secondary: list[MetadataRow]) -> list[MetadataRow]:
    by_symbol = {row.symbol: row for row in primary}
    for row in secondary:
        current = by_symbol.get(row.symbol)
        if current is None:
            by_symbol[row.symbol] = row
            continue
        by_symbol[row.symbol] = MetadataRow(
            symbol=current.symbol,
            name=current.name or row.name,
            sector_name=row.sector_name or current.sector_name,
            listing_date=current.listing_date or row.listing_date,
            status=current.status or row.status,
            is_st=current.is_st or row.is_st,
        )
    return list(by_symbol.values())


def dedupe_rows(rows: list[MetadataRow]) -> list[MetadataRow]:
    merged: dict[str, MetadataRow] = {}
    for row in rows:
        if not row.symbol:
            continue
        merged[row.symbol] = merge_metadata_rows([merged[row.symbol]], [row])[0] if row.symbol in merged else row
    return list(merged.values())


def upsert_metadata_rows(db, rows: list[MetadataRow]) -> dict[str, int]:  # noqa: ANN001
    totals = {"seen": len(rows), "created": 0, "updated": 0, "sector": 0, "listing": 0}
    existing = {row.symbol: row for row in db.execute(select(Instrument)).scalars().all()}
    for item in rows:
        row = existing.get(item.symbol)
        if row is None:
            row = Instrument(symbol=item.symbol, name=item.name, market=guess_market(item.symbol), instrument_type="stock")
            db.add(row)
            existing[item.symbol] = row
            totals["created"] += 1
        else:
            totals["updated"] += 1
        row.name = item.name or row.name
        row.market = guess_market(item.symbol)
        row.instrument_type = "stock"
        if item.sector_name:
            row.sector_name = item.sector_name
            totals["sector"] += 1
            upsert_industry_history(db, item)
        if item.listing_date:
            row.listing_date = item.listing_date
            totals["listing"] += 1
        row.is_st = bool(item.is_st)
        row.status = "historical_metadata_only" if not row.name and not item.listing_date else (item.status or "active")
    return totals


def upsert_industry_history(db, item: MetadataRow) -> None:  # noqa: ANN001
    trade_date = item.listing_date or "1900-01-01"
    existing = db.execute(
        select(InstrumentIndustryHistory).where(
            InstrumentIndustryHistory.symbol == item.symbol,
            InstrumentIndustryHistory.trade_date == trade_date,
            InstrumentIndustryHistory.industry_name == item.sector_name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.source = "instrument_metadata_backfill"
        existing.data_quality = "fresh" if item.listing_date else "partial_metadata"
        return
    db.add(
        InstrumentIndustryHistory(
            symbol=item.symbol,
            trade_date=trade_date,
            industry_name=item.sector_name,
            source="instrument_metadata_backfill",
            data_quality="fresh" if item.listing_date else "partial_metadata",
        )
    )


def coverage_report(db) -> dict[str, object]:  # noqa: ANN001
    rows = db.execute(select(Instrument).where(Instrument.instrument_type == "stock")).scalars().all()
    total = len(rows)
    sector = sum(1 for row in rows if row.sector_name)
    listing = sum(1 for row in rows if row.listing_date is not None)
    status = sum(1 for row in rows if row.status)
    return {
        "stock_count": total,
        "sector_filled_count": sector,
        "listing_date_count": listing,
        "status_count": status,
        "sector_coverage_pct": pct(sector, total),
        "listing_date_coverage_pct": pct(listing, total),
    }


def build_report(*, rows: list[MetadataRow], provider_errors: list[dict[str, str]], totals: dict[str, int], coverage: dict[str, object]) -> dict[str, object]:
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": "completed" if rows else "partial_data",
        "source": "akshare.stock_zh_a_spot_em|eastmoney.clist",
        "totals": totals,
        "coverage": coverage,
        "provider_errors": provider_errors,
        "sample": [asdict(row) for row in rows[:10]],
        "notes": [
            "仅写入真实返回的行业、上市日期和状态字段，缺失字段不会硬填。",
            "ST/退市状态按名称和远端状态字段保守识别，正式回测仍需独立校验。",
            "脚本成功不代表 24 个月回测验收通过，仍需闭环门禁确认。",
        ],
    }


def text_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", "-", "--"):
            return str(value).strip()
    return ""


def normalize_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or raw in {"0", "19700101"}:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return raw[:10]


def is_st_name(name: str) -> bool:
    text = str(name or "").upper()
    return "ST" in text or str(name or "").startswith("退市")


def pct(part: int, total: int) -> float:
    return round(part / total * 100.0, 2) if total else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
