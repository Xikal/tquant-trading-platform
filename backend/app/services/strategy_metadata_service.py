from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, Instrument, StrategyMetadata, StrategyPreset
from app.models.schema_defs.strategy_meta import (
    StrategyMetaOut,
    StrategyMetaResponse,
    StrategyPresetOut,
    StrategyPresetResponse,
    SymbolSearchItem,
    SymbolSearchResponse,
)


@dataclass(frozen=True)
class StrategyDisplaySeed:
    key: str
    name: str
    description: str
    category: str
    risk_level: str
    typical_holding_days: str
    sort_order: int


DEFAULT_STRATEGY_META: tuple[StrategyDisplaySeed, ...] = (
    StrategyDisplaySeed("first_board", "首板回调", "首板启动后回调承接，偏事件低吸。", "生产策略", "medium", "1-3天", 10),
    StrategyDisplaySeed("volume_shrink", "量能低吸", "放量启动后缩量回踩，等待承接修复。", "生产策略", "medium", "1-3天", 20),
    StrategyDisplaySeed("late_session_strong_support", "收盘强势承接", "主线标的收盘仍有承接，关注次日冲高兑现。", "辅助策略", "medium", "1-2天", 30),
    StrategyDisplaySeed("core_midcap_vwap_ma5_retrace", "中军回踩", "板块核心中军回踩均线/VWAP 附近的低吸观察。", "辅助策略", "medium", "2-4天", 40),
    StrategyDisplaySeed("sector_mainline_first_divergence_low_buy", "主线首分歧", "主线板块首次有效分歧后的修复低吸观察。", "辅助策略", "high", "1-3天", 50),
)

DEFAULT_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "key": "quick_check",
        "name": "快速体检",
        "description": "全策略最近半年快速扫描，适合日常看策略状态。",
        "sort_order": 10,
        "config": {
            "range": "6m",
            "initial_capital": 500000,
            "strategies": [seed.key for seed in DEFAULT_STRATEGY_META],
            "execution_model": "open_price",
            "max_position_pct": 30,
            "max_single_order_pct": 15,
            "max_positions": 8,
            "max_daily_loss_pct": 5,
            "min_cash_reserve": 5000,
            "stop_loss_pct": -5,
            "take_profit_pct": 10,
            "benchmark": "000300",
        },
    },
    {
        "key": "annual_review",
        "name": "年度回顾",
        "description": "最近 1 年全策略回测，适合复盘策略稳定性。",
        "sort_order": 20,
        "config": {
            "range": "12m",
            "initial_capital": 500000,
            "strategies": [seed.key for seed in DEFAULT_STRATEGY_META],
            "execution_model": "vwap",
            "max_position_pct": 30,
            "max_single_order_pct": 15,
            "max_positions": 8,
            "max_daily_loss_pct": 5,
            "min_cash_reserve": 5000,
            "stop_loss_pct": -5,
            "take_profit_pct": 10,
            "benchmark": "000300",
        },
    },
    {
        "key": "full_validation",
        "name": "完整检验",
        "description": "最近 2 年保守成交模型，适合上线前检查。",
        "sort_order": 30,
        "config": {
            "range": "24m",
            "initial_capital": 500000,
            "strategies": [seed.key for seed in DEFAULT_STRATEGY_META],
            "execution_model": "open_price",
            "max_position_pct": 30,
            "max_single_order_pct": 15,
            "max_positions": 8,
            "max_daily_loss_pct": 5,
            "min_cash_reserve": 5000,
            "stop_loss_pct": -5,
            "take_profit_pct": 10,
            "benchmark": "000300",
        },
    },
)


class StrategyMetadataService:
    def __init__(self, db: Session):
        self.db = db

    def list_strategy_meta(self) -> StrategyMetaResponse:
        overrides = self._load_metadata_overrides()
        items = []
        for seed in DEFAULT_STRATEGY_META:
            row = overrides.get(seed.key)
            items.append(
                StrategyMetaOut(
                    key=seed.key,
                    name=row.display_name if row else seed.name,
                    display_name=row.display_name if row else seed.name,
                    description=row.description if row and row.description else seed.description,
                    category=row.category if row and row.category else seed.category,
                    risk_level=row.risk_level if row and row.risk_level else seed.risk_level,
                    typical_holding_days=(
                        row.typical_holding_days if row and row.typical_holding_days else seed.typical_holding_days
                    ),
                    sort_order=row.sort_order if row else seed.sort_order,
                )
            )
        items.sort(key=lambda item: (item.sort_order, item.key))
        return StrategyMetaResponse(strategies=items)

    def list_presets(self) -> StrategyPresetResponse:
        rows = self._load_preset_rows()
        if not rows:
            return StrategyPresetResponse(presets=[_preset_from_seed(item) for item in DEFAULT_PRESETS])
        return StrategyPresetResponse(presets=[_preset_from_row(row) for row in rows])

    def search_symbols(self, query: str, limit: int = 10) -> SymbolSearchResponse:
        keyword = query.strip()
        if not keyword:
            return SymbolSearchResponse(items=[], total=0)
        safe_limit = max(1, min(limit, 20))
        rows = self._search_instruments(keyword, safe_limit)
        total = self._count_instruments(keyword)
        fallback_symbols: list[str] = []
        if len(rows) < safe_limit:
            fallback_symbols = self._search_daily_bar_symbols(
                keyword=keyword,
                limit=safe_limit - len(rows),
                excluded={row.symbol for row in rows},
            )
            total += self._count_daily_bar_symbols(keyword, excluded={row.symbol for row in rows})
        prices = self._latest_prices([row.symbol for row in rows] + fallback_symbols)
        items = [
            SymbolSearchItem(
                symbol=row.symbol,
                name=row.name or "",
                latest_price=prices.get(row.symbol),
                industry=row.sector_name or "",
                market=row.market or "",
                instrument_type=row.instrument_type or "stock",
            )
            for row in rows
        ]
        items.extend(
            SymbolSearchItem(
                symbol=symbol,
                name=symbol,
                latest_price=prices.get(symbol),
                market="CN",
                instrument_type="stock",
            )
            for symbol in fallback_symbols
        )
        return SymbolSearchResponse(items=items, total=total)

    def _load_metadata_overrides(self) -> dict[str, StrategyMetadata]:
        try:
            rows = self.db.execute(select(StrategyMetadata)).scalars().all()
        except SQLAlchemyError:
            return {}
        return {row.key: row for row in rows}

    def _load_preset_rows(self) -> list[StrategyPreset]:
        try:
            return list(
                self.db.execute(select(StrategyPreset).order_by(StrategyPreset.sort_order.asc(), StrategyPreset.id.asc()))
                .scalars()
                .all()
            )
        except SQLAlchemyError:
            return []

    def _search_instruments(self, keyword: str, limit: int) -> list[Instrument]:
        escaped = _escape_like(keyword)
        pattern = f"%{escaped}%"
        prefix = f"{escaped}%"
        statement = (
            select(Instrument)
            .where(
                or_(
                    Instrument.symbol.like(prefix, escape="\\"),
                    Instrument.name.like(pattern, escape="\\"),
                    Instrument.sector_name.like(pattern, escape="\\"),
                )
            )
            .order_by(Instrument.instrument_type.asc(), Instrument.symbol.asc())
            .limit(limit)
        )
        return list(self.db.execute(statement).scalars().all())

    def _count_instruments(self, keyword: str) -> int:
        escaped = _escape_like(keyword)
        pattern = f"%{escaped}%"
        prefix = f"{escaped}%"
        statement = select(func.count(Instrument.id)).where(
            or_(
                Instrument.symbol.like(prefix, escape="\\"),
                Instrument.name.like(pattern, escape="\\"),
                Instrument.sector_name.like(pattern, escape="\\"),
            )
        )
        return int(self.db.execute(statement).scalar() or 0)

    def _search_daily_bar_symbols(self, keyword: str, limit: int, excluded: set[str]) -> list[str]:
        latest_date = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest_date:
            return []
        prefix = f"{_escape_like(keyword)}%"
        statement = (
            select(distinct(DailyBarSnapshot.symbol))
            .where(
                DailyBarSnapshot.trade_date == latest_date,
                DailyBarSnapshot.symbol.like(prefix, escape="\\"),
            )
            .order_by(DailyBarSnapshot.symbol.asc())
            .limit(limit + len(excluded))
        )
        symbols = [str(row[0]) for row in self.db.execute(statement).all()]
        return [symbol for symbol in symbols if symbol not in excluded][:limit]

    def _count_daily_bar_symbols(self, keyword: str, excluded: set[str]) -> int:
        latest_date = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest_date:
            return 0
        prefix = f"{_escape_like(keyword)}%"
        statement = select(func.count(distinct(DailyBarSnapshot.symbol))).where(
            DailyBarSnapshot.trade_date == latest_date,
            DailyBarSnapshot.symbol.like(prefix, escape="\\"),
        )
        if excluded:
            statement = statement.where(DailyBarSnapshot.symbol.notin_(excluded))
        return int(self.db.execute(statement).scalar() or 0)

    def _latest_prices(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        latest_date = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest_date:
            return {}
        rows = self.db.execute(
            select(DailyBarSnapshot.symbol, DailyBarSnapshot.close_price).where(
                DailyBarSnapshot.trade_date == latest_date,
                DailyBarSnapshot.symbol.in_(symbols),
            )
        ).all()
        return {str(symbol): float(price or 0) for symbol, price in rows}


def _preset_from_seed(item: dict[str, Any]) -> StrategyPresetOut:
    return StrategyPresetOut(
        id=None,
        key=str(item["key"]),
        name=str(item["name"]),
        description=str(item.get("description") or ""),
        config=dict(item.get("config") or {}),
        sort_order=int(item.get("sort_order") or 0),
    )


def _preset_from_row(row: StrategyPreset) -> StrategyPresetOut:
    try:
        config = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    return StrategyPresetOut(
        id=row.id,
        key=str(row.preset_key or row.id),
        name=row.name,
        description=row.description or "",
        config=config,
        sort_order=row.sort_order or 0,
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
