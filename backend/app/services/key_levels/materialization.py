from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import DailyBarSnapshot, Instrument, SystemSetting
from app.models.schema_defs.key_levels import KeyLevelResult
from app.repositories.low_buy.daily_history import DailyBarRow
from app.services.key_levels.cache_repository import KeyLevelSnapshotRepository
from app.services.key_levels.engine import AKeyLevelEngine, _build_proxy_rows


class AKeyLevelMaterializationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def refresh(
        self,
        *,
        trade_date: str | None = None,
        symbols: list[str] | None = None,
        sectors: list[str] | None = None,
        stock_limit: int | None = None,
        sector_limit: int | None = None,
        batch_size: int = 250,
    ) -> dict[str, Any]:
        as_of = (trade_date or self._latest_trade_date() or beijing_today().isoformat())[:10]
        stock_symbols = (
            _unique_non_empty(symbols)
            if symbols is not None
            else self._stock_symbols(limit=stock_limit)
        )
        sector_keys = (
            _unique_non_empty(sectors)
            if sectors is not None
            else self._sector_keys(limit=sector_limit)
        )
        engine = AKeyLevelEngine(self.db)
        rows_cache: dict[str, list[DailyBarRow]] = {}
        stock_count = 0
        sector_count = 0
        pending_writes = 0
        commit_every = max(1, min(int(batch_size or 250), 1000))
        for symbol in stock_symbols:
            result = self._build_stock_from_cached_rows(engine, rows_cache, symbol, trade_date=as_of)
            write_cached_key_level(self.db, result)
            stock_count += 1
            pending_writes += 1
            if pending_writes >= commit_every:
                self._commit_progress(
                    trade_date=as_of,
                    phase="stocks",
                    completed=stock_count,
                    total=len(stock_symbols),
                )
                pending_writes = 0
        if pending_writes:
            self._commit_progress(
                trade_date=as_of,
                phase="stocks",
                completed=stock_count,
                total=len(stock_symbols),
            )
            pending_writes = 0
        for sector_key in sector_keys:
            result = self._build_sector_from_cached_rows(engine, rows_cache, sector_key, trade_date=as_of)
            write_cached_key_level(self.db, result)
            sector_count += 1
            pending_writes += 1
            if pending_writes >= commit_every:
                self._commit_progress(
                    trade_date=as_of,
                    phase="sectors",
                    completed=sector_count,
                    total=len(sector_keys),
                )
                pending_writes = 0
        if pending_writes:
            self._commit_progress(
                trade_date=as_of,
                phase="sectors",
                completed=sector_count,
                total=len(sector_keys),
            )
            pending_writes = 0
        market_result = self._build_market_from_cached_rows(engine, rows_cache, trade_date=as_of)
        write_cached_key_level(self.db, market_result, key="market")
        self._commit_progress(trade_date=as_of, phase="market", completed=1, total=1)
        return {
            "ok": True,
            "trade_date": as_of,
            "stock_count": stock_count,
            "sector_count": sector_count,
            "market_count": 1,
            "batch_size": commit_every,
        }

    def _build_stock_from_cached_rows(
        self,
        engine: AKeyLevelEngine,
        rows_cache: dict[str, list[DailyBarRow]],
        symbol: str,
        *,
        trade_date: str,
    ) -> KeyLevelResult:
        rows = self._rows_for(engine, rows_cache, symbol, trade_date=trade_date)
        instrument = engine._instrument(symbol)
        return engine._build_from_rows(
            symbol=symbol,
            name=getattr(instrument, "name", "") or "",
            scope="stock",
            rows=rows,
            include_intraday=False,
        )

    def _build_sector_from_cached_rows(
        self,
        engine: AKeyLevelEngine,
        rows_cache: dict[str, list[DailyBarRow]],
        sector_key: str,
        *,
        trade_date: str,
    ) -> KeyLevelResult:
        symbols = engine._sector_symbols(sector_key, limit=30)
        rows_by_symbol = {
            symbol: self._rows_for(engine, rows_cache, symbol, trade_date=trade_date)
            for symbol in symbols
        }
        result = engine._build_from_rows(
            symbol=sector_key,
            name=sector_key,
            scope="sector",
            rows=_build_proxy_rows(rows_by_symbol, instrument_type="sector"),
            include_intraday=False,
        )
        if result.data_quality == "ok":
            result.data_quality = "research_only"
            result.warnings.append("板块关键位使用成分股等权代理序列，作为研究观察口径。")
        return result

    def _build_market_from_cached_rows(
        self,
        engine: AKeyLevelEngine,
        rows_cache: dict[str, list[DailyBarRow]],
        *,
        trade_date: str,
    ) -> KeyLevelResult:
        index_symbol = engine._market_index_symbol()
        if index_symbol:
            instrument = engine._instrument(index_symbol)
            rows = self._rows_for(engine, rows_cache, index_symbol, trade_date=trade_date)
            return engine._build_from_rows(
                symbol=index_symbol,
                name=getattr(instrument, "name", "") or "核心指数",
                scope="market",
                rows=rows,
                include_intraday=False,
            )
        stock_symbols = engine._stock_symbols(limit=80)
        rows_by_symbol = {
            symbol: self._rows_for(engine, rows_cache, symbol, trade_date=trade_date)
            for symbol in stock_symbols
        }
        result = engine._build_from_rows(
            symbol="market",
            name="大盘等权代理",
            scope="market",
            rows=_build_proxy_rows(rows_by_symbol, instrument_type="market"),
            include_intraday=False,
        )
        if result.data_quality == "ok":
            result.data_quality = "research_only"
            result.warnings.append("大盘关键位使用股票等权代理序列，作为研究观察口径。")
        return result

    def _rows_for(
        self,
        engine: AKeyLevelEngine,
        rows_cache: dict[str, list[DailyBarRow]],
        symbol: str,
        *,
        trade_date: str,
    ) -> list[DailyBarRow]:
        if symbol not in rows_cache:
            rows_cache[symbol] = engine._load_rows(symbol, trade_date=trade_date, lookback_days=120)
        return rows_cache[symbol]

    def _commit_progress(self, *, trade_date: str, phase: str, completed: int, total: int) -> None:
        _write_materialization_checkpoint(
            self.db,
            {
                "trade_date": trade_date,
                "phase": phase,
                "completed": completed,
                "total": total,
            },
        )
        self.db.commit()

    def _latest_trade_date(self) -> str | None:
        latest = self.db.execute(
            select(DailyBarSnapshot.trade_date)
            .order_by(DailyBarSnapshot.trade_date.desc())
            .limit(1)
        ).scalar()
        return str(latest)[:10] if latest else None

    def _stock_symbols(self, *, limit: int | None) -> list[str]:
        statement = (
            select(Instrument.symbol)
            .where(Instrument.instrument_type == "stock", Instrument.status == "active")
            .order_by(Instrument.symbol.asc())
        )
        if limit:
            statement = statement.limit(max(1, min(int(limit), 10000)))
        rows = self.db.execute(statement).scalars()
        return [str(row) for row in rows]

    def _sector_keys(self, *, limit: int | None) -> list[str]:
        statement = (
            select(Instrument.sector_name)
            .where(
                Instrument.instrument_type == "stock",
                Instrument.status == "active",
                Instrument.sector_name != "",
            )
            .distinct()
            .order_by(Instrument.sector_name.asc())
        )
        if limit:
            statement = statement.limit(max(1, min(int(limit), 1000)))
        rows = self.db.execute(statement).scalars()
        return [str(row) for row in rows if str(row or "").strip()]


def read_cached_key_level(
    db: Session,
    *,
    scope: str,
    key: str,
    trade_date: str | None = None,
) -> KeyLevelResult | None:
    return KeyLevelSnapshotRepository(db).read(scope=scope, cache_key=key, trade_date=trade_date)


def write_cached_key_level(db: Session, result: KeyLevelResult, *, key: str | None = None) -> None:
    KeyLevelSnapshotRepository(db).upsert(result, cache_key=key or result.symbol)


def cleanup_old_key_level_snapshots(db: Session, *, keep_trade_dates: int = 5) -> int:
    return KeyLevelSnapshotRepository(db).cleanup_old_trade_dates(keep_trade_dates=keep_trade_dates)


def blocked_key_level_result(*, scope: str, key: str, reason: str) -> KeyLevelResult:
    return KeyLevelResult(
        symbol=key,
        name=key,
        scope=scope,  # type: ignore[arg-type]
        trade_date=beijing_today().isoformat(),
        latest_price=0.0,
        engine_version="akey-level-v1",
        as_of=beijing_today().isoformat(),
        adjust_mode="qfq",
        intraday_included=False,
        data_quality="blocked",
        explanation="数据不足，仅观察。",
        warnings=[reason],
    )


def stale_key_level_result(*, scope: str, key: str, reason: str) -> KeyLevelResult:
    return KeyLevelResult(
        symbol=key,
        name=key,
        scope=scope,  # type: ignore[arg-type]
        trade_date=beijing_today().isoformat(),
        latest_price=0.0,
        engine_version="akey-level-v1",
        as_of=beijing_today().isoformat(),
        adjust_mode="qfq",
        intraday_included=False,
        data_quality="stale",
        explanation="数据不足，仅观察。",
        warnings=[reason],
    )


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _unique_non_empty(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _write_materialization_checkpoint(db: Session, payload: dict[str, Any]) -> None:
    key = f"akey_level_materialization_checkpoint:{str(payload.get('trade_date') or '')[:10]}"
    raw = _json_dumps(payload)
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        db.add(SystemSetting(key=key, value=raw))
    else:
        row.value = raw
