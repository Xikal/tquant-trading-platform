from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import Instrument
from app.repositories.low_buy import DailyBarRow, DailyHistoryRepository
from app.services.market_data import guess_market
from sqlalchemy import select, text

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    name: str
    market: str
    instrument_type: str = "stock"


@dataclass(frozen=True)
class BackfillResult:
    symbol: str
    status: str
    rows: int = 0
    message: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="补齐 A 股日线历史到本地数据库")
    parser.add_argument("--months", type=int, default=24, help="向前补齐月份数，默认 24")
    parser.add_argument("--start-date", default="", help="指定开始日期 YYYY-MM-DD，优先级高于 months")
    parser.add_argument("--end-date", default=date.today().isoformat(), help="结束日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--scope", choices=("all-stock", "pool", "symbols"), default="all-stock")
    parser.add_argument("--symbols", default="", help="scope=symbols 时使用，逗号分隔证券代码")
    parser.add_argument("--workers", type=int, default=4, help="并发抓取数，建议 3-6")
    parser.add_argument("--batch-size", type=int, default=80, help="每批处理代码数")
    parser.add_argument("--sleep", type=float, default=0.05, help="每个远端请求后的轻微间隔")
    parser.add_argument("--limit", type=int, default=0, help="调试用，最多处理 N 只")
    parser.add_argument("--force", action="store_true", help="即使已有覆盖也重新拉取")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if ak is None:
        raise SystemExit("当前环境未安装 akshare，无法补齐日线。")
    init_db()
    start_date = args.start_date or (date.fromisoformat(args.end_date) - timedelta(days=max(args.months, 1) * 31 + 90)).isoformat()
    symbols = _load_symbols(scope=args.scope, raw_symbols=args.symbols)
    if args.limit > 0:
        symbols = symbols[: args.limit]
    print(
        {
            "scope": args.scope,
            "symbols": len(symbols),
            "start_date": start_date,
            "end_date": args.end_date,
            "workers": args.workers,
            "force": args.force,
        },
        flush=True,
    )

    totals = {"ok": 0, "skip": 0, "empty": 0, "error": 0}
    for batch_index, batch in enumerate(_chunks(symbols, max(args.batch_size, 1)), start=1):
        results = _backfill_batch(
            batch=batch,
            start_date=start_date,
            end_date=args.end_date,
            workers=max(1, args.workers),
            sleep_seconds=max(args.sleep, 0.0),
            force=args.force,
        )
        for result in results:
            totals[result.status] = totals.get(result.status, 0) + 1
            if result.status in {"ok", "error"}:
                print(
                    f"[daily-backfill] {result.status} {result.symbol} rows={result.rows} {result.message}",
                    flush=True,
                )
        print(
            {
                "batch": batch_index,
                "processed": min(batch_index * len(batch), len(symbols)),
                "total_symbols": len(symbols),
                "totals": totals,
            },
            flush=True,
        )
    print({"done": True, "totals": totals}, flush=True)
    return 0


def _load_symbols(*, scope: str, raw_symbols: str) -> list[SymbolInfo]:
    if scope == "symbols":
        return [
            SymbolInfo(symbol=item.strip(), name=item.strip(), market=guess_market(item.strip()))
            for item in raw_symbols.split(",")
            if item.strip()
        ]
    if scope == "pool":
        return _load_pool_symbols()
    return _load_all_stock_symbols()


def _load_all_stock_symbols() -> list[SymbolInfo]:
    rows = []
    try:
        rows = ak.stock_info_a_code_name().to_dict("records")
    except Exception:
        rows = []
    symbols: list[SymbolInfo] = []
    for row in rows:
        symbol = str(row.get("code") or row.get("证券代码") or row.get("A股代码") or row.get("symbol") or "").strip()
        if not symbol:
            continue
        name = str(row.get("name") or row.get("证券简称") or row.get("A股简称") or symbol).strip()
        if _is_st_or_delist_name(name):
            continue
        symbols.append(SymbolInfo(symbol=symbol, name=name, market=guess_market(symbol)))
    if symbols:
        return _dedupe_symbols(symbols)
    with SessionLocal() as db:
        stored = db.execute(
            select(Instrument).where(Instrument.instrument_type == "stock").order_by(Instrument.symbol.asc())
        ).scalars().all()
        return _dedupe_symbols(
            [
                SymbolInfo(symbol=row.symbol, name=row.name or row.symbol, market=row.market or guess_market(row.symbol))
                for row in stored
            ]
        )


def _load_pool_symbols() -> list[SymbolInfo]:
    sql = text(
        """
        SELECT symbol, MAX(name) AS name
        FROM low_buy_pool_snapshots
        GROUP BY symbol
        ORDER BY symbol
        """
    )
    with SessionLocal() as db:
        rows = db.execute(sql).mappings().all()
    return _dedupe_symbols(
        [
            SymbolInfo(symbol=str(row["symbol"]), name=str(row["name"] or row["symbol"]), market=guess_market(str(row["symbol"])))
            for row in rows
        ]
    )


def _dedupe_symbols(symbols: Iterable[SymbolInfo]) -> list[SymbolInfo]:
    deduped: dict[str, SymbolInfo] = {}
    for item in symbols:
        if item.symbol:
            deduped[item.symbol] = item
    return list(deduped.values())


def _backfill_batch(
    *,
    batch: list[SymbolInfo],
    start_date: str,
    end_date: str,
    workers: int,
    sleep_seconds: float,
    force: bool,
) -> list[BackfillResult]:
    with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as executor:
        futures = [
            executor.submit(
                _backfill_symbol,
                item,
                start_date,
                end_date,
                sleep_seconds,
                force,
            )
            for item in batch
        ]
        return [future.result() for future in as_completed(futures)]


def _backfill_symbol(
    symbol_info: SymbolInfo,
    start_date: str,
    end_date: str,
    sleep_seconds: float,
    force: bool,
) -> BackfillResult:
    symbol = symbol_info.symbol
    try:
        if not force and _coverage_is_complete(symbol=symbol, start_date=start_date, end_date=end_date):
            return BackfillResult(symbol=symbol, status="skip", message="coverage complete")
        rows = _fetch_daily_rows(symbol=symbol, start_date=start_date, end_date=end_date)
        if not rows:
            return BackfillResult(symbol=symbol, status="empty", message="remote empty")
        with SessionLocal() as db:
            DailyHistoryRepository(db).upsert_rows(symbol=symbol, payloads=rows)
            db.commit()
        time.sleep(sleep_seconds)
        return BackfillResult(symbol=symbol, status="ok", rows=len(rows))
    except Exception as exc:
        return BackfillResult(symbol=symbol, status="error", message=str(exc)[:180])


def _coverage_is_complete(*, symbol: str, start_date: str, end_date: str) -> bool:
    sql = text(
        """
        SELECT MIN(trade_date) AS min_date, MAX(trade_date) AS max_date, COUNT(*) AS rows_count
        FROM daily_bar_snapshots
        WHERE symbol = :symbol
        """
    )
    with SessionLocal() as db:
        row = db.execute(sql, {"symbol": symbol}).mappings().first()
    if not row or not row["rows_count"]:
        return False
    return str(row["min_date"]) <= start_date and str(row["max_date"]) >= end_date


def _fetch_daily_rows(*, symbol: str, start_date: str, end_date: str) -> list[DailyBarRow]:
    frame = None
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    try:
        frame = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
    except Exception:
        frame = None
    if frame is None or frame.empty:
        try:
            market_symbol = _to_sina_symbol(symbol)
            frame = ak.stock_zh_a_daily(symbol=market_symbol, start_date=start, end_date=end, adjust="qfq")
        except Exception:
            frame = None
    if frame is None or frame.empty:
        return []
    normalized = _normalize_daily_frame(frame)
    return [
        DailyBarRow(
            trade_date=str(record["date"]),
            open_price=float(record["open"]),
            close_price=float(record["close"]),
            high_price=float(record["high"]),
            low_price=float(record["low"]),
            volume=float(record["volume"]),
            amount=float(record["amount"]),
            pct_chg=float(record["pct_chg"]),
        )
        for record in normalized
    ]


def _normalize_daily_frame(frame) -> list[dict[str, float | str]]:
    column_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "涨跌幅": "pct_chg",
        "date": "date",
        "open": "open",
        "close": "close",
        "high": "high",
        "low": "low",
        "volume": "volume",
        "amount": "amount",
    }
    renamed = frame.rename(columns={key: value for key, value in column_map.items() if key in frame.columns}).copy()
    required = {"date", "open", "close", "high", "low"}
    if not required.issubset(set(renamed.columns)):
        return []
    if "volume" not in renamed.columns:
        renamed["volume"] = 0.0
    if "amount" not in renamed.columns:
        renamed["amount"] = 0.0
    if "pct_chg" not in renamed.columns:
        renamed["pct_chg"] = renamed["close"].pct_change().fillna(0.0) * 100
    rows = []
    for record in renamed.to_dict("records"):
        try:
            rows.append(
                {
                    "date": str(record["date"])[:10],
                    "open": float(record["open"]),
                    "close": float(record["close"]),
                    "high": float(record["high"]),
                    "low": float(record["low"]),
                    "volume": float(record.get("volume") or 0.0),
                    "amount": float(record.get("amount") or 0.0),
                    "pct_chg": float(record.get("pct_chg") or 0.0),
                }
            )
        except (TypeError, ValueError):
            continue
    return rows


def _to_sina_symbol(symbol: str) -> str:
    prefix = "sh" if guess_market(symbol) == "SH" else "sz"
    return f"{prefix}{symbol}"


def _is_st_or_delist_name(name: str) -> bool:
    upper_name = str(name or "").upper()
    return "ST" in upper_name or str(name or "").startswith("退市")


def _chunks(items: list[SymbolInfo], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


if __name__ == "__main__":
    raise SystemExit(main())
