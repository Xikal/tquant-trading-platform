from __future__ import annotations

import json
from datetime import datetime, time as dt_time

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import (
    DailyBarSnapshot,
    Instrument,
    LowBuyResultSnapshot,
    PaperPosition,
    StrategyTrackingSnapshot,
    UserWatchlist,
)
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.models.schemas import QuoteSnapshot
from app.services.agent_notification_service import AgentNotificationService
from app.core.config import get_settings
from app.services.market.local_quote_cache import (
    read_local_quote_snapshot,
    record_quote_cache_demand_coverage,
    write_local_quote_snapshots,
)
from app.services.market_data import MarketDataService

DEFAULT_LIMIT = 1200
WATCHLIST_CORE_LIMIT = 200
PRIORITY_CORE_LIMIT = 600
HOLDING_CORE_LIMIT = 300
STRATEGY_TRACKING_CORE_LIMIT = 300
MONITOR_SECTOR_LIMIT = 8
MONITOR_SECTOR_MEMBER_LIMIT = 30
QUOTE_CACHE_COVERAGE_TARGET = 0.9


class MarketQuoteCacheRefreshService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.market = MarketDataService()

    def refresh(self, *, limit: int = DEFAULT_LIMIT) -> dict[str, object]:
        symbols = self._target_symbols(limit=limit)
        if not symbols:
            return {"ok": True, "count": 0, "symbols": [], "message": "无可预热行情标的"}
        quotes = self._fetch_realtime_quotes(symbols)
        realtime_missing = [symbol for symbol in symbols if symbol not in quotes]
        if len(quotes) < len(symbols):
            quotes.update({symbol: quote for symbol, quote in self._daily_fallback_quotes(symbols).items() if symbol not in quotes})
        redis_written = write_local_quote_snapshots(quotes)
        cached_symbols = self._cached_symbols_after_write(symbols)
        unresolved_reasons = {
            symbol: "no_daily_bar"
            for symbol in realtime_missing
            if symbol not in quotes
        }
        coverage = record_quote_cache_demand_coverage(
            requested_symbols=symbols,
            cached_symbols=cached_symbols,
            target_ratio=QUOTE_CACHE_COVERAGE_TARGET,
            unresolved_reasons=unresolved_reasons,
        )
        alert = maybe_send_quote_cache_coverage_alert(coverage)
        return {
            "ok": True,
            "count": len(quotes),
            "redis_written": redis_written,
            "requested_count": len(symbols),
            "cached_count": len(cached_symbols),
            "coverage": coverage,
            "coverage_alert": alert,
            "missing_count": coverage["demand_miss_count"],
            "symbols": symbols[:20],
            "message": f"已刷新 {len(quotes)} 只标的本地行情缓存，Redis 写入 {redis_written} 条，可读 {len(cached_symbols)} 条",
        }

    def _fetch_realtime_quotes(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        if get_settings().market_quote_async_provider_enabled:
            async_batch = getattr(self.market, "get_quotes_batch_async_provider", None)
            if callable(async_batch):
                try:
                    return async_batch(symbols, force_refresh=True, allow_slow_fallback=True)
                except Exception:
                    pass
        return self.market.get_quotes_batch(symbols, force_refresh=True, allow_slow_fallback=True)

    def _cached_symbols_after_write(self, symbols: list[str]) -> list[str]:
        cached: list[str] = []
        for symbol in self._dedupe_symbols(symbols):
            if read_local_quote_snapshot(symbol) is not None:
                cached.append(symbol)
        return cached

    def _daily_fallback_quotes(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        cleaned = list(dict.fromkeys(symbol for symbol in symbols if symbol))
        if not cleaned:
            return {}
        latest_date = self.db.execute(select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1)).scalar()
        if not latest_date:
            return {}
        rows = self.db.execute(
            select(DailyBarSnapshot, Instrument.name)
            .outerjoin(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(DailyBarSnapshot.trade_date == latest_date)
            .where(DailyBarSnapshot.symbol.in_(cleaned))
        ).all()
        result: dict[str, QuoteSnapshot] = {}
        for row, name in rows:
            if not row.symbol or float(row.close_price or 0.0) <= 0:
                continue
            prev_close = float(row.pre_close or 0.0)
            close_price = float(row.close_price or 0.0)
            result[row.symbol] = QuoteSnapshot(
                symbol=row.symbol,
                name=str(name or row.symbol),
                market=str(row.market or "CN"),
                instrument_type=str(row.instrument_type or "stock"),
                last_price=close_price,
                change_pct=float(row.pct_chg or 0.0),
                change_amount=round(close_price - prev_close, 4) if prev_close else 0.0,
                open_price=float(row.open_price or 0.0),
                high_price=float(row.high_price or 0.0),
                low_price=float(row.low_price or 0.0),
                prev_close=prev_close,
                volume=float(row.volume or 0.0),
                amount=float(row.amount or 0.0),
                timestamp=str(row.trade_date),
                data_source="mysql_daily_bar_snapshot",
                source_quality="stale",
                data_quality="stale",
                data_quality_message="实时行情未命中，使用 MySQL 最新日线快照兜底。",
                is_stale=True,
            )
        return result

    def _target_symbols(self, *, limit: int) -> list[str]:
        core_symbols = self._core_demand_symbols()
        liquidity_limit = max(0, int(limit or DEFAULT_LIMIT) - len(core_symbols))
        symbols = [*core_symbols, *self._top_liquidity_symbols(limit=max(50, liquidity_limit))]
        return self._dedupe_symbols(symbols)

    def _core_demand_symbols(self) -> list[str]:
        symbols: list[str] = []
        symbols.extend(self._watchlist_symbols(limit=WATCHLIST_CORE_LIMIT))
        symbols.extend(self._priority_board_symbols(limit=PRIORITY_CORE_LIMIT))
        symbols.extend(self._paper_holding_symbols(limit=HOLDING_CORE_LIMIT))
        symbols.extend(self._strategy_tracking_symbols(limit=STRATEGY_TRACKING_CORE_LIMIT))
        symbols.extend(self._monitor_sector_member_symbols())
        return self._dedupe_symbols(symbols)

    def _dedupe_symbols(self, symbols: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for symbol in symbols:
            clean = str(symbol or "").strip()
            if len(clean) != 6 or clean in seen:
                continue
            seen.add(clean)
            ordered.append(clean)
        return ordered

    def _watchlist_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(UserWatchlist.symbol).order_by(UserWatchlist.updated_at.desc()).limit(limit)
        ).scalars().all()
        return [str(item) for item in rows if item]

    def _priority_board_symbols(self, *, limit: int) -> list[str]:
        latest_date = self.db.execute(
            select(LowBuyResultSnapshot.latest_trade_date)
            .group_by(LowBuyResultSnapshot.latest_trade_date)
            .order_by(desc(LowBuyResultSnapshot.latest_trade_date))
            .limit(1)
        ).scalar()
        if not latest_date:
            return []
        rows = self.db.execute(
            select(LowBuyResultSnapshot.symbol)
            .where(LowBuyResultSnapshot.latest_trade_date == latest_date)
            .order_by(
                LowBuyResultSnapshot.buy_signal_state.asc(),
                desc(LowBuyResultSnapshot.score),
                LowBuyResultSnapshot.symbol.asc(),
            )
            .limit(limit)
        ).scalars().all()
        return [str(item) for item in rows if item]

    def _paper_holding_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(PaperPosition.symbol)
            .where(PaperPosition.quantity > 0)
            .order_by(desc(PaperPosition.updated_at), PaperPosition.symbol.asc())
            .limit(limit)
        ).scalars().all()
        return [str(item) for item in rows if item]

    def _strategy_tracking_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(StrategyTrackingSnapshot.payload_json)
            .where(StrategyTrackingSnapshot.status == "fresh")
            .order_by(desc(StrategyTrackingSnapshot.generated_at))
            .limit(3)
        ).scalars().all()
        symbols: list[str] = []
        for payload_json in rows:
            symbols.extend(_strategy_tracking_payload_symbols(str(payload_json or ""), remaining=limit - len(symbols)))
            if len(symbols) >= limit:
                break
        return symbols[:limit]

    def _monitor_sector_member_symbols(self) -> list[str]:
        latest_date = self.db.execute(select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1)).scalar()
        if not latest_date:
            return []
        sector_rows = self.db.execute(
            select(
                Instrument.sector_name,
                func.sum(DailyBarSnapshot.amount).label("sector_amount"),
            )
            .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(DailyBarSnapshot.trade_date == latest_date)
            .where(DailyBarSnapshot.instrument_type == "stock")
            .where(Instrument.sector_name.isnot(None))
            .where(Instrument.sector_name != "")
            .group_by(Instrument.sector_name)
            .order_by(desc("sector_amount"))
            .limit(MONITOR_SECTOR_LIMIT)
        ).all()
        sectors = [str(sector) for sector, _amount in sector_rows if sector]
        if not sectors:
            return []
        rows = self.db.execute(
            select(DailyBarSnapshot.symbol)
            .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(DailyBarSnapshot.trade_date == latest_date)
            .where(DailyBarSnapshot.instrument_type == "stock")
            .where(Instrument.sector_name.in_(sectors))
            .order_by(Instrument.sector_name.asc(), desc(DailyBarSnapshot.amount), DailyBarSnapshot.symbol.asc())
            .limit(MONITOR_SECTOR_LIMIT * MONITOR_SECTOR_MEMBER_LIMIT)
        ).scalars().all()
        return [str(item) for item in rows if item]

    def _top_liquidity_symbols(self, *, limit: int) -> list[str]:
        latest_date = self.db.execute(select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1)).scalar()
        if not latest_date:
            return []
        rows = self.db.execute(
            select(DailyBarSnapshot.symbol)
            .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(DailyBarSnapshot.trade_date == latest_date)
            .where(~Instrument.name.like("ST%"))
            .where(~Instrument.name.like("*ST%"))
            .where(~DailyBarSnapshot.symbol.like("30%"))
            .where(~DailyBarSnapshot.symbol.like("68%"))
            .order_by(DailyBarSnapshot.amount.desc())
            .limit(limit)
        ).scalars().all()
        return [str(item) for item in rows if item]


def quote_cache_refresh_due(now: datetime | None = None) -> bool:
    current = now or beijing_now()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    morning = dt_time(9, 25) <= current_time <= dt_time(11, 31)
    afternoon = dt_time(12, 55) <= current_time <= dt_time(15, 5)
    return morning or afternoon


def quote_cache_refresh_bucket(now: datetime | None = None) -> str:
    current = now or beijing_now()
    bucket_minute = (current.minute // 1)
    return current.strftime(f"%Y%m%d%H{bucket_minute:02d}")


def maybe_send_quote_cache_coverage_alert(coverage: dict[str, object]) -> dict[str, object]:
    if not coverage.get("coverage_below_target"):
        return {"ok": True, "sent": False, "reason": "coverage_ok"}
    service = AgentNotificationService()
    if not service.supports_channel("feishu"):
        return {"ok": True, "sent": False, "reason": "notification_channel_not_configured"}
    response = service.send_test(
        AgentNotificationTestRequest(
            channel="feishu",
            message=(
                "quote_cache_coverage_below_target: "
                f"coverage={coverage.get('coverage_ratio')} "
                f"demand={coverage.get('demand_count')} "
                f"missing={coverage.get('demand_miss_count')} "
                f"sample={coverage.get('missing_symbols_sample')}"
            ),
        )
    )
    return {"ok": bool(response.ok), "sent": bool(response.ok), "reason": response.message, "code": response.code}


def _strategy_tracking_payload_symbols(payload_json: str, *, remaining: int) -> list[str]:
    if remaining <= 0:
        return []
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError):
        return []
    raw_items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        return []
    symbols: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip()
        if len(symbol) == 6:
            symbols.append(symbol)
        if len(symbols) >= remaining:
            break
    return symbols
