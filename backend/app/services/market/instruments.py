from __future__ import annotations

from typing import Iterable

from app.services.market.shared import (
    Instrument,
    InstrumentOut,
    Session,
    _safe_str,
    ak,
    func,
    guess_market,
    or_,
    select,
    sqlite3,
)


_ST_NAME_MARKERS = ("ST", "*ST", "退")
_ST_PREFIX_MARKERS = ("退市",)


class MarketInstrumentMixin:
    def sync_instruments(self, db: Session, kind: str = "all") -> dict[str, int]:
        counters = {"stock": 0, "etf": 0}
        if ak is None:
            if kind in {"all", "stock"}:
                counters["stock"] = self._sync_seed_instruments(db, "stock")
            if kind in {"all", "etf"}:
                counters["etf"] = self._sync_seed_instruments(db, "etf")
            db.commit()
            if kind in {"all", "stock"} and counters["stock"] == 0:
                counters["stock"] = self._count_existing_instruments(db, "stock")
            if kind in {"all", "etf"} and counters["etf"] == 0:
                counters["etf"] = self._count_existing_instruments(db, "etf")
            return counters
        if kind in {"all", "stock"}:
            try:
                counters["stock"] = self._sync_stock_instruments(db)
            except Exception:
                counters["stock"] = self._sync_seed_instruments(db, "stock")
        if kind in {"all", "etf"}:
            try:
                counters["etf"] = self._sync_etf_instruments(db)
            except Exception:
                counters["etf"] = self._sync_seed_instruments(db, "etf")
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
        total = self._upsert_frame(
            db,
            self._call_akshare(ak.stock_info_a_code_name, purpose="industry").to_dict("records"),
            symbol_keys=("code", "证券代码", "A股代码", "symbol"),
            name_keys=("name", "证券简称", "A股简称", "name"),
            instrument_type="stock",
            sector_by_symbol=industry_by_symbol,
        )
        return total

    def _sync_etf_instruments(self, db: Session) -> int:
        return self._upsert_frame(
            db,
            self._normalize_sina_etf_rows(
                self._call_akshare(
                    ak.fund_etf_category_sina,
                    symbol="ETF基金",
                    purpose="industry",
                ).to_dict("records")
            ),
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
        result = self._load_em_industry_constituent_map()
        sw_result = self._load_sw_industry_constituent_map()
        for symbol, industry in sw_result.items():
            result.setdefault(symbol, industry)
        return result

    def _load_em_industry_constituent_map(self) -> dict[str, str]:
        if ak is None:
            return {}
        try:
            industry_frame = self._call_akshare(ak.stock_board_industry_name_em, purpose="industry")
        except Exception:
            return {}
        industry_names = _extract_industry_names(industry_frame.to_dict("records"))
        result: dict[str, str] = {}
        for industry in industry_names:
            try:
                constituents = self._call_akshare(
                    ak.stock_board_industry_cons_em,
                    symbol=industry,
                    purpose="industry",
                )
            except Exception:
                continue
            for record in constituents.to_dict("records"):
                symbol = _extract_first_value(record, ("代码", "股票代码", "code", "symbol"))
                name = _extract_first_value(record, ("名称", "股票名称", "name", "证券简称"))
                if not symbol or _is_st_or_delist_name(name):
                    continue
                result.setdefault(symbol, industry)
        return result

    def _load_sw_industry_constituent_map(self) -> dict[str, str]:
        if ak is None:
            return {}
        try:
            history_frame = self._call_akshare(ak.stock_industry_clf_hist_sw, purpose="industry")
            category_frame = self._call_akshare(
                ak.stock_industry_category_cninfo,
                symbol="申银万国行业分类标准",
                purpose="industry",
            )
        except Exception:
            return {}
        category_map = _build_sw_category_map(category_frame.to_dict("records"))
        latest_by_symbol: dict[str, tuple[str, str, str]] = {}
        for row in history_frame.to_dict("records"):
            symbol = _extract_first_value(row, ("symbol", "股票代码", "代码"))
            industry_code = _extract_first_value(row, ("industry_code", "行业代码", "类目编码"))
            if not symbol or not industry_code:
                continue
            start_date = _extract_first_value(row, ("start_date", "开始日期"))
            update_time = _extract_first_value(row, ("update_time", "更新时间"))
            current = latest_by_symbol.get(symbol)
            marker = (start_date, update_time)
            if current is None or marker >= (current[1], current[2]):
                latest_by_symbol[symbol] = (industry_code, start_date, update_time)
        result: dict[str, str] = {}
        for symbol, (industry_code, _, _) in latest_by_symbol.items():
            industry = _resolve_sw_industry_name(industry_code, category_map)
            if industry:
                result[symbol] = industry
        return result

    def _infer_sector_name(self, symbol: str, name: str, instrument_type: str) -> str | None:
        if instrument_type == "etf":
            return __import__("app.services.market.shared", fromlist=["MarketRuleService"]).MarketRuleService.infer_etf_theme(name)
        if _is_st_or_delist_name(name):
            return None
        if ak is None:
            return None
        try:
            info_df = self._call_akshare(ak.stock_individual_info_em, symbol=symbol, purpose="industry")
            industry_values = info_df.loc[info_df["item"] == "行业", "value"].tolist()
            if industry_values:
                return str(industry_values[0]).strip()
        except Exception:
            return None
        return None


def _extract_industry_names(rows: Iterable[dict[str, object]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        industry = _extract_first_value(row, ("板块名称", "行业", "name", "industry"))
        if industry and industry not in names:
            names.append(industry)
    return names


def _extract_first_value(row: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _safe_str(row.get(key)).strip()
        if value:
            return value
    return ""


def _build_sw_category_map(rows: Iterable[dict[str, object]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        raw_code = _extract_first_value(row, ("类目编码", "code"))
        name = _extract_first_value(row, ("类目名称", "name"))
        if not raw_code or not name:
            continue
        code = raw_code.removeprefix("S")
        result[code] = name
    return result


def _resolve_sw_industry_name(industry_code: str, category_map: dict[str, str]) -> str:
    code = str(industry_code or "").strip().removeprefix("S")
    if not code:
        return ""
    for candidate in (code[:4], code[:6], code[:2], code):
        name = category_map.get(candidate)
        if name:
            return name
    return ""


def _chunks(items: list[str], *, size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def _is_st_or_delist_name(name: str) -> bool:
    upper_name = _safe_str(name).upper()
    return any(marker in upper_name for marker in _ST_NAME_MARKERS) or any(
        _safe_str(name).startswith(marker) for marker in _ST_PREFIX_MARKERS
    )
