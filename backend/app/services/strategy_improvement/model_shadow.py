from __future__ import annotations

from typing import Any

import json

from sqlalchemy import case, func, select

from app.models.entities import MarketModelObservation
from app.services.paper.exit_model_advisor import ACTION_RANK
from app.services.paper.exit_model_schema import EXIT_MODEL_OBSERVATION_KEY


def exit_model_shadow_status(db) -> dict[str, Any]:
    rows = db.execute(
        select(
            func.count(MarketModelObservation.id),
            func.sum(case((MarketModelObservation.outcome_status == "settled", 1), else_=0)),
            func.min(MarketModelObservation.trade_date),
            func.max(MarketModelObservation.trade_date),
            func.avg(MarketModelObservation.confidence),
        ).where(MarketModelObservation.model_key == EXIT_MODEL_OBSERVATION_KEY)
    ).one()
    total = int(rows[0] or 0)
    settled = int(rows[1] or 0)
    records = _latest_records(db)
    diff = _action_diff(records)
    outcomes = _outcome_summary(records)
    return {
        "model_key": EXIT_MODEL_OBSERVATION_KEY,
        "status": "shadow_ready" if total >= 30 and settled >= 30 else "insufficient_shadow_samples",
        "record_count": total,
        "settled_count": settled,
        "first_trade_date": str(rows[2] or ""),
        "last_trade_date": str(rows[3] or ""),
        "avg_confidence": round(float(rows[4] or 0.0), 4),
        "production_effect": "none_shadow_only",
        "hard_stop_override_allowed": False,
        "shadow_only": True,
        "action_diff": diff,
        "outcome_summary": outcomes,
        "promotion_ready": total >= 30 and settled >= 30 and not diff["hard_stop_override_risk_count"],
        "promotion_blockers": _promotion_blockers(total=total, settled=settled, diff=diff),
        "notes": [
            "模型只能用于信号过滤、仓位建议和止盈止损辅助建议的 Shadow 评估。",
            "模型不得直接下单、不得取消或放宽硬止损、不得绕过风控或修改账本。",
        ],
    }


def _latest_records(db) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(MarketModelObservation)
            .where(MarketModelObservation.model_key == EXIT_MODEL_OBSERVATION_KEY)
            .order_by(MarketModelObservation.trade_date.desc(), MarketModelObservation.id.desc())
            .limit(500)
        )
        .scalars()
        .all()
    )
    return [_payload(row) for row in rows]


def _action_diff(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"same_as_rule": 0, "more_aggressive_than_rule": 0, "less_aggressive_than_rule": 0, "fallback": 0}
    hard_stop_risk = 0
    for row in records:
        rule = str(row.get("rule_action") or "hold")
        model = str(row.get("model_action") or "hold")
        if row.get("fallback_reason"):
            counts["fallback"] += 1
        if rule == "hard_stop" and model not in {"sell_all", "hard_stop"}:
            hard_stop_risk += 1
        rule_rank = ACTION_RANK.get(rule, 0)
        model_rank = ACTION_RANK.get(model, 0)
        if model_rank == rule_rank:
            counts["same_as_rule"] += 1
        elif model_rank > rule_rank:
            counts["more_aggressive_than_rule"] += 1
        else:
            counts["less_aggressive_than_rule"] += 1
    return {
        **counts,
        "fallback_rate_pct": _pct(counts["fallback"], len(records)),
        "hard_stop_override_risk_count": hard_stop_risk,
    }


def _outcome_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in records if str(row.get("outcome_status") or "") == "settled" or row.get("outcome_5d")]
    sell_rows = [row for row in settled if str(row.get("model_action") or "").startswith("sell")]
    sell_flying = [row for row in sell_rows if _outcome_float(row, "max_favorable_5d_pct") >= 5.0]
    return {
        "settled_or_labeled_count": len(settled),
        "avg_return_5d_pct": _avg(_outcome_float(row, "return_5d_pct") for row in settled),
        "avg_max_adverse_5d_pct": _avg(_outcome_float(row, "max_adverse_5d_pct") for row in settled),
        "sell_flying_count": len(sell_flying),
        "sell_flying_rate_pct": _pct(len(sell_flying), len(sell_rows)),
    }


def _promotion_blockers(*, total: int, settled: int, diff: dict[str, Any]) -> list[str]:
    blockers = []
    if total < 30:
        blockers.append("shadow_record_count_lt_30")
    if settled < 30:
        blockers.append("settled_shadow_count_lt_30")
    if diff["hard_stop_override_risk_count"]:
        blockers.append("hard_stop_override_risk_detected")
    return blockers


def _payload(row: MarketModelObservation) -> dict[str, Any]:
    try:
        payload = json.loads(row.payload_json or "{}")
    except Exception:
        payload = {}
    payload.setdefault("symbol", row.symbol)
    payload.setdefault("model_confidence", float(row.confidence or 0.0))
    payload.setdefault("outcome_status", row.outcome_status)
    return payload if isinstance(payload, dict) else {}


def _outcome_float(record: dict[str, Any], key: str) -> float:
    outcome = record.get("outcome_5d")
    if not isinstance(outcome, dict):
        outcome = record.get("outcome")
    if not isinstance(outcome, dict):
        return 0.0
    try:
        return float(outcome.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _avg(values) -> float:
    items = [float(value or 0.0) for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def _pct(part: int, total: int) -> float:
    return round(part / total * 100.0, 3) if total else 0.0
