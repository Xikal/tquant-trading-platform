from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.entities import DailyBarSnapshot, Instrument, MarketHourlySnapshotHistory
from app.models.schema_defs.market import (
    MarketBreadthResponse,
    SectorRelativeStrengthItem,
    SectorRelativeStrengthResponse,
)


@dataclass
class MarketAutofillResult:
    market_breadth: MarketBreadthResponse | None = None
    sector_relative_strength: SectorRelativeStrengthResponse | None = None
    details: list[dict[str, Any]] = field(default_factory=list)


class MarketDataAutofillService:
    """Best-effort market data completion before pulse/review generation.

    Autofill never upgrades derived data to fresh. It records source/method so
    downstream review text can separate "still missing" from "conservatively
    filled".
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def fill_for_pulse(
        self,
        *,
        market_breadth: MarketBreadthResponse | None,
        sector_relative_strength: SectorRelativeStrengthResponse | None,
        trade_date: str = "",
        cutoff_time: str = "",
    ) -> MarketAutofillResult:
        details: list[dict[str, Any]] = []
        breadth = market_breadth
        if breadth is not None and not breadth.hourly_all_market_snapshot:
            hourly = self.latest_valid_hourly_snapshot(trade_date=trade_date, cutoff_time=cutoff_time)
            if hourly:
                breadth = breadth.model_copy(update={"hourly_all_market_snapshot": hourly})
                details.append(
                    _detail(
                        "hourly_all_market_snapshot",
                        "last_valid_snapshot",
                        "使用同日最近有效全市场小时快照补齐",
                        count=hourly.get("snapshot_count"),
                    )
                )
        if breadth is not None and not breadth.emotion_ready:
            emotion = self._derive_emotion_from_breadth(breadth)
            breadth = breadth.model_copy(
                update={
                    "emotion_ready": True,
                    "emotion_temperature": emotion["emotion_temperature"],
                    "emotion_temperature_text": emotion["emotion_temperature_text"],
                    "emotion_temperature_score": emotion["emotion_temperature_score"],
                    "data_quality": _downgrade_quality(breadth.data_quality),
                    "data_quality_text": _append_quality_note(
                        breadth.data_quality_text,
                        "情绪温度由市场涨跌面保守派生",
                    ),
                }
            )
            details.append(
                _detail(
                    "emotion_temperature",
                    "derived_from_breadth",
                    "情绪温度由涨跌比例、中位涨跌幅和强弱股数量保守派生",
                    score=emotion["emotion_temperature_score"],
                    text=emotion["emotion_temperature_text"],
                )
            )
        sector_strength = sector_relative_strength
        if sector_strength is None or not getattr(sector_strength, "items", []):
            sector_strength = self._load_sector_strength_fallback()
            if sector_strength is not None and sector_strength.items:
                details.append(
                    _detail(
                        "sector_relative_strength",
                        "daily_bar_rank",
                        "使用最新日线和行业映射补齐板块/龙头强度",
                        count=len(sector_strength.items),
                    )
                )
            elif breadth is not None:
                sector_strength = self._derive_leader_strength_from_hourly(breadth.hourly_all_market_snapshot)
                if sector_strength is not None and sector_strength.items:
                    details.append(
                        _detail(
                            "sector_relative_strength",
                            "derived_from_market_breadth",
                            "无行业映射时用全市场强势扩散代理龙头强度",
                            count=len(sector_strength.items),
                        )
                    )
        if breadth is not None and details:
            breadth = breadth.model_copy(update={"autofill_details": details, "data_quality": _downgrade_quality(breadth.data_quality)})
        return MarketAutofillResult(
            market_breadth=breadth,
            sector_relative_strength=sector_strength,
            details=details,
        )

    def latest_valid_hourly_snapshot(self, trade_date: str = "", cutoff_time: str = "") -> dict[str, Any]:
        statement = select(MarketHourlySnapshotHistory)
        if trade_date:
            statement = statement.where(MarketHourlySnapshotHistory.trade_date == trade_date)
        rows = self.db.execute(
            statement.order_by(desc(MarketHourlySnapshotHistory.snapshot_bucket), desc(MarketHourlySnapshotHistory.id)).limit(24)
        ).scalars().all()
        for row in rows:
            payload = _json_dict(row.payload_json)
            if cutoff_time and str(payload.get("updated_at") or "")[11:19] > cutoff_time:
                continue
            if payload.get("ok") and int(payload.get("snapshot_count") or 0) > 0:
                return payload
        return {}

    def _derive_emotion_from_breadth(self, breadth: MarketBreadthResponse) -> dict[str, Any]:
        hourly = dict(breadth.hourly_all_market_snapshot or {})
        up_ratio = _float(hourly.get("stock_up_ratio"), breadth.stock_up_ratio)
        median_change = _float(hourly.get("stock_median_change"), breadth.stock_median_change)
        strong_count = int(_float(hourly.get("strong_count"), 0.0))
        weak_count = int(_float(hourly.get("weak_count"), 0.0))
        score = 50.0 + (up_ratio - 0.5) * 80.0 + median_change * 5.0 + min(strong_count - weak_count, 1000) / 1000.0 * 18.0
        score = max(0.0, min(100.0, score))
        if score < 30:
            key = "cold"
            text = "冷区：由市场涨跌面推断，短线情绪偏弱"
        elif score < 58:
            key = "warm"
            text = "温区：由市场涨跌面推断，情绪中性偏稳"
        elif score < 78:
            key = "hot"
            text = "热区：由市场涨跌面推断，情绪活跃"
        else:
            key = "overheated"
            text = "过热区：由市场涨跌面推断，注意兑现压力"
        return {
            "emotion_temperature": key,
            "emotion_temperature_text": f"{text}（派生）",
            "emotion_temperature_score": round(score, 2),
        }

    def _load_sector_strength_fallback(self) -> SectorRelativeStrengthResponse | None:
        target_date = self._latest_complete_trade_date()
        if not target_date:
            return None
        rows = self._load_daily_sector_rows(target_date)
        if not rows:
            return None
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["sector_name"]), []).append(row)
        sectors = sorted(
            grouped,
            key=lambda sector: median([float(item["change_pct"]) for item in grouped[sector]]),
            reverse=True,
        )[:8]
        items: list[SectorRelativeStrengthItem] = []
        for sector in sectors:
            sector_rows = grouped[sector]
            sector_median = median([float(item["change_pct"]) for item in sector_rows])
            ranked = sorted(
                sector_rows,
                key=lambda item: (float(item["change_pct"]) - sector_median) * 6 + min(float(item["amount"]) / 100000000.0, 12.0),
                reverse=True,
            )
            for rank, row in enumerate(ranked[:3], start=1):
                change_pct = float(row["change_pct"])
                items.append(
                    SectorRelativeStrengthItem(
                        sector_name=sector,
                        symbol=str(row["symbol"]),
                        name=str(row["name"]),
                        latest_price=float(row["close_price"]),
                        change_pct=change_pct,
                        sector_median_change_pct=round(float(sector_median), 4),
                        relative_strength_ratio=None if abs(sector_median) < 0.1 else round(change_pct / sector_median, 4),
                        turnover_proxy=round(float(row["amount"]) / 100000000.0, 4),
                        leader_score=round(max(0.0, min(100.0, 50.0 + (change_pct - sector_median) * 6.0)), 2),
                        rank=rank,
                        data_quality_text="自动补全：使用最新日线和行业映射代理板块/龙头强度。",
                    )
                )
        return SectorRelativeStrengthResponse(
            updated_at=beijing_now_string(),
            trade_date=str(target_date),
            sector_count=len(sectors),
            items=items,
            notes=["自动补全：实时板块强度不可用，使用最新完整日线代理。"],
        )

    def _derive_leader_strength_from_hourly(self, hourly: dict[str, Any]) -> SectorRelativeStrengthResponse | None:
        if not hourly or int(hourly.get("snapshot_count") or 0) <= 0:
            return None
        strong_count = int(hourly.get("strong_count") or 0)
        weak_count = int(hourly.get("weak_count") or 0)
        score = max(0.0, min(100.0, 50.0 + (strong_count - weak_count) / max(int(hourly.get("snapshot_count") or 1), 1) * 100.0))
        item = SectorRelativeStrengthItem(
            sector_name="全市场强势扩散",
            symbol="MARKET",
            name="全市场代理",
            latest_price=0.0,
            change_pct=float(hourly.get("stock_median_change") or 0.0),
            sector_median_change_pct=float(hourly.get("stock_median_change") or 0.0),
            leader_score=round(score, 2),
            rank=1,
            data_quality_text="自动补全：缺少行业映射时，用强势股与弱势股扩散度代理。",
        )
        return SectorRelativeStrengthResponse(
            updated_at=beijing_now_string(),
            trade_date=str(hourly.get("updated_at") or "")[:10],
            sector_count=1,
            items=[item],
            notes=["自动补全：当前不是行业龙头排行，只是全市场强势扩散代理。"],
        )

    def _latest_complete_trade_date(self) -> str:
        rows = self.db.execute(
            select(DailyBarSnapshot.trade_date, func.count(DailyBarSnapshot.symbol).label("stock_count"))
            .where(DailyBarSnapshot.instrument_type == "stock")
            .group_by(DailyBarSnapshot.trade_date)
            .having(func.count(DailyBarSnapshot.symbol) >= 3000)
            .order_by(desc(DailyBarSnapshot.trade_date))
            .limit(1)
        ).all()
        return str(rows[0][0]) if rows else ""

    def _load_daily_sector_rows(self, trade_date: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(
                DailyBarSnapshot.symbol,
                Instrument.name,
                Instrument.sector_name,
                DailyBarSnapshot.close_price,
                DailyBarSnapshot.pct_chg,
                DailyBarSnapshot.amount,
            )
            .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(
                DailyBarSnapshot.trade_date == trade_date,
                DailyBarSnapshot.instrument_type == "stock",
                Instrument.sector_name.isnot(None),
            )
        ).all()
        return [
            {
                "symbol": str(symbol),
                "name": str(name or symbol),
                "sector_name": str(sector_name or ""),
                "close_price": float(close_price or 0.0),
                "change_pct": float(pct_chg or 0.0),
                "amount": float(amount or 0.0),
            }
            for symbol, name, sector_name, close_price, pct_chg, amount in rows
            if str(sector_name or "").strip()
        ]


def _detail(source: str, method: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"source": source, "method": method, "detail": detail, "filled_at": beijing_now_string(), **extra}


def _append_quality_note(text: str, note: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return note
    return clean if note in clean else f"{clean}；{note}"


def _downgrade_quality(value: str) -> str:
    return "partial" if str(value or "").lower() in {"fresh", "stale", "partial"} else "unavailable"


def _json_dict(raw: str) -> dict[str, Any]:
    import json

    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
