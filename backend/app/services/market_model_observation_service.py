from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import MarketModelObservation
from app.repositories.low_buy import DailyHistoryRepository


class MarketModelObservationService:
    """Shadow tracking for advisory market models.

    This does not assert profitability. It records emitted opportunities and
    warnings so validation reports can distinguish "no data yet" from "model
    failed acceptance".
    """

    def record(
        self,
        db: Session,
        *,
        model_key: str,
        symbol: str = "",
        name: str = "",
        signal_state: str = "",
        confidence: float = 0.0,
        expected_edge_pct: float = 0.0,
        score: float = 0.0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        trade_date = beijing_now().date().isoformat()
        row = db.execute(
            select(MarketModelObservation).where(
                MarketModelObservation.model_key == model_key,
                MarketModelObservation.symbol == symbol,
                MarketModelObservation.trade_date == trade_date,
                MarketModelObservation.signal_state == signal_state,
            )
        ).scalar_one_or_none()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        if row is None:
            row = MarketModelObservation(
                model_key=model_key,
                symbol=symbol,
                name=name,
                trade_date=trade_date,
                signal_state=signal_state,
                confidence=float(confidence or 0.0),
                expected_edge_pct=float(expected_edge_pct or 0.0),
                score=float(score or 0.0),
                outcome_status="pending",
                payload_json=payload_json,
            )
            db.add(row)
            db.flush()
            return
        row.name = name or row.name
        row.confidence = float(confidence or 0.0)
        row.expected_edge_pct = float(expected_edge_pct or 0.0)
        row.score = float(score or 0.0)
        row.payload_json = payload_json
        if row.outcome_status != "settled":
            row.outcome_status = "pending"

    def summarize(self, db: Session, *, model_key: str, lookback_days: int = 60) -> dict[str, Any]:
        self.settle_pending(db, model_key=model_key)
        cutoff_date = (beijing_now().date().toordinal() - max(1, lookback_days))
        cutoff_iso = _date_from_ordinal(cutoff_date)
        rows = db.execute(
            select(MarketModelObservation).where(
                MarketModelObservation.model_key == model_key,
                MarketModelObservation.trade_date >= cutoff_iso,
            )
        ).scalars().all()
        filtered = [
            row for row in rows
            if _date_ordinal(row.trade_date) >= cutoff_date
        ]
        actionable = [
            row for row in filtered
            if row.signal_state in {"positive_t", "watch", "medium", "high", "ETF 正T候选"}
            or row.confidence > 0
            or row.score > 0
        ]
        edge_pass = [row for row in actionable if float(row.expected_edge_pct or 0.0) > 0]
        settled = [row for row in filtered if row.outcome_status == "settled"]
        successful = [row for row in settled if _payload_outcome(row).get("success") is True]
        return {
            "sample_count": len(filtered),
            "actionable_count": len(actionable),
            "edge_pass_count": len(edge_pass),
            "avg_confidence": _avg(row.confidence for row in actionable),
            "avg_edge_pct": _avg(row.expected_edge_pct for row in actionable),
            "pending_count": sum(1 for row in filtered if row.outcome_status == "pending"),
            "settled_count": len(settled),
            "success_count": len(successful),
            "success_rate_pct": round(len(successful) / len(settled) * 100, 3) if settled else 0.0,
            "avg_return_1d_pct": _avg(_payload_outcome(row).get("return_1d_pct") for row in settled),
            "avg_return_3d_pct": _avg(_payload_outcome(row).get("return_3d_pct") for row in settled),
            "avg_max_adverse_5d_pct": _avg(_payload_outcome(row).get("max_adverse_5d_pct") for row in settled),
        }

    def settle_pending(self, db: Session, *, model_key: str, max_rows: int = 500) -> int:
        rows = (
            db.execute(
                select(MarketModelObservation)
                .where(
                    MarketModelObservation.model_key == model_key,
                    MarketModelObservation.outcome_status == "pending",
                    MarketModelObservation.symbol != "",
                )
                .order_by(MarketModelObservation.observed_at.asc())
                .limit(max(1, min(max_rows, 5000)))
            )
            .scalars()
            .all()
        )
        if not rows:
            return 0
        trade_dates = [row.trade_date for row in rows if row.trade_date]
        if not trade_dates:
            return 0
        repo = DailyHistoryRepository(db)
        latest_dates = repo.fetch_recent_trade_dates(1)
        if not latest_dates:
            return 0
        histories = repo.fetch_rows_for_symbols(
            sorted({row.symbol for row in rows}),
            min(trade_dates),
            latest_dates[-1],
        )
        settled = 0
        for row in rows:
            bars = histories.get(row.symbol, [])
            outcome = _settle_row_outcome(row, bars)
            if not outcome:
                continue
            payload = _json_dict(row.payload_json)
            payload["outcome"] = outcome
            row.payload_json = json.dumps(payload, ensure_ascii=False)
            row.outcome_status = "settled"
            settled += 1
        if settled:
            db.flush()
        return settled

    def count_total(self, db: Session, *, model_key: str) -> int:
        return int(
            db.execute(
                select(func.count(MarketModelObservation.id)).where(MarketModelObservation.model_key == model_key)
            ).scalar_one()
            or 0
        )


def _avg(values) -> float:
    items = [float(value or 0.0) for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def _date_ordinal(value: str) -> int:
    try:
        from datetime import date

        return date.fromisoformat(str(value)[:10]).toordinal()
    except Exception:
        return 0


def _date_from_ordinal(value: int) -> str:
    from datetime import date

    return date.fromordinal(value).isoformat()


def _settle_row_outcome(row: MarketModelObservation, bars) -> dict[str, Any]:
    index = next((idx for idx, item in enumerate(bars) if str(item.trade_date) == str(row.trade_date)), None)
    if index is None or index + 1 >= len(bars):
        return {}
    entry_bar = bars[index]
    entry_price = _entry_price_from_payload(row, float(entry_bar.close_price or 0.0))
    if entry_price <= 0:
        return {}
    future = bars[index + 1 : min(index + 6, len(bars))]
    if not future:
        return {}
    returns: dict[str, float] = {}
    for horizon in (1, 2, 3, 5):
        target = future[min(horizon - 1, len(future) - 1)]
        close_price = float(target.close_price or 0.0)
        returns[f"return_{horizon}d_pct"] = round((close_price - entry_price) / entry_price * 100, 4) if close_price > 0 else 0.0
    highs = [float(item.high_price or 0.0) for item in future if float(item.high_price or 0.0) > 0]
    lows = [float(item.low_price or 0.0) for item in future if float(item.low_price or 0.0) > 0]
    max_favorable = round((max(highs) - entry_price) / entry_price * 100, 4) if highs else 0.0
    max_adverse = round((min(lows) - entry_price) / entry_price * 100, 4) if lows else 0.0
    success = _outcome_success(row, returns, max_favorable, max_adverse)
    return {
        **returns,
        "max_favorable_5d_pct": max_favorable,
        "max_adverse_5d_pct": max_adverse,
        "success": success,
        "settled_at": beijing_now().isoformat(),
    }


def _outcome_success(row: MarketModelObservation, returns: dict[str, float], max_favorable: float, max_adverse: float) -> bool:
    if row.model_key == "intraday_anomaly":
        if row.signal_state in {"high", "medium"}:
            return max_adverse <= -1.0 or returns.get("return_1d_pct", 0.0) <= -0.5
        return max_adverse > -1.5
    return max_favorable >= 0.8 or returns.get("return_1d_pct", 0.0) > 0


def _entry_price_from_payload(row: MarketModelObservation, fallback: float) -> float:
    payload = _json_dict(row.payload_json)
    for key in ("last_price", "latest_price", "current_price", "source_signal_price"):
        try:
            value = float(payload.get(key) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value
    return fallback


def _payload_outcome(row: MarketModelObservation) -> dict[str, Any]:
    outcome = _json_dict(row.payload_json).get("outcome")
    return outcome if isinstance(outcome, dict) else {}


def _json_dict(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}
