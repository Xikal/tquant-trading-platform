from __future__ import annotations

from collections.abc import Callable, Iterable

from app.services.market.shared import (
    Instrument,
    InstrumentOut,
    Session,
    _safe_str,
    func,
    guess_market,
    or_,
    select,
    sqlite3,
)


_ST_NAME_MARKERS = ("ST", "*ST", "退")
_ST_PREFIX_MARKERS = ("退市",)


class MarketInstrumentMixin:
    def sync_instruments(
        self,
        db: Session,
        kind: str = "all",
        progress_callback: Callable[[float, str, dict[str, int] | None], None] | None = None,
    ) -> dict[str, int]:
        counters = {"stock": 0, "etf": 0}
        if kind in {"all", "stock"}:
            try:
                _report_progress(progress_callback, 12.0, "正在读取 A 股股票资料", counters)
                counters["stock"] = self._sync_stock_instruments(db)
                _report_progress(progress_callback, 62.0, f"股票资料已写入 {counters['stock']} 条", counters)
            except Exception:
                _report_progress(progress_callback, 36.0, "股票数据源失败，使用本地种子兜底", counters)
                counters["stock"] = self._sync_seed_instruments(db, "stock")
                _report_progress(progress_callback, 62.0, f"股票兜底资料已写入 {counters['stock']} 条", counters)
        if kind in {"all", "etf"}:
            try:
                _report_progress(progress_callback, 70.0, "正在读取 ETF 资料", counters)
                counters["etf"] = self._sync_etf_instruments(db)
                _report_progress(progress_callback, 90.0, f"ETF 资料已写入 {counters['etf']} 条", counters)
            except Exception:
                _report_progress(progress_callback, 78.0, "ETF 数据源失败，使用本地种子兜底", counters)
                counters["etf"] = self._sync_seed_instruments(db, "etf")
                _report_progress(progress_callback, 90.0, f"ETF 兜底资料已写入 {counters['etf']} 条", counters)
        _report_progress(progress_callback, 96.0, "正在提交数据库变更", counters)
        db.commit()
        return counters

    def search_instruments(self, db: Session, keyword: str = "", kind: str = "all", page: int = 1, page_size: int = 50) -> list[InstrumentOut]:
        query = select(Instrument)
        if kind != "all":
            query = query.where(Instrument.instrument_type == kind)
        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.where(or_(Instrument.symbol.ilike(like), Instrument.name.ilike(like)))
        query = query.order_by(Instrument.symbol).offset((page - 1) * page_size).limit(page_size)
        return [
            InstrumentOut(symbol=row.symbol, name=row.name, market=row.market, instrument_type=row.instrument_type, sector_name=row.sector_name)
            for row in db.execute(query).scalars().all()
        ]

    def get_instrument(self, db: Session, symbol: str) -> Instrument:
        row = db.execute(select(Instrument).where(Instrument.symbol == symbol)).scalar_one_or_none()
        if row:
            if not row.sector_name or row.sector_name == "宽基/未识别":
                self._enrich_instrument_metadata(db, row)
            return row
        quote = self.get_quote(symbol)
        row = Instrument(symbol=symbol, name=quote.name or symbol, market=quote.market, instrument_type=quote.instrument_type, sector_name=self._infer_sector_name(quote.symbol, quote.name, quote.instrument_type))
        db.add(row)
        db.commit()
        db.refresh(row)
        self._enrich_instrument_metadata(db, row)
        return row

    def get_total_instruments(self, db: Session, kind: str = "all") -> int:
        query = select(func.count(Instrument.id))
        if kind != "all":
            query = query.where(Instrument.instrument_type == kind)
        return int(db.execute(query).scalar_one())

    def _sync_stock_instruments(self, db: Session) -> int:
        industry_by_symbol = self._load_industry_constituent_map()
        rows_result = self.provider_router.fetch_stock_instrument_rows()
        rows = rows_result.data or []
        if not rows:
            raise RuntimeError(rows_result.message or "stock instrument provider unavailable")
        total = self._upsert_frame(
            db,
            rows,
            symbol_keys=("code", "证券代码", "A股代码", "symbol"),
            name_keys=("name", "证券简称", "A股简称", "name"),
            instrument_type="stock",
            sector_by_symbol=industry_by_symbol,
        )
        return total

    def _sync_etf_instruments(self, db: Session) -> int:
        rows_result = self.provider_router.fetch_etf_instrument_rows()
        rows = rows_result.data or []
        if not rows:
            raise RuntimeError(rows_result.message or "etf instrument provider unavailable")
        return self._upsert_frame(
            db,
            self._normalize_sina_etf_rows(rows),
            symbol_keys=("代码", "symbol"),
            name_keys=("名称", "name"),
            instrument_type="etf",
        )

    def _count_existing_instruments(self, db: Session, instrument_type: str) -> int:
        return int(db.execute(select(func.count(Instrument.id)).where(Instrument.instrument_type == instrument_type)).scalar_one())

    def _sync_seed_instruments(self, db: Session, instrument_type: str) -> int:
        seed_rows = self._load_seed_instruments(instrument_type)
        if not seed_rows:
            return 0
        existing_by_symbol = {row.symbol: row for row in db.execute(select(Instrument)).scalars().all()}
        total = 0
        for symbol, name, market, sector_name in seed_rows:
            existing = existing_by_symbol.get(symbol)
            resolved_market = market or guess_market(symbol)
            resolved_name = name or symbol
            if existing is None:
                row = Instrument(symbol=symbol, name=resolved_name, market=resolved_market, instrument_type=instrument_type, sector_name=sector_name or self._infer_sector_name(symbol, resolved_name, instrument_type))
                db.add(row)
                existing_by_symbol[symbol] = row
            else:
                existing.name = resolved_name
                existing.market = resolved_market
                existing.instrument_type = instrument_type
                if sector_name:
                    existing.sector_name = sector_name
                elif not existing.sector_name:
                    existing.sector_name = self._infer_sector_name(symbol, resolved_name, instrument_type)
            total += 1
        return total

    def _load_seed_instruments(self, instrument_type: str) -> list[tuple[str, str, str, str | None]]:
        if not self.seed_database_path.exists():
            return []
        query = "SELECT symbol, name, market, sector_name FROM instruments WHERE instrument_type = ? ORDER BY symbol"
        try:
            with sqlite3.connect(self.seed_database_path) as connection:
                rows = connection.execute(query, (instrument_type,)).fetchall()
                return [(_safe_str(row[0]), _safe_str(row[1]), _safe_str(row[2]), _safe_str(row[3]) or None) for row in rows if row and row[0]]
        except sqlite3.Error:
            return []

    def _upsert_frame(
        self,
        db: Session,
        rows: Iterable[dict[str, object]],
        symbol_keys: tuple[str, ...],
        name_keys: tuple[str, ...],
        instrument_type: str,
        sector_by_symbol: dict[str, str] | None = None,
    ) -> int:
        sector_by_symbol = sector_by_symbol or {}
        normalized_rows = self._normalize_instrument_rows(
            rows=rows,
            symbol_keys=symbol_keys,
            name_keys=name_keys,
            instrument_type=instrument_type,
        )
        if not normalized_rows:
            return 0
        existing_by_symbol = self._load_existing_instruments(db, list(normalized_rows))
        total = 0
        for symbol, name in normalized_rows.items():
            market = guess_market(symbol)
            existing = existing_by_symbol.get(symbol)
            inferred_sector = sector_by_symbol.get(symbol)
            if not inferred_sector and instrument_type != "stock":
                inferred_sector = self._infer_sector_name(symbol, name, instrument_type)
            if existing is None:
                existing = Instrument(
                    symbol=symbol,
                    name=name or symbol,
                    market=market,
                    instrument_type=instrument_type,
                    sector_name=inferred_sector,
                )
                db.add(existing)
                existing_by_symbol[symbol] = existing
            else:
                existing.name = name or existing.name
                existing.market = market
                existing.instrument_type = instrument_type
                if inferred_sector and existing.sector_name != inferred_sector:
                    existing.sector_name = inferred_sector
            total += 1
        return total

    def _load_existing_instruments(self, db: Session, symbols: list[str]) -> dict[str, Instrument]:
        existing: dict[str, Instrument] = {}
        for chunk in _chunks(symbols, size=800):
            rows = db.execute(select(Instrument).where(Instrument.symbol.in_(chunk))).scalars().all()
            existing.update({row.symbol: row for row in rows})
        return existing

    def _normalize_instrument_rows(
        self,
        *,
        rows: Iterable[dict[str, object]],
        symbol_keys: tuple[str, ...],
        name_keys: tuple[str, ...],
        instrument_type: str,
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for row in rows:
            symbol = next((_safe_str(row.get(key)) for key in symbol_keys if row.get(key)), "")
            name = next((_safe_str(row.get(key)) for key in name_keys if row.get(key)), "")
            if not symbol:
                continue
            if instrument_type == "stock" and _is_st_or_delist_name(name):
                continue
            normalized[symbol] = name
        return normalized

    def _normalize_sina_etf_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for row in rows:
            symbol = str(row.get("代码", "")).lower().replace("sh", "").replace("sz", "")
            if symbol:
                normalized.append({"代码": symbol, "名称": row.get("名称", symbol)})
        return normalized

    def _enrich_instrument_metadata(self, db: Session, instrument: Instrument) -> None:
        inferred_sector = self._infer_sector_name(instrument.symbol, instrument.name, instrument.instrument_type)
        if inferred_sector and inferred_sector != instrument.sector_name:
            instrument.sector_name = inferred_sector
            db.commit()

    def _enrich_stock_industries_bulk(self, db: Session) -> int:
        industry_by_symbol = self._load_industry_constituent_map()
        if not industry_by_symbol:
            return 0
        rows = db.execute(
            select(Instrument).where(Instrument.instrument_type == "stock")
        ).scalars().all()
        updated = 0
        for row in rows:
            if _is_st_or_delist_name(row.name):
                continue
            sector_name = industry_by_symbol.get(row.symbol)
            if not sector_name or row.sector_name == sector_name:
                continue
            row.sector_name = sector_name
            updated += 1
        return updated

    def _load_industry_constituent_map(self) -> dict[str, str]:
        result = self.provider_router.fetch_industry_constituent_map()
        return dict(result.data or {})

    def _infer_sector_name(self, symbol: str, name: str, instrument_type: str) -> str | None:
        if instrument_type == "etf":
            return __import__("app.services.market.shared", fromlist=["MarketRuleService"]).MarketRuleService.infer_etf_theme(name)
        if _is_st_or_delist_name(name):
            return None
        result = self.provider_router.fetch_stock_industry(symbol)
        return str(result.data or "").strip() or None


def _chunks(items: list[str], *, size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def _is_st_or_delist_name(name: str) -> bool:
    upper_name = _safe_str(name).upper()
    return any(marker in upper_name for marker in _ST_NAME_MARKERS) or any(
        _safe_str(name).startswith(marker) for marker in _ST_PREFIX_MARKERS
    )


def _report_progress(
    callback: Callable[[float, str, dict[str, int] | None], None] | None,
    progress_pct: float,
    message: str,
    result: dict[str, int] | None = None,
) -> None:
    if callback is None:
        return
    try:
        callback(progress_pct, message, dict(result or {}))
    except Exception:
        return
