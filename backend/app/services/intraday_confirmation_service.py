from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import IntradayConfirmationSnapshot
from app.models.schema_defs.research import IntradayConfirmationOut
from app.services.low_buy.intraday_confirmation import build_intraday_confirmation
from app.services.market_data import MarketDataService


class IntradayConfirmationService:
    """Build and persist compact intraday confirmation snapshots."""

    def __init__(self, db: Session, market_data: MarketDataService | None = None) -> None:
        self.db = db
        self.market_data = market_data or MarketDataService()

    def confirm_symbols(
        self,
        symbols: list[str],
        *,
        period: str = "1m",
        limit: int = 120,
    ) -> list[IntradayConfirmationOut]:
        results: list[IntradayConfirmationOut] = []
        for symbol in _clean_symbols(symbols):
            try:
                results.append(self._confirm_one(symbol=symbol, period=period, limit=limit))
            except Exception as exc:
                results.append(_error_confirmation(symbol=symbol, reason=str(exc)))
        self.db.commit()
        return results

    def list_recent(self, limit: int = 50) -> list[IntradayConfirmationOut]:
        rows = (
            self.db.execute(
                select(IntradayConfirmationSnapshot)
                .order_by(IntradayConfirmationSnapshot.updated_at.desc())
                .limit(max(1, min(limit, 200)))
            )
            .scalars()
            .all()
        )
        return [_row_to_out(row) for row in rows]

    def _confirm_one(self, *, symbol: str, period: str, limit: int) -> IntradayConfirmationOut:
        bars = self.market_data.get_intraday_bars(symbol, period=period, limit=limit)
        confirmation = build_intraday_confirmation(bars)
        tick = self.market_data.get_tick_snapshot(symbol)
        profile = self.market_data.get_volume_profile(symbol, period=period, limit=limit)
        big_order = self.market_data.get_big_order_tracker(symbol, period=period, limit=min(limit, 120))
        score = _confirmation_score(confirmation, big_order)
        trade_date = _trade_date_from_tick(tick)
        row = self._upsert_snapshot(
            symbol=symbol,
            name=str(tick.get("name") or ""),
            trade_date=trade_date,
            period=period,
            confirmation=confirmation,
            score=score,
            tick=tick,
            profile=profile,
            big_order=big_order,
        )
        return _row_to_out(row)

    def _upsert_snapshot(
        self,
        *,
        symbol: str,
        name: str,
        trade_date: str,
        period: str,
        confirmation,
        score: float,
        tick: dict,
        profile: dict,
        big_order: dict,
    ) -> IntradayConfirmationSnapshot:
        row = (
            self.db.execute(
                select(IntradayConfirmationSnapshot).where(
                    IntradayConfirmationSnapshot.symbol == symbol,
                    IntradayConfirmationSnapshot.trade_date == trade_date,
                    IntradayConfirmationSnapshot.bar_period == period,
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            row = IntradayConfirmationSnapshot(symbol=symbol, trade_date=trade_date, bar_period=period)
            self.db.add(row)
        row.name = name
        row.vwap = float(confirmation.vwap or 0.0)
        row.latest_price = float(tick.get("last_price") or 0.0)
        row.above_vwap = bool(confirmation.above_vwap)
        row.confirmed = bool(confirmation.confirmed)
        row.late_confirmed = bool(confirmation.late_confirmed)
        row.score = score
        row.reason = confirmation.reason
        row.payload_json = json.dumps(
            {"tick": tick, "profile": profile, "big_order": big_order},
            ensure_ascii=False,
            default=str,
        )
        row.updated_at = datetime.now()
        return row


def _row_to_out(row: IntradayConfirmationSnapshot) -> IntradayConfirmationOut:
    payload = _loads(row.payload_json)
    return IntradayConfirmationOut(
        symbol=row.symbol,
        name=row.name,
        trade_date=row.trade_date,
        vwap=float(row.vwap or 0.0),
        latest_price=float(row.latest_price or 0.0),
        above_vwap=bool(row.above_vwap),
        confirmed=bool(row.confirmed),
        late_confirmed=bool(row.late_confirmed),
        score=float(row.score or 0.0),
        reason=row.reason or "",
        profile=payload.get("profile") or {},
        big_order=payload.get("big_order") or {},
        tick=payload.get("tick") or {},
        updated_at=row.updated_at,
    )


def _error_confirmation(symbol: str, reason: str) -> IntradayConfirmationOut:
    return IntradayConfirmationOut(
        symbol=symbol,
        trade_date=beijing_now().strftime("%Y-%m-%d"),
        reason=f"盘中确认失败：{reason}",
    )


def _confirmation_score(confirmation, big_order: dict) -> float:
    score = 0.0
    if confirmation.above_vwap:
        score += 25
    if confirmation.confirmed:
        score += 35
    if confirmation.late_confirmed:
        score += 25
    if float(big_order.get("net_ratio") or 0.0) > 0:
        score += 15
    return round(min(score, 100.0), 2)


def _trade_date_from_tick(tick: dict) -> str:
    timestamp = str(tick.get("timestamp") or "")
    if len(timestamp) >= 10:
        return timestamp[:10]
    return beijing_now().strftime("%Y-%m-%d")


def _loads(raw: str | None) -> dict:
    try:
        payload = json.loads(raw or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _clean_symbols(symbols: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol).strip()
        if not value or value in seen:
            continue
        cleaned.append(value)
        seen.add(value)
    return cleaned[:50]
