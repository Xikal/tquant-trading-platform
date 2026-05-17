from __future__ import annotations

from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyTradeLifecycleOut,
    LowBuyTradeLifecycleUpdate,
)
from app.repositories.low_buy import LowBuyTradeLifecycleRepository
from app.services.low_buy.shared import PLAYBOOKS, Session, datetime


class LowBuyLifecycleMixin:
    def sync_trade_lifecycle(
        self,
        db: Session,
        *,
        strategy: str | None = None,
        limit: int = 100,
    ) -> list[LowBuyTradeLifecycleOut]:
        candidates = self._load_lifecycle_candidates(db=db, strategy=strategy, limit=limit)
        repository = LowBuyTradeLifecycleRepository(db)
        rows = [
            repository.upsert_planned(_candidate_to_lifecycle_values(candidate))
            for candidate in candidates
        ]
        db.commit()
        return [_row_to_lifecycle_out(row) for row in rows]

    def list_trade_lifecycle(
        self,
        db: Session,
        *,
        strategy: str | None = None,
        limit: int = 100,
    ) -> list[LowBuyTradeLifecycleOut]:
        rows = LowBuyTradeLifecycleRepository(db).fetch_recent(
            strategy_key=strategy,
            limit=limit,
        )
        return [_row_to_lifecycle_out(row) for row in rows]

    def update_trade_lifecycle(
        self,
        db: Session,
        *,
        symbol: str,
        payload: LowBuyTradeLifecycleUpdate,
    ) -> LowBuyTradeLifecycleOut | None:
        values = payload.model_dump(exclude_none=True)
        resolved_status = _resolve_lifecycle_status(values)
        if resolved_status:
            values["status"] = resolved_status
        realized_return = _resolve_realized_return(values)
        if realized_return is not None:
            values["realized_return_pct"] = realized_return
        row = LowBuyTradeLifecycleRepository(db).update_execution(
            signal_trade_date=payload.signal_trade_date,
            strategy_key=payload.strategy_key,
            symbol=symbol,
            values=values,
        )
        if row is None:
            return None
        db.commit()
        return _row_to_lifecycle_out(row)

    def _load_lifecycle_candidates(
        self,
        db: Session,
        *,
        strategy: str | None,
        limit: int,
    ) -> list[LowBuyCandidateOut]:
        strategies = [strategy] if strategy else list(PLAYBOOKS)
        candidates: list[LowBuyCandidateOut] = []
        for strategy_key in strategies:
            payload = self._load_latest_materialized_full_result(
                db=db,
                strategy=strategy_key,
                limit=max(24, limit),
                include_history=False,
                allow_repair=False,
            )
            if payload is None:
                continue
            candidates.extend(
                item
                for item in payload.confirmed_candidates + payload.candidates
                if item.buy_signal_state in {"buy_now", "soft_buy_now", "observe_confirmed", "near_entry"}
            )
        candidates.sort(key=lambda item: (item.confirmed_trade_date or item.quote_timestamp, item.score), reverse=True)
        return candidates[:limit]


def _candidate_to_lifecycle_values(candidate: LowBuyCandidateOut) -> dict:
    signal_trade_date = candidate.confirmed_trade_date or candidate.quote_timestamp
    return {
        "signal_trade_date": signal_trade_date,
        "strategy_key": candidate.strategy_key,
        "symbol": candidate.symbol,
        "name": candidate.name,
        "signal_state": candidate.buy_signal_state,
        "status": "planned",
        "entry_plan_low": candidate.entry_zone_low,
        "entry_plan_high": candidate.entry_zone_high,
        "stop_loss": candidate.exit_plan.stop_loss or candidate.stop_loss,
        "take_profit": candidate.exit_plan.first_take_profit or candidate.take_profit,
        "max_holding_days": candidate.exit_plan.max_holding_days,
        "payload_json": candidate.model_dump_json(),
    }


def _row_to_lifecycle_out(row) -> LowBuyTradeLifecycleOut:
    return LowBuyTradeLifecycleOut(
        symbol=row.symbol,
        name=row.name,
        strategy_key=row.strategy_key,
        signal_trade_date=row.signal_trade_date,
        status=row.status,
        signal_state=row.signal_state,
        entry_plan_low=row.entry_plan_low,
        entry_plan_high=row.entry_plan_high,
        stop_loss=row.stop_loss,
        take_profit=row.take_profit,
        max_holding_days=row.max_holding_days,
        entry_price=row.entry_price,
        entry_trade_date=row.entry_trade_date,
        exit_price=row.exit_price,
        exit_trade_date=row.exit_trade_date,
        exit_reason=row.exit_reason,
        realized_return_pct=row.realized_return_pct,
        max_gain_pct=row.max_gain_pct,
        max_drawdown_pct=row.max_drawdown_pct,
        attribution_note=row.attribution_note,
        updated_at=row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _resolve_lifecycle_status(values: dict) -> str | None:
    explicit = values.get("status")
    if explicit:
        return explicit
    if values.get("exit_price") is not None or values.get("exit_trade_date"):
        return "exited"
    if values.get("entry_price") is not None or values.get("entry_trade_date"):
        return "holding"
    return None


def _resolve_realized_return(values: dict) -> float | None:
    if values.get("realized_return_pct") is not None:
        return values["realized_return_pct"]
    entry_price = values.get("entry_price")
    exit_price = values.get("exit_price")
    if not entry_price or not exit_price:
        return None
    return round((exit_price - entry_price) / max(entry_price, 0.01) * 100, 3)
