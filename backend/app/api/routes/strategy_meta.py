from __future__ import annotations

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot, User
from app.models.schema_defs.strategy_meta import (
    StrategyGovernanceMutationRequest,
    StrategyGovernanceMutationResponse,
    StrategyMetaResponse,
    StrategyPresetResponse,
    StrategySignalReplayItem,
    StrategySignalReplayResponse,
    SymbolSearchResponse,
)
from app.services.strategy_metadata_service import StrategyMetadataService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/strategies/meta", response_model=StrategyMetaResponse)
def list_strategy_meta(
    include_hidden: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyMetaResponse:
    service = StrategyMetadataService(db)
    return service.list_strategy_meta(
        current_user=current_user,
        include_hidden=include_hidden,
    )


@router.get("/strategy/presets", response_model=StrategyPresetResponse)
def list_strategy_presets(db: Session = Depends(get_db)) -> StrategyPresetResponse:
    return StrategyMetadataService(db).list_presets()


@router.post("/strategy/governance/promote", response_model=StrategyGovernanceMutationResponse)
def promote_strategy(
    payload: StrategyGovernanceMutationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyGovernanceMutationResponse:
    _require_admin(current_user)
    try:
        return StrategyMetadataService(db).promote_strategy(payload, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/strategy/governance/demote", response_model=StrategyGovernanceMutationResponse)
def demote_strategy(
    payload: StrategyGovernanceMutationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyGovernanceMutationResponse:
    _require_admin(current_user)
    try:
        return StrategyMetadataService(db).demote_strategy(payload, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/symbols/search", response_model=SymbolSearchResponse)
def search_symbols(
    q: str = Query(default="", min_length=0, max_length=40),
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
) -> SymbolSearchResponse:
    return StrategyMetadataService(db).search_symbols(q, limit)


@router.get("/strategy/signals/replay", response_model=StrategySignalReplayResponse)
def list_strategy_signal_replay(
    strategy: str = Query(default="first_board", min_length=1, max_length=80),
    symbol: str = Query(default="", max_length=40),
    limit: int = Query(default=20, ge=1, le=80),
    lookback_days: int = Query(default=30, ge=1, le=120),
    db: Session = Depends(get_db),
) -> StrategySignalReplayResponse:
    """Read-only replay view over materialized low-buy results.

    This endpoint intentionally never triggers a scan. It only reads existing
    snapshots so the strategy workbench can inspect signals without creating
    another expensive low-buy request path.
    """

    recent_dates = _recent_result_dates(db, strategy=strategy, lookback_days=lookback_days)
    if not recent_dates:
        return StrategySignalReplayResponse(items=[], total=0)

    statement = select(LowBuyResultSnapshot).where(
        LowBuyResultSnapshot.strategy_key == strategy,
        LowBuyResultSnapshot.latest_trade_date.in_(recent_dates),
    )
    keyword = symbol.strip()
    if keyword:
        like = f"%{_escape_like(keyword)}%"
        statement = statement.where(
            or_(
                LowBuyResultSnapshot.symbol.ilike(like, escape="\\"),
                LowBuyResultSnapshot.name.ilike(like, escape="\\"),
            )
        )
    total = int(db.execute(select(func.count()).select_from(statement.subquery())).scalar() or 0)
    rows = (
        db.execute(
            statement.order_by(
                desc(LowBuyResultSnapshot.latest_trade_date),
                desc(LowBuyResultSnapshot.score),
                desc(LowBuyResultSnapshot.updated_at),
            ).limit(limit)
        )
        .scalars()
        .all()
    )
    return StrategySignalReplayResponse(items=[_signal_replay_item(row) for row in rows], total=total)


def _recent_result_dates(db: Session, *, strategy: str, lookback_days: int) -> list[str]:
    dates = [
        str(value)
        for value in db.execute(
            select(LowBuyScanSnapshot.latest_trade_date)
            .where(LowBuyScanSnapshot.strategy_key == strategy)
            .order_by(desc(LowBuyScanSnapshot.latest_trade_date))
            .limit(lookback_days)
        )
        .scalars()
        .all()
        if value
    ]
    if dates:
        return dates
    return [
        str(value)
        for value in db.execute(
            select(LowBuyResultSnapshot.latest_trade_date)
            .where(LowBuyResultSnapshot.strategy_key == strategy)
            .distinct()
            .order_by(desc(LowBuyResultSnapshot.latest_trade_date))
            .limit(lookback_days)
        )
        .scalars()
        .all()
        if value
    ]


def _signal_replay_item(row: LowBuyResultSnapshot) -> StrategySignalReplayItem:
    payload = _json_dict(row.payload_json)
    reasons = payload.get("reasons") or payload.get("top_reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    if not isinstance(reasons, list):
        reasons = []
    entry_low = payload.get("entry_low")
    entry_high = payload.get("entry_high")
    entry_zone = str(payload.get("entry_zone") or "")
    if not entry_zone and entry_low is not None and entry_high is not None:
        entry_zone = f"{_fmt_price(entry_low)}-{_fmt_price(entry_high)}"
    return StrategySignalReplayItem(
        latest_trade_date=str(row.latest_trade_date or ""),
        strategy_key=str(row.strategy_key or ""),
        symbol=str(row.symbol or ""),
        name=str(row.name or payload.get("name") or ""),
        buy_signal_state=str(row.buy_signal_state or payload.get("buy_signal_state") or ""),
        buy_signal_text=str(payload.get("buy_signal_text") or payload.get("status_text") or row.buy_signal_state or ""),
        score=float(row.score or 0.0),
        latest_price=_float_or_none(payload.get("latest_price") or payload.get("current_price")),
        change_pct=_float_or_none(payload.get("change_pct")),
        entry_zone=entry_zone,
        stop_loss=_float_or_none(payload.get("stop_loss")),
        suggested_position_text=str(payload.get("suggested_position_text") or ""),
        summary=str(payload.get("summary") or payload.get("strategy_notes") or ""),
        reasons=[str(item)[:120] for item in reasons[:4]],
        updated_at=row.updated_at.isoformat(sep=" ", timespec="seconds") if row.updated_at else "",
    )


def _json_dict(raw_value: str) -> dict:
    try:
        value = json.loads(raw_value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _float_or_none(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _fmt_price(value) -> str:
    parsed = _float_or_none(value)
    return "--" if parsed is None else f"{parsed:.3f}"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _require_admin(user: User) -> None:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    if "admin" in roles or "administrator" in roles:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
