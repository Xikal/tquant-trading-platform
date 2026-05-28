from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import MarketModelObservation
from app.repositories.low_buy import DailyHistoryRepository
from app.services.low_buy.main_force_model_schema import MAIN_FORCE_MODEL_OBSERVATION_KEY
from app.services.market_model_observation_service import MarketModelObservationService


def record_main_force_shadow(
    db: Session,
    *,
    candidate: Any,
    advice: dict[str, Any],
    rank_bonus: float = 0.0,
) -> None:
    payload = _shadow_payload(candidate=candidate, advice=advice, rank_bonus=rank_bonus)
    trade_date = str(
        payload.get("as_of")
        or getattr(candidate, "confirmed_trade_date", "")
        or getattr(candidate, "quote_timestamp", "")
    )[:10]
    if trade_date:
        _upsert_for_trade_date(
            db,
            candidate=candidate,
            advice=advice,
            payload=payload,
            rank_bonus=rank_bonus,
            trade_date=trade_date,
        )
        return
    MarketModelObservationService().record(
        db,
        model_key=MAIN_FORCE_MODEL_OBSERVATION_KEY,
        symbol=str(getattr(candidate, "symbol", "") or advice.get("symbol") or ""),
        name=str(getattr(candidate, "name", "") or advice.get("name") or ""),
        signal_state=str(advice.get("action") or "observe"),
        confidence=_float(advice.get("confidence")),
        expected_edge_pct=float(rank_bonus or 0.0),
        score=_float(advice.get("score")),
        payload=payload,
    )


def _upsert_for_trade_date(
    db: Session,
    *,
    candidate: Any,
    advice: dict[str, Any],
    payload: dict[str, Any],
    rank_bonus: float,
    trade_date: str,
) -> None:
    signal_state = str(advice.get("action") or "observe")
    row = db.execute(
        select(MarketModelObservation).where(
            MarketModelObservation.model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY,
            MarketModelObservation.symbol == str(getattr(candidate, "symbol", "") or ""),
            MarketModelObservation.trade_date == trade_date,
            MarketModelObservation.signal_state == signal_state,
        )
    ).scalar_one_or_none()
    payload_json = json.dumps(payload, ensure_ascii=False)
    if row is None:
        db.add(
            MarketModelObservation(
                model_key=MAIN_FORCE_MODEL_OBSERVATION_KEY,
                symbol=str(getattr(candidate, "symbol", "") or ""),
                name=str(getattr(candidate, "name", "") or ""),
                trade_date=trade_date,
                signal_state=signal_state,
                confidence=_float(advice.get("confidence")),
                expected_edge_pct=float(rank_bonus or 0.0),
                score=_float(advice.get("score")),
                outcome_status="pending",
                payload_json=payload_json,
            )
        )
        db.flush()
        return
    row.name = str(getattr(candidate, "name", "") or row.name)
    row.confidence = _float(advice.get("confidence"))
    row.expected_edge_pct = float(rank_bonus or 0.0)
    row.score = _float(advice.get("score"))
    row.payload_json = payload_json
    if row.outcome_status != "settled":
        row.outcome_status = "pending"
    db.flush()


def summarize_main_force_shadow(db: Session, *, lookback_days: int = 365) -> dict[str, Any]:
    settle_main_force_shadow(db)
    cutoff = (date.today() - timedelta(days=max(1, lookback_days))).isoformat()
    rows = (
        db.execute(
            select(MarketModelObservation).where(
                MarketModelObservation.model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY,
                MarketModelObservation.trade_date >= cutoff,
            )
        )
        .scalars()
        .all()
    )
    settled = [row for row in rows if row.outcome_status == "settled"]
    outcomes = [_payload(row).get("outcome", {}) for row in settled]
    successes = [item for item in outcomes if isinstance(item, dict) and item.get("success") is True]
    fallbacks = [row for row in rows if _payload(row).get("fallback_reason")]
    gains = [_float(item.get("return_20d_pct")) for item in outcomes if isinstance(item, dict)]
    profit_factor = _profit_factor(gains)
    success_rate = round(len(successes) / len(settled) * 100.0, 3) if settled else 0.0
    settings = get_settings()
    blockers = _promotion_blockers(
        record_count=len(rows),
        settled_count=len(settled),
        success_rate_pct=success_rate,
        profit_factor=profit_factor,
        fallback_count=len(fallbacks),
        settings=settings,
    )
    return {
        "model_key": MAIN_FORCE_MODEL_OBSERVATION_KEY,
        "status": "shadow_ready" if not blockers else "insufficient_shadow_samples",
        "record_count": len(rows),
        "settled_count": len(settled),
        "success_rate_pct": success_rate,
        "profit_factor": profit_factor,
        "avg_return_20d_pct": _avg(gains),
        "max_adverse_20d_pct": _avg(_float(item.get("max_adverse_20d_pct")) for item in outcomes if isinstance(item, dict)),
        "fallback_count": len(fallbacks),
        "promotion_ready": not blockers,
        "promotion_blockers": blockers,
        "production_effect": "readonly_shadow",
        "shadow_only": True,
    }


def settle_main_force_shadow(db: Session, *, max_rows: int = 500) -> int:
    rows = (
        db.execute(
            select(MarketModelObservation)
            .where(
                MarketModelObservation.model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY,
                MarketModelObservation.outcome_status == "pending",
                MarketModelObservation.symbol != "",
            )
            .order_by(MarketModelObservation.trade_date.asc(), MarketModelObservation.id.asc())
            .limit(max(1, min(max_rows, 5000)))
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    latest_trade_date = _latest_trade_date(db)
    if not latest_trade_date:
        return 0
    histories = DailyHistoryRepository(db).fetch_rows_for_symbols(
        sorted({row.symbol for row in rows}),
        min(row.trade_date for row in rows if row.trade_date),
        latest_trade_date,
    )
    settled = 0
    for row in rows:
        outcome = _settle_row(row, histories.get(row.symbol, []))
        if not outcome:
            continue
        payload = _payload(row)
        payload["outcome"] = outcome
        row.payload_json = json.dumps(payload, ensure_ascii=False)
        row.outcome_status = "settled"
        settled += 1
    if settled:
        db.flush()
    return settled


def _shadow_payload(*, candidate: Any, advice: dict[str, Any], rank_bonus: float) -> dict[str, Any]:
    feature_snapshot = advice.get("feature_snapshot") if isinstance(advice.get("feature_snapshot"), dict) else {}
    return {
        "as_of": getattr(candidate, "quote_timestamp", "") or feature_snapshot.get("as_of_date", ""),
        "strategy_key": getattr(candidate, "strategy_key", ""),
        "rule_score_before": _float(getattr(candidate, "score", 0.0)),
        "rule_signal_state": getattr(candidate, "buy_signal_state", ""),
        "model_advice": advice,
        "feature_snapshot": feature_snapshot,
        "fallback_reason": advice.get("fallback_reason"),
        "production_effect": advice.get("production_effect", "readonly_shadow"),
        "rank_bonus": float(rank_bonus or 0.0),
        "latest_price": _float(getattr(candidate, "latest_price", 0.0)),
        "entry_zone_low": _float(getattr(candidate, "entry_zone_low", 0.0)),
        "entry_zone_high": _float(getattr(candidate, "entry_zone_high", 0.0)),
        "stop_loss": _float(getattr(candidate, "stop_loss", 0.0)),
        "take_profit": _float(getattr(candidate, "take_profit", 0.0)),
        "outcome": {},
    }


def _settle_row(row: MarketModelObservation, bars: list[Any]) -> dict[str, Any]:
    index = next((idx for idx, item in enumerate(bars) if str(item.trade_date) == str(row.trade_date)), None)
    if index is None or index + 1 >= len(bars):
        return {}
    entry_price = _entry_price(row, bars[index])
    if entry_price <= 0:
        return {}
    future = bars[index + 1 : min(index + 41, len(bars))]
    if not future:
        return {}
    outcome: dict[str, Any] = {}
    for horizon in (1, 3, 5, 10, 20, 40):
        target = future[min(horizon - 1, len(future) - 1)]
        outcome[f"return_{horizon}d_pct"] = _return_pct(_float(target.close_price), entry_price)
    highs = [_float(item.high_price) for item in future[:20] if _float(item.high_price) > 0]
    lows = [_float(item.low_price) for item in future[:20] if _float(item.low_price) > 0]
    stop_loss = _payload(row).get("model_advice", {}).get("stop_loss") or _payload(row).get("stop_loss")
    stop = _float(stop_loss)
    take_profit = _first_take_profit(_payload(row).get("model_advice", {}))
    outcome["max_favorable_20d_pct"] = _return_pct(max(highs), entry_price) if highs else 0.0
    outcome["max_adverse_20d_pct"] = _return_pct(min(lows), entry_price) if lows else 0.0
    outcome["hit_stop_loss_20d"] = bool(stop > 0 and lows and min(lows) <= stop)
    outcome["first_profit_before_stop"] = _first_profit_before_stop(future[:20], stop=stop, take_profit=take_profit)
    outcome["success"] = bool(outcome["return_20d_pct"] > 0 or outcome["first_profit_before_stop"])
    return outcome


def _entry_price(row: MarketModelObservation, bar: Any) -> float:
    payload = _payload(row)
    for key in ("latest_price", "source_signal_price", "entry_zone_low"):
        value = _float(payload.get(key))
        if value > 0:
            return value
    return _float(getattr(bar, "close_price", 0.0))


def _first_take_profit(advice: dict[str, Any]) -> float:
    plan = advice.get("take_profit_plan")
    if isinstance(plan, list) and plan:
        return _float(plan[0].get("price") if isinstance(plan[0], dict) else 0.0)
    return 0.0


def _first_profit_before_stop(future: list[Any], *, stop: float, take_profit: float) -> bool:
    if take_profit <= 0:
        return False
    for item in future:
        if stop > 0 and _float(item.low_price) <= stop:
            return False
        if _float(item.high_price) >= take_profit:
            return True
    return False


def _latest_trade_date(db: Session) -> str:
    value = db.execute(select(func.max(MarketModelObservation.trade_date))).scalar()
    repo_dates = DailyHistoryRepository(db).fetch_recent_trade_dates(1)
    return repo_dates[-1] if repo_dates else str(value or "")


def _promotion_blockers(*, record_count: int, settled_count: int, success_rate_pct: float, profit_factor: float, fallback_count: int, settings: Any) -> list[str]:
    blockers: list[str] = []
    if record_count < int(settings.main_force_model_shadow_sample_min):
        blockers.append(f"shadow_record_count_lt_{settings.main_force_model_shadow_sample_min}")
    if settled_count < int(settings.main_force_model_shadow_settled_min):
        blockers.append(f"settled_shadow_count_lt_{settings.main_force_model_shadow_settled_min}")
    if success_rate_pct < float(settings.main_force_model_min_success_rate_pct):
        blockers.append("success_rate_below_threshold")
    if profit_factor < float(settings.main_force_model_min_profit_factor):
        blockers.append("profit_factor_below_threshold")
    if record_count and fallback_count / record_count > 0.15:
        blockers.append("fallback_rate_gt_15pct")
    return blockers


def _payload(row: MarketModelObservation) -> dict[str, Any]:
    try:
        value = json.loads(row.payload_json or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _profit_factor(values: list[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return round(gains / losses, 4) if losses else (round(gains, 4) if gains else 0.0)


def _avg(values) -> float:
    items = [float(value or 0.0) for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def _return_pct(price: float, entry: float) -> float:
    return round((price - entry) / entry * 100.0, 4) if entry > 0 and price > 0 else 0.0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
