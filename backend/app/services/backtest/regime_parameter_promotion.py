from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.schema_defs.backtest import ALLOWED_OPTIMIZATION_PARAMS
from app.models.schema_defs.phase4 import QuantParameterSetCreate, QuantParameterSetOut
from app.services.quant.parameter_version_service import QuantParameterVersionService

MIN_STATE_WINDOWS = 4
MIN_STATE_PASS_RATE = 0.6
MIN_STATE_SIGNAL_COUNT = 50
_SIGNAL_COUNT_FIELDS = ("signal_count", "filled_signals", "filled_count", "trade_count", "sample_count")

logger = logging.getLogger(__name__)


def promote_regime_parameter_versions(
    db: Session,
    *,
    validation_result: dict[str, Any],
    strategy_key: str,
    operator: str,
    activate: bool = True,
) -> dict[str, Any]:
    best_params_by_state = validation_result.get("best_params_by_market_state") or {}
    by_state = validation_result.get("by_market_state") or {}
    promoted: list[QuantParameterSetOut] = []
    skipped: list[dict[str, str]] = []
    service = QuantParameterVersionService(db)
    for state, params in sorted(best_params_by_state.items()):
        clean_state = str(state or "").strip()
        clean_params = _clean_params(params)
        ok, reason = _state_gate(clean_state, clean_params, by_state.get(clean_state) or {})
        if not ok:
            skipped.append({"market_state": clean_state or "unknown", "reason": reason})
            continue
        payload = QuantParameterSetCreate(
            version=_version(strategy_key, clean_state),
            name=f"{strategy_key} {clean_state} 自适应参数",
            scope="low_buy",
            market_state_scope=clean_state,
            params=_params_payload(clean_params),
            description="Walk-forward 分市场状态验证通过后生成；仅影响对应市场状态作用域。",
            activate=activate,
        )
        promoted.append(service.create(payload, created_by=operator))
    return {
        "ok": True,
        "strategy_key": strategy_key,
        "promoted_count": len(promoted),
        "skipped_count": len(skipped),
        "promoted": [item.model_dump(mode="json") for item in promoted],
        "skipped": skipped,
    }


def _clean_params(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    return {str(key): value for key, value in params.items() if str(key) in ALLOWED_OPTIMIZATION_PARAMS}


def _state_gate(state: str, params: dict[str, Any], metrics: dict[str, Any]) -> tuple[bool, str]:
    if not state or state == "未标注":
        return False, "市场状态缺失，跳过参数晋级。"
    if not params:
        return False, "没有可映射参数。"
    window_count = int(metrics.get("window_count") or 0)
    if window_count < MIN_STATE_WINDOWS:
        return False, f"样本外窗口不足：{window_count} < {MIN_STATE_WINDOWS}。"
    pass_rate = float(metrics.get("pass_rate") or 0.0)
    if pass_rate < MIN_STATE_PASS_RATE:
        return False, f"样本外通过率不足：{pass_rate:.2f} < {MIN_STATE_PASS_RATE:.2f}。"
    signal_count, count_field = _signal_count(metrics, state=state)
    if signal_count < MIN_STATE_SIGNAL_COUNT:
        field_text = f"（来源字段：{count_field}）" if count_field else "（缺少样本数字段）"
        return False, f"成交信号样本不足：{signal_count} < {MIN_STATE_SIGNAL_COUNT}{field_text}。"
    return True, ""


def _signal_count(metrics: dict[str, Any], *, state: str) -> tuple[int, str]:
    for key in _SIGNAL_COUNT_FIELDS:
        value = metrics.get(key)
        if value is not None:
            try:
                count = int(float(value))
            except (TypeError, ValueError):
                logger.warning(
                    "regime parameter promotion signal count field invalid: state=%s field=%s value=%r",
                    state,
                    key,
                    value,
                )
                continue
            logger.info(
                "regime parameter promotion signal count field selected: state=%s field=%s value=%s",
                state,
                key,
                count,
            )
            return count, key
    logger.warning(
        "regime parameter promotion missing signal count field: state=%s expected=%s available=%s",
        state,
        ",".join(_SIGNAL_COUNT_FIELDS),
        ",".join(sorted(str(key) for key in metrics.keys())),
    )
    return 0, ""


def _params_payload(params: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"low_buy": {}, "risk": {}, "backtest": {"execution": {}}}
    if "min_score" in params:
        payload["low_buy"]["min_priority_score"] = float(params["min_score"])
    if "max_position_pct" in params:
        payload["risk"]["max_single_position_pct"] = _position_fraction(params["max_position_pct"])
    if "max_holding_days" in params:
        payload["backtest"]["execution"]["max_holding_days"] = int(params["max_holding_days"])
    if "stop_loss_pct" in params:
        payload["risk"]["default_stop_loss_pct"] = float(params["stop_loss_pct"])
    if "take_profit_pct" in params:
        payload["risk"]["default_take_profit_pct"] = float(params["take_profit_pct"])
    return _drop_empty(payload)


def _position_fraction(value: Any) -> float:
    numeric = float(value)
    return numeric / 100.0 if numeric > 1 else numeric


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            nested = _drop_empty(item)
            if nested:
                result[key] = nested
        elif item not in (None, ""):
            result[key] = item
    return result


def _version(strategy_key: str, market_state: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    clean_state = "".join(ch for ch in market_state if ch.isalnum() or ch in "_-")[:18] or "state"
    clean_strategy = "".join(ch for ch in strategy_key if ch.isalnum() or ch in "_-")[:24] or "strategy"
    return f"wf-{clean_strategy}-{clean_state}-{stamp}"[:80]
