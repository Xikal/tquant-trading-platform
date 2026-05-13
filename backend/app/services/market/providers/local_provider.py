from __future__ import annotations

import json

from sqlalchemy import func, select
import pandas as pd

from app.core.database import SessionLocal
from app.models.entities import DailyBarSnapshot, Instrument, LowBuyHotIndustrySnapshot
from app.models.schemas import SectorSnapshot
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


class LocalMarketProvider:
    """Local factual market data provider backed by materialized DB snapshots."""

    name = "local"

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult[pd.DataFrame]:
        start_iso = _date_iso(start_date)
        end_iso = _date_iso(end_date)
        with SessionLocal() as db:
            rows = (
                db.execute(
                    select(DailyBarSnapshot)
                    .where(
                        DailyBarSnapshot.symbol == symbol,
                        DailyBarSnapshot.trade_date >= start_iso,
                        DailyBarSnapshot.trade_date <= end_iso,
                    )
                    .order_by(DailyBarSnapshot.trade_date.asc())
                )
                .scalars()
                .all()
            )
        frame = pd.DataFrame(
            [
                {
                    "date": row.trade_date,
                    "open": float(row.open_price or 0),
                    "close": float(row.close_price or 0),
                    "high": float(row.high_price or 0),
                    "low": float(row.low_price or 0),
                    "volume": float(row.volume or 0),
                    "amount": float(row.amount or 0),
                    "pct_chg": float(row.pct_chg or 0),
                }
                for row in rows
            ]
        )
        return _daily_history_result(frame, end_iso)

    def fetch_trade_dates(self) -> ProviderResult[list[str]]:
        with SessionLocal() as db:
            rows = (
                db.execute(
                    select(DailyBarSnapshot.trade_date)
                    .group_by(DailyBarSnapshot.trade_date)
                    .order_by(DailyBarSnapshot.trade_date.asc())
                )
                .scalars()
                .all()
            )
        return ProviderResult(
            quality=MarketDataQuality.FRESH if rows else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=list(rows) or None,
            message="" if rows else "local trade dates unavailable",
        )

    def fetch_sector_fund_flow_rank(self) -> ProviderResult[pd.DataFrame]:
        with SessionLocal() as db:
            latest = _latest_daily_trade_date(db)
            if not latest:
                return _unavailable("local sector flow unavailable: no daily bars")
            rows = (
                db.execute(
                    select(
                        Instrument.sector_name,
                        func.sum(DailyBarSnapshot.amount),
                        func.avg(DailyBarSnapshot.pct_chg),
                        func.count(DailyBarSnapshot.symbol),
                    )
                    .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
                    .where(
                        DailyBarSnapshot.trade_date == latest,
                        Instrument.sector_name.is_not(None),
                        Instrument.sector_name != "",
                    )
                    .group_by(Instrument.sector_name)
                    .order_by(func.sum(DailyBarSnapshot.amount).desc())
                    .limit(120)
                )
                .all()
            )
        frame = pd.DataFrame(
            [
                {
                    "行业": sector,
                    "净流入": float(amount or 0),
                    "涨跌幅": float(avg_pct or 0),
                    "成分数": int(count or 0),
                }
                for sector, amount, avg_pct, count in rows
            ]
        )
        if frame.empty:
            return _unavailable("local sector flow unavailable: empty sector map")
        return ProviderResult(quality=MarketDataQuality.STALE, source=self.name, data=frame)

    def fetch_sector_fund_flow(self, period: str = "today", sector_type: str = "industry", limit: int = 30) -> ProviderResult:
        """Local provider does not support multi-period fund flow; delegate to rank."""
        return self.fetch_sector_fund_flow_rank()

    def fetch_limit_up_snapshot(self) -> ProviderResult[pd.DataFrame]:
        with SessionLocal() as db:
            latest = _latest_daily_trade_date(db)
            if not latest:
                return _unavailable("local limit-up snapshot unavailable: no daily bars")
            rows = (
                db.execute(
                    select(DailyBarSnapshot, Instrument.name, Instrument.sector_name)
                    .outerjoin(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
                    .where(
                        DailyBarSnapshot.trade_date == latest,
                        DailyBarSnapshot.pct_chg >= 9.5,
                    )
                    .order_by(DailyBarSnapshot.amount.desc())
                    .limit(500)
                )
                .all()
            )
        frame = pd.DataFrame(
            [
                {
                    "代码": bar.symbol,
                    "名称": name or bar.symbol,
                    "行业": sector or "",
                    "涨跌幅": float(bar.pct_chg or 0),
                    "成交额": float(bar.amount or 0),
                }
                for bar, name, sector in rows
            ]
        )
        if frame.empty:
            return _unavailable("local limit-up snapshot unavailable: no local limit-up rows")
        return ProviderResult(quality=MarketDataQuality.STALE, source=self.name, data=frame)

    def fetch_industry_constituent_map(self) -> ProviderResult[dict[str, str]]:
        with SessionLocal() as db:
            rows = db.execute(
                select(Instrument.symbol, Instrument.sector_name).where(
                    Instrument.sector_name.is_not(None),
                    Instrument.sector_name != "",
                )
            ).all()
        mapping = {symbol: sector for symbol, sector in rows if symbol and sector}
        return ProviderResult(
            quality=MarketDataQuality.STALE if mapping else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=mapping or None,
            message="" if mapping else "local industry map unavailable",
        )

    def fetch_stock_industry(self, symbol: str) -> ProviderResult[str]:
        with SessionLocal() as db:
            sector = db.execute(
                select(Instrument.sector_name).where(Instrument.symbol == symbol)
            ).scalar()
        return ProviderResult(
            quality=MarketDataQuality.STALE if sector else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=sector or None,
            message="" if sector else "local stock industry unavailable",
        )

    def fetch_sector_heatmap(self) -> ProviderResult:
        with SessionLocal() as db:
            row = (
                db.execute(
                    select(LowBuyHotIndustrySnapshot)
                    .order_by(LowBuyHotIndustrySnapshot.latest_trade_date.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
        if row is None or not row.industries_json:
            return _unavailable("local sector heatmap unavailable")
        try:
            industries = json.loads(row.industries_json)
        except Exception:
            industries = []
        snapshots = [
            SectorSnapshot(
                sector_name=str(item),
                sector_strength=max(40.0, 80.0 - index * 4),
                market_strength=60.0,
                alignment_score=max(40.0, 76.0 - index * 3),
                notes="来自本地热点行业快照，作为外部源不可用时的降级参考。",
            )
            for index, item in enumerate(industries[:30])
            if item
        ]
        if not snapshots:
            return _unavailable("local sector heatmap unavailable: empty hot industries")
        return ProviderResult(quality=MarketDataQuality.STALE, source=self.name, data=snapshots)

    def __getattr__(self, name: str):
        if name.startswith("fetch_"):
            return lambda *_, **__: ProviderResult(
                quality=MarketDataQuality.UNAVAILABLE,
                source=self.name,
                message=f"{name} not provided by local snapshot provider",
            )
        raise AttributeError(name)


def _date_iso(value: str) -> str:
    clean = str(value or "").strip()
    if len(clean) == 8 and clean.isdigit():
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:]}"
    return clean


def _unavailable(message: str) -> ProviderResult:
    return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=LocalMarketProvider.name, message=message)


def _latest_daily_trade_date(db) -> str:
    return str(db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar() or "")


def _daily_history_result(frame: pd.DataFrame, expected_end_date: str) -> ProviderResult[pd.DataFrame]:
    if frame.empty:
        return _unavailable("local daily bars unavailable")
    latest_local_date = str(frame["date"].iloc[-1])
    row_count = len(frame)
    if row_count >= 60 and latest_local_date >= expected_end_date:
        return ProviderResult(quality=MarketDataQuality.FRESH, source=LocalMarketProvider.name, data=frame)
    if row_count >= 20:
        return ProviderResult(
            quality=MarketDataQuality.ESTIMATED,
            source=LocalMarketProvider.name,
            data=frame,
            message=f"limited_history: rows={row_count}, latest={latest_local_date}, expected={expected_end_date}",
        )
    return ProviderResult(
        quality=MarketDataQuality.STALE,
        source=LocalMarketProvider.name,
        data=frame,
        message=f"partial_local_history: rows={row_count}, latest={latest_local_date}, expected={expected_end_date}",
    )
