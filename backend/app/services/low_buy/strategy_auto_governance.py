from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.low_buy import SystemSettingRepository
from app.services.low_buy.strategy_governance import (
    AUTO_GOVERNANCE_SETTING_KEY,
    _strategy_health,
    latest_strategy_performance_map,
)
from app.services.low_buy.strategy_parameter_defaults import LOW_BUY_AUTO_GOVERNANCE_DEFAULTS
from app.services.quant.runtime_parameters import get_low_buy_auto_governance


def _auto_governance_params() -> dict[str, Any]:
    return _deep_merge(LOW_BUY_AUTO_GOVERNANCE_DEFAULTS, get_low_buy_auto_governance())


def _float_param(params: dict[str, Any], key: str) -> float:
    return float(params.get(key, LOW_BUY_AUTO_GOVERNANCE_DEFAULTS[key]))


def _int_param(params: dict[str, Any], key: str) -> int:
    return int(params.get(key, LOW_BUY_AUTO_GOVERNANCE_DEFAULTS[key]))


def refresh_low_buy_strategy_auto_governance(db: Session) -> dict[str, Any]:
    """Persist automatic strategy downgrade/pause decisions.

    The task is intentionally conservative: only strategies with enough real
    filled samples can be auto-downgraded. Missing or sparse samples remain
    visible as research/watch data but do not trigger persistent overrides.
    """

    performances = latest_strategy_performance_map(db)
    previous_items = _load_previous_items(db)
    params = _auto_governance_params()
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items: dict[str, dict[str, Any]] = {}
    evidence_gates = params.get("evidence_gated_strategies")
    evidence_strategy_keys = set(evidence_gates.keys()) if isinstance(evidence_gates, dict) else set()
    for strategy_key in sorted(set(performances.keys()).union(evidence_strategy_keys)):
        performance = performances.get(strategy_key)
        evidence_decision = _evidence_gate_decision(strategy_key, performance, params)
        if evidence_decision is not None:
            items[strategy_key] = {
                "status": evidence_decision["status"],
                "reason": evidence_decision["reason"],
                "health_score": 0.0,
                "filled_signals": int(getattr(performance, "filled_signals", 0) or 0),
                "recovery_pass_days": 0,
                "recovery_required_days": 0,
                "updated_at": updated_at,
                "source": "evidence_gate",
            }
            continue
        if performance is None:
            continue
        health_score, _ = _strategy_health(performance)
        decision = _auto_governance_decision(
            filled_signals=performance.filled_signals,
            health_score=health_score,
            stop_loss_rate=performance.stop_loss_rate,
            avg_net_return_pct=performance.avg_net_return_pct,
            params=params,
        )
        previous = previous_items.get(strategy_key)
        recovery_passed = _recovery_gate_passed(
            filled_signals=performance.filled_signals,
            health_score=health_score,
            stop_loss_rate=performance.stop_loss_rate,
            avg_net_return_pct=performance.avg_net_return_pct,
            params=params,
        )
        recovery_pass_days = 0
        recovery_required_days = 0
        if decision is None and previous:
            previous_status = str(previous.get("status") or "watch")
            recovery_required_days = (
                _int_param(params, "recovery_paused_days")
                if previous_status == "paused"
                else _int_param(params, "recovery_watch_days")
            )
            recovery_pass_days = (int(previous.get("recovery_pass_days") or 0) + 1) if recovery_passed else 0
            if recovery_pass_days < recovery_required_days:
                remaining_days = recovery_required_days - recovery_pass_days
                decision = {
                    "status": previous_status,
                    "reason": f"策略正在恢复观察，还需连续 {remaining_days} 个交易日达到恢复门槛。",
                }
            else:
                continue
        if decision is None:
            continue
        items[strategy_key] = {
            "status": decision["status"],
            "reason": decision["reason"],
            "health_score": health_score,
            "filled_signals": performance.filled_signals,
            "recovery_pass_days": recovery_pass_days,
            "recovery_required_days": recovery_required_days,
            "updated_at": updated_at,
        }

    payload = {
        "version": 1,
        "updated_at": updated_at,
        "min_filled_signals": _int_param(params, "min_filled_signals"),
        "items": items,
    }
    SystemSettingRepository(db).upsert(
        AUTO_GOVERNANCE_SETTING_KEY,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
    db.commit()
    return payload


def _auto_governance_decision(
    *,
    filled_signals: int,
    health_score: float,
    stop_loss_rate: float,
    avg_net_return_pct: float,
    params: dict[str, Any],
) -> dict[str, str] | None:
    if filled_signals < _int_param(params, "min_filled_signals"):
        return None
    if health_score < _float_param(params, "pause_health_threshold") or (
        stop_loss_rate >= _float_param(params, "pause_stop_loss_rate_threshold") and avg_net_return_pct < 0
    ):
        return {
            "status": "paused",
            "reason": "真实成交绩效偏弱，自动暂停强信号",
        }
    if health_score < _float_param(params, "watch_health_threshold") or stop_loss_rate >= _float_param(
        params, "watch_stop_loss_rate_threshold"
    ):
        return {
            "status": "watch",
            "reason": "真实成交绩效一般，自动降级观察",
        }
    return None


def _recovery_gate_passed(
    *,
    filled_signals: int,
    health_score: float,
    stop_loss_rate: float,
    avg_net_return_pct: float,
    params: dict[str, Any],
) -> bool:
    return (
        filled_signals >= _int_param(params, "recovery_min_filled_signals")
        and health_score >= _float_param(params, "recovery_health_threshold")
        and stop_loss_rate <= _float_param(params, "recovery_max_stop_loss_rate")
        and avg_net_return_pct > 0
    )


def _load_previous_items(db: Session) -> dict[str, dict[str, Any]]:
    row = SystemSettingRepository(db).fetch(AUTO_GOVERNANCE_SETTING_KEY)
    if row is None or not row.value:
        return {}
    try:
        payload = json.loads(row.value)
    except Exception:
        return {}
    items = payload.get("items") if isinstance(payload, dict) else None
    return items if isinstance(items, dict) else {}


def _evidence_gate_decision(
    strategy_key: str,
    performance,
    params: dict[str, Any],
) -> dict[str, str] | None:
    gates = params.get("evidence_gated_strategies")
    if not isinstance(gates, dict):
        return None
    raw_gate = gates.get(strategy_key)
    if not isinstance(raw_gate, dict):
        return None
    min_filled = int(raw_gate.get("min_filled_signals") or 0)
    filled = int(getattr(performance, "filled_signals", 0) or 0)
    if filled >= min_filled:
        return None
    status = str(raw_gate.get("status") or "watch")
    if status not in {"watch", "paused"}:
        status = "watch"
    reason = str(raw_gate.get("reason") or "").strip()
    if not reason:
        reason = f"真实成交样本 {filled}/{min_filled}，暂不放大为强买。"
    return {"status": status, "reason": reason}


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, default_value in defaults.items():
        override_value = overrides.get(key) if isinstance(overrides, dict) else None
        if isinstance(default_value, dict) and isinstance(override_value, dict):
            result[key] = _deep_merge(default_value, override_value)
        elif isinstance(overrides, dict) and key in overrides:
            result[key] = override_value
        else:
            result[key] = default_value
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key not in result:
                result[key] = value
    return result
