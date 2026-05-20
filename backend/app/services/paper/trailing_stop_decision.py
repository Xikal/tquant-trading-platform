from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.paper.exit_types import PaperExitDecision
from app.services.paper.smart_exit_context import PaperExitContext

DecisionFactory = Callable[..., PaperExitDecision]
FloatParamGetter = Callable[[dict[str, Any], str, float], float]


def trailing_stop_decision(
    *,
    available: int,
    price: float,
    pnl_pct: float,
    hold_days: int,
    strategy_key: str,
    context: PaperExitContext | None,
    params: dict[str, Any],
    fee_drag_pct: float,
    net_profit_pct: float,
    make_decision: DecisionFactory,
    float_param: FloatParamGetter,
) -> PaperExitDecision | None:
    if context is None:
        return None
    high_price = float(getattr(context, "trailing_high_price", 0.0) or 0.0)
    stop_price = float(getattr(context, "trailing_stop_price", 0.0) or 0.0)
    trigger_pct = float_param(params, "trailing_stop_trigger_pct", 3.0)
    if high_price <= 0 or stop_price <= 0 or pnl_pct < trigger_pct or price > stop_price:
        return None
    ratio = float_param(params, "trailing_stop_sell_ratio", 0.5)
    return make_decision(
        available,
        ratio=ratio,
        pnl_pct=pnl_pct,
        hold_days=hold_days,
        strategy_key=strategy_key,
        code="trailing_stop_profit_protection",
        reason=f"移动止盈：高点{high_price:.2f}回落至保护价{stop_price:.2f}附近，先锁定利润",
        action_signal="scale_out",
        action_text="移动止盈减仓",
        why=f"持仓创新高后回落，当前仍有浮盈{pnl_pct:.2f}%，先保护利润。",
        invalid_condition="若重新放量站回高点，剩余仓位继续跟随；跌破保护价继续减仓。",
        fee_drag_pct=fee_drag_pct,
        net_profit_pct=net_profit_pct,
    )
