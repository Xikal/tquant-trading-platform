from __future__ import annotations

from typing import Any

from app.models.schemas import QuoteSnapshot, SectorSnapshot
from app.services.quant.runtime_parameters import get_position_t_decision


WEIGHT_SECTOR_KEYWORDS = (
    "银行",
    "保险",
    "石油",
    "煤炭",
    "运营商",
    "电力",
    "铁路公路",
    "高速公路",
)


def asset_bucket(quote: QuoteSnapshot, sector: SectorSnapshot | None = None) -> str:
    if quote.instrument_type == "etf":
        return "etf"
    sector_name = (sector.sector_name if sector is not None else "") or ""
    if any(keyword in sector_name for keyword in WEIGHT_SECTOR_KEYWORDS):
        return "weight_stock"
    return "thematic_stock"


def decision_params() -> dict[str, Any]:
    try:
        values = get_position_t_decision()
    except Exception:
        values = {}
    return values if isinstance(values, dict) else {}


def execution_cost_params() -> dict[str, Any]:
    values = decision_params().get("execution_costs", {})
    return values if isinstance(values, dict) else {}


def direction_gate_params(name: str) -> dict[str, Any]:
    values = decision_params().get("direction_gates", {})
    if not isinstance(values, dict):
        return {}
    section = values.get(name, {})
    return section if isinstance(section, dict) else {}


def param_float(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def dict_param(params: dict[str, Any], key: str) -> dict[str, Any]:
    value = params.get(key, {})
    return value if isinstance(value, dict) else {}


def list_param(params: dict[str, Any], key: str) -> list[str]:
    value = params.get(key, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def bucket_state_params(params: dict[str, Any], asset_bucket_value: str, state: str) -> dict[str, float]:
    result = dict(dict_param(params, "default"))
    overrides = dict_param(params, "state_overrides")
    specific = overrides.get(f"{asset_bucket_value}.{state}", {})
    if isinstance(specific, dict):
        result.update(specific)
    return result


def bucket_float(mapping: dict[str, Any], asset_bucket_value: str, default: float) -> float:
    try:
        return float(mapping.get(asset_bucket_value, mapping.get("thematic_stock", default)))
    except (TypeError, ValueError):
        return default


def tier_bonus(tiers: Any, *, value: float, value_key: str, bonus_key: str) -> float:
    if not isinstance(tiers, list):
        return 0.0
    valid_tiers = [item for item in tiers if isinstance(item, dict)]
    valid_tiers.sort(key=lambda item: param_float(item, value_key, 0.0), reverse=True)
    for item in valid_tiers:
        if value >= param_float(item, value_key, 0.0):
            return param_float(item, bonus_key, 0.0)
    return 0.0


def range_bonus(tiers: Any, *, value: float, min_key: str, max_key: str, bonus_key: str) -> float:
    if not isinstance(tiers, list):
        return 0.0
    for item in tiers:
        if not isinstance(item, dict):
            continue
        lower = param_float(item, min_key, 0.0)
        upper = param_float(item, max_key, 0.0)
        if lower < value <= upper:
            return param_float(item, bonus_key, 0.0)
    return 0.0


def liquidity_bonus(params: dict[str, Any], amount: float, bonus_key: str) -> float:
    tiers = params.get("liquidity_bonus_tiers", [])
    if not isinstance(tiers, list):
        return 0.0
    valid_tiers = [item for item in tiers if isinstance(item, dict)]
    valid_tiers.sort(key=lambda item: param_float(item, "min_amount", 0.0), reverse=True)
    for item in valid_tiers:
        if amount >= param_float(item, "min_amount", 0.0):
            return param_float(item, bonus_key, 0.0)
    return 0.0


def negative_buyback_anchor(*, ma5: float, vwap_value: float) -> float:
    return min(ma5, vwap_value)
