from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, DecisionContextSnapshot, SignalOutcomeAttribution


@dataclass(frozen=True)
class SignalAttributionInput:
    symbol: str
    entry_date: date
    entry_price: float
    horizon_days: int
    future_bars: list[Any]


@dataclass(frozen=True)
class SignalOutcome:
    symbol: str
    entry_date: date
    horizon_days: int
    return_pct: float | None
    max_gain_pct: float | None
    max_drawdown_pct: float | None
    hit: bool
    data_quality: str
    reasons: list[str]
    exit_reason: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date.isoformat(),
            "horizon_days": self.horizon_days,
            "return_pct": self.return_pct,
            "max_gain_pct": self.max_gain_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "hit": self.hit,
            "data_quality": self.data_quality,
            "reasons": list(self.reasons),
            "exit_reason": self.exit_reason,
        }


def compute_signal_outcome(value: SignalAttributionInput) -> SignalOutcome:
    entry_price = float(value.entry_price or 0.0)
    horizon = max(1, int(value.horizon_days or 1))
    bars = sorted(
        [bar for bar in value.future_bars if _bar_date(bar) and _bar_date(bar) > value.entry_date],
        key=lambda bar: _bar_date(bar) or date.min,
    )[:horizon]
    if entry_price <= 0:
        return SignalOutcome(
            symbol=value.symbol,
            entry_date=value.entry_date,
            horizon_days=horizon,
            return_pct=None,
            max_gain_pct=None,
            max_drawdown_pct=None,
            hit=False,
            data_quality="no_data",
            reasons=["入场价缺失，无法计算信号归因。"],
            exit_reason="entry_price_missing",
        )
    if len(bars) < horizon:
        return SignalOutcome(
            symbol=value.symbol,
            entry_date=value.entry_date,
            horizon_days=horizon,
            return_pct=None,
            max_gain_pct=None,
            max_drawdown_pct=None,
            hit=False,
            data_quality="no_data",
            reasons=[f"缺少 {horizon} 日未来行情，不能计算信号归因。"],
            exit_reason="future_bars_missing",
        )
    exit_close = _price(bars[-1], "close_price", "close")
    highs = [_price(bar, "high_price", "high") for bar in bars]
    lows = [_price(bar, "low_price", "low") for bar in bars]
    if exit_close <= 0 or not highs or not lows or max(highs) <= 0 or min(lows) <= 0:
        return SignalOutcome(
            symbol=value.symbol,
            entry_date=value.entry_date,
            horizon_days=horizon,
            return_pct=None,
            max_gain_pct=None,
            max_drawdown_pct=None,
            hit=False,
            data_quality="no_data",
            reasons=["未来行情价格字段缺失，不能计算信号归因。"],
            exit_reason="future_price_missing",
        )
    return_pct = round((exit_close / entry_price - 1.0) * 100.0, 4)
    max_gain_pct = round((max(highs) / entry_price - 1.0) * 100.0, 4)
    max_drawdown_pct = round((min(lows) / entry_price - 1.0) * 100.0, 4)
    return SignalOutcome(
        symbol=value.symbol,
        entry_date=value.entry_date,
        horizon_days=horizon,
        return_pct=return_pct,
        max_gain_pct=max_gain_pct,
        max_drawdown_pct=max_drawdown_pct,
        hit=return_pct > 0,
        data_quality="ok",
        reasons=["按信号日之后的未来行情计算归因，不回写策略分数。"],
        exit_reason=f"horizon_{horizon}d_close",
    )


def refresh_signal_attributions(
    db: Session,
    *,
    as_of_date: date,
    horizons: list[int] | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    safe_horizons = [max(1, int(item)) for item in (horizons or [1, 3, 5, 10])][:8]
    rows = (
        db.execute(
            select(DecisionContextSnapshot)
            .where(DecisionContextSnapshot.trade_date <= as_of_date)
            .order_by(DecisionContextSnapshot.trade_date.desc(), DecisionContextSnapshot.id.desc())
            .limit(max(1, min(int(limit or 200), 1000)))
        )
        .scalars()
        .all()
    )
    written = 0
    no_data = 0
    items: list[dict[str, Any]] = []
    for row in rows:
        entry_price = _entry_price(row)
        max_horizon = max(safe_horizons)
        future_bars = (
            db.execute(
                select(DailyBarSnapshot)
                .where(DailyBarSnapshot.symbol == row.symbol)
                .where(DailyBarSnapshot.trade_date > row.trade_date)
                .order_by(DailyBarSnapshot.trade_date.asc())
                .limit(max_horizon)
            )
            .scalars()
            .all()
        )
        for horizon in safe_horizons:
            outcome = compute_signal_outcome(
                SignalAttributionInput(
                    symbol=row.symbol,
                    entry_date=row.trade_date,
                    entry_price=entry_price,
                    horizon_days=horizon,
                    future_bars=list(future_bars),
                )
            )
            if outcome.data_quality == "ok":
                _upsert_attribution(db, row, outcome)
                written += 1
            else:
                no_data += 1
            items.append(
                {
                    "context_snapshot_id": int(row.id),
                    "strategy_key": row.strategy_key,
                    **outcome.as_payload(),
                }
            )
    db.commit()
    return {
        "ok": True,
        "worker_scope": "runtime-worker",
        "status": "ok" if written else "no_data",
        "as_of_date": as_of_date.isoformat(),
        "context_count": len(rows),
        "horizons": safe_horizons,
        "written_count": written,
        "no_data_count": no_data,
        "items": items[:50],
    }


def decision_context_attribution_payload(
    db: Session,
    *,
    symbol: str,
    strategy_key: str,
    trade_date: date | None = None,
) -> dict[str, Any]:
    statement = (
        select(DecisionContextSnapshot)
        .where(DecisionContextSnapshot.symbol == symbol)
        .where(DecisionContextSnapshot.strategy_key == strategy_key)
    )
    if trade_date is not None:
        statement = statement.where(DecisionContextSnapshot.trade_date == trade_date)
    context = db.execute(
        statement.order_by(DecisionContextSnapshot.trade_date.desc(), DecisionContextSnapshot.id.desc()).limit(1)
    ).scalar_one_or_none()
    if context is None:
        return {
            "status": "no_data",
            "data_quality": "missing",
            "reasons": ["未找到决策上下文快照，不能展示生产归因。"],
            "outcomes": [],
            "gates": {},
            "similar_history_sample_count": 0,
        }
    outcomes = (
        db.execute(
            select(SignalOutcomeAttribution)
            .where(SignalOutcomeAttribution.context_snapshot_id == context.id)
            .order_by(SignalOutcomeAttribution.horizon_days.asc())
        )
        .scalars()
        .all()
    )
    gates = _json_dict(context.gates_json)
    return {
        "status": "ok" if outcomes else "no_data",
        "context_snapshot_id": int(context.id),
        "symbol": context.symbol,
        "strategy_key": context.strategy_key,
        "trade_date": context.trade_date.isoformat(),
        "strategy_tier": context.strategy_tier,
        "production_eligible": bool(context.production_eligible),
        "production_score": _json_dict(context.source_snapshot_json).get("production_score"),
        "final_decision": context.final_decision,
        "final_score": float(context.final_score or 0.0),
        "data_quality": context.data_quality,
        "gates": gates,
        "gate_contributions": _gate_contributions(gates),
        "source_versions": _source_versions(context),
        "entry": _entry_payload(context),
        "outcomes": [_outcome_payload(item) for item in outcomes],
        "similar_history_sample_count": _similar_history_sample_count(db, context),
        "reasons": [] if outcomes else ["信号归因尚未生成，可由 runtime-worker 执行 signal_attribution_refresh。"],
    }


def _upsert_attribution(db: Session, context: DecisionContextSnapshot, outcome: SignalOutcome) -> None:
    row = db.execute(
        select(SignalOutcomeAttribution)
        .where(SignalOutcomeAttribution.context_snapshot_id == context.id)
        .where(SignalOutcomeAttribution.horizon_days == outcome.horizon_days)
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        row = SignalOutcomeAttribution(
            context_snapshot_id=int(context.id),
            horizon_days=outcome.horizon_days,
        )
        db.add(row)
    row.return_pct = float(outcome.return_pct or 0.0)
    row.max_gain_pct = float(outcome.max_gain_pct or 0.0)
    row.max_drawdown_pct = float(outcome.max_drawdown_pct or 0.0)
    row.hit = bool(outcome.hit)
    row.exit_reason = outcome.exit_reason


def _outcome_payload(row: SignalOutcomeAttribution) -> dict[str, Any]:
    return {
        "horizon_days": int(row.horizon_days),
        "return_pct": float(row.return_pct or 0.0),
        "max_gain_pct": float(row.max_gain_pct or 0.0),
        "max_drawdown_pct": float(row.max_drawdown_pct or 0.0),
        "hit": bool(row.hit),
        "exit_reason": row.exit_reason,
    }


def _gate_contributions(gates: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key, raw in gates.items():
        if not isinstance(raw, dict):
            continue
        decision = str(raw.get("decision") or "no_data")
        score = _float_or_none(raw.get("score"))
        result.append(
            {
                "gate": key,
                "decision": decision,
                "score": score,
                "effect": _gate_effect(decision),
                "reasons": [str(item) for item in raw.get("reasons") or []],
            }
        )
    return result


def _gate_effect(decision: str) -> str:
    if decision == "allow":
        return "positive"
    if decision in {"reduce", "wait"}:
        return "negative"
    if decision in {"block", "research_only", "no_data"}:
        return "blocked"
    return "neutral"


def _source_versions(context: DecisionContextSnapshot) -> dict[str, Any]:
    source = _json_dict(context.source_snapshot_json)
    return {
        key: source.get(key)
        for key in (
            "source",
            "data_version",
            "production_scoring_config_version",
            "market_data_source",
            "market_data_updated_at",
        )
        if source.get(key) not in (None, "")
    }


def _entry_payload(context: DecisionContextSnapshot) -> dict[str, Any]:
    source = _json_dict(context.source_snapshot_json)
    return {
        "entry_price": _entry_price(context) or None,
        "entry_zone_low": _float_or_none(source.get("entry_zone_low") or source.get("entry_low")),
        "entry_zone_high": _float_or_none(source.get("entry_zone_high") or source.get("entry_high")),
        "stop_loss": _float_or_none(source.get("stop_loss")),
        "invalidation": source.get("invalidation") or source.get("exit_reason") or "",
    }


def _similar_history_sample_count(db: Session, context: DecisionContextSnapshot) -> int:
    return int(
        db.execute(
            select(func.count(DecisionContextSnapshot.id))
            .where(DecisionContextSnapshot.strategy_key == context.strategy_key)
            .where(DecisionContextSnapshot.id != context.id)
        ).scalar()
        or 0
    )


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _entry_price(row: DecisionContextSnapshot) -> float:
    payload = _json_dict(row.source_snapshot_json)
    for key in ("entry_price", "latest_price", "close_price", "price"):
        value = payload.get(key)
        try:
            if float(value or 0.0) > 0:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _bar_date(bar: Any) -> date | None:
    value = getattr(bar, "trade_date", None)
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _price(bar: Any, *fields: str) -> float:
    for field in fields:
        value = getattr(bar, field, None)
        try:
            if float(value or 0.0) > 0:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
