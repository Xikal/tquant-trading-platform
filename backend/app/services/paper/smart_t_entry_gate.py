from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.paper.smart_exit_context import PaperExitContext


@dataclass(frozen=True)
class SmartTEntryGateResult:
    allowed: bool
    reason: str
    vwap_discount_pct: float = 0.0
    required_vwap_discount_pct: float = 0.0
    volume_release_ratio: float = 0.0
    max_volume_release_ratio: float = 0.0


def evaluate_smart_t_entry_gate(
    *,
    quote_price: float,
    context: PaperExitContext,
    params: dict[str, Any],
) -> SmartTEntryGateResult:
    if not context.intraday_usable:
        return SmartTEntryGateResult(False, "分时数据不可用，跳过做T加仓。")
    if not context.volume_usable:
        return SmartTEntryGateResult(False, "分时量能样本不足，跳过做T加仓。")
    if context.vwap <= 0 or quote_price <= 0:
        return SmartTEntryGateResult(False, "分时均价线不可用，跳过做T加仓。")

    max_volume_ratio = _float_param(
        params,
        "smart_t_add_volume_release_ratio_max",
        _float_param(params, "smart_t_add_volume_ratio_max", 0.4),
    )
    if context.volume_release_ratio > max_volume_ratio:
        return SmartTEntryGateResult(
            False,
            "量能释放仍偏大，不像健康洗盘。",
            volume_release_ratio=context.volume_release_ratio,
            max_volume_release_ratio=max_volume_ratio,
        )

    if _bool_param(params, "smart_t_require_low_rising", True) and not context.low_rising:
        return SmartTEntryGateResult(False, "分时低点没有抬高，不做洗盘加仓。")

    required_discount_pct = _float_param(
        params,
        "smart_t_add_vwap_discount_pct",
        _float_param(params, "smart_t_buy_below_vwap_pct", 0.3),
    )
    actual_discount_pct = max((1 - quote_price / context.vwap) * 100, 0.0)
    max_entry_price = context.vwap * (1 - required_discount_pct / 100)
    if quote_price > max_entry_price:
        return SmartTEntryGateResult(
            False,
            "价格没有回到分时均价线下方的折价区间。",
            vwap_discount_pct=actual_discount_pct,
            required_vwap_discount_pct=required_discount_pct,
            volume_release_ratio=context.volume_release_ratio,
            max_volume_release_ratio=max_volume_ratio,
        )

    return SmartTEntryGateResult(
        True,
        "满足 VWAP 折价 + 洗盘量能释放门槛。",
        vwap_discount_pct=actual_discount_pct,
        required_vwap_discount_pct=required_discount_pct,
        volume_release_ratio=context.volume_release_ratio,
        max_volume_release_ratio=max_volume_ratio,
    )


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)


def _bool_param(params: dict[str, Any], key: str, fallback: bool) -> bool:
    value = params.get(key, fallback)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "off", "no", ""}
    return bool(value)
