from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.timezone import beijing_now
from app.services.paper.admission import AdmissionResult


@dataclass(frozen=True)
class SizedOrder:
    symbol: str
    name: str
    side: str
    order_type: str
    quantity: int
    price: Decimal
    current_price: Decimal
    strategy_key: str
    reason: str
    signal_snapshot: dict[str, Any]
    source: str = "auto"

    def to_plan_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": str(self.price),
            "current_price": str(self.current_price),
            "quote_time": beijing_now().replace(tzinfo=None),
            "is_suspended": bool(self.signal_snapshot.get("is_suspended") or False),
            "source": self.source,
            "strategy_key": self.strategy_key,
            "reason": self.reason,
            "signal_snapshot": self.signal_snapshot,
            "require_intraday_confirmation": bool(self.signal_snapshot.get("require_intraday_confirmation") or False),
        }


class PositionSizer:
    """Convert admitted priority-board candidates into paper buy plans."""

    def __init__(self, *, max_position_pct: float = 0.10, max_cash_pct: float = 0.30) -> None:
        self.max_position_pct = Decimal(str(max_position_pct))
        self.max_cash_pct = Decimal(str(max_cash_pct))

    def calculate(
        self,
        *,
        candidates: list[AdmissionResult],
        total_assets: float,
        available_cash: float,
        max_orders: int = 5,
        current_positions: dict[str, Decimal | float | int | str] | None = None,
    ) -> list[SizedOrder]:
        if total_assets <= 0 or available_cash <= 0 or max_orders <= 0:
            return []

        position_values = _decimal_positions(current_positions or {})
        remaining_cash = Decimal(str(available_cash))
        total_assets_value = Decimal(str(total_assets))
        orders: list[SizedOrder] = []
        for candidate in sorted(candidates, key=lambda item: item.priority_score, reverse=True):
            if len(orders) >= max_orders:
                break
            order = self._size_candidate(
                candidate,
                total_assets=total_assets_value,
                remaining_cash=remaining_cash,
                current_position_value=position_values.get(candidate.symbol, Decimal("0")),
            )
            if order is None:
                continue
            orders.append(order)
            remaining_cash -= Decimal(order.quantity) * order.current_price
            if remaining_cash <= 0:
                break
        return orders

    def _size_candidate(
        self,
        candidate: AdmissionResult,
        *,
        total_assets: Decimal,
        remaining_cash: Decimal,
        current_position_value: Decimal,
    ) -> SizedOrder | None:
        current_price = _current_price(candidate.signal)
        if current_price <= 0:
            return None

        price_value = current_price
        position_cap, position_cap_source, position_cap_reason = self._position_cap(candidate)
        max_position_value = (total_assets * position_cap) - max(current_position_value, Decimal("0"))
        if max_position_value <= 0:
            return None
        max_value = min(max_position_value, remaining_cash * self.max_cash_pct)
        quantity = _round_lot_decimal(max_value / price_value)
        if quantity < 100:
            return None
        if Decimal(quantity) * price_value > remaining_cash:
            quantity = _round_lot_decimal(remaining_cash / price_value)
        if quantity < 100:
            return None

        strategy_key = _strategy_key(candidate.signal)
        signal_snapshot = dict(candidate.signal)
        signal_snapshot["position_cap_pct"] = round(float(position_cap * Decimal(100)), 2)
        signal_snapshot["position_cap_source"] = position_cap_source
        signal_snapshot["position_cap_reason"] = position_cap_reason
        if getattr(candidate, "kelly_position", None) is not None:
            signal_snapshot.setdefault("kelly_position_text", "半凯利仓位已参与自动下单上限控制")
        return SizedOrder(
            symbol=candidate.symbol,
            name=candidate.name,
            side="buy",
            order_type="market",
            quantity=quantity,
            price=current_price,
            current_price=current_price,
            strategy_key=strategy_key,
            reason=_reason(candidate, strategy_key=strategy_key),
            signal_snapshot=signal_snapshot,
        )

    def _position_cap(self, candidate: AdmissionResult) -> tuple[Decimal, str, str]:
        caps: list[tuple[Decimal, str, str]] = [
            (self.max_position_pct, "default_cap", f"默认单票仓位上限 {float(self.max_position_pct * Decimal(100)):.1f}%")
        ]
        kelly = getattr(candidate, "kelly_position", None)
        if kelly is not None and float(kelly.half_kelly or 0) > 0:
            caps.append(
                (
                    Decimal(str(kelly.half_kelly)),
                    "kelly_half",
                    f"半凯利仓位上限 {float(Decimal(str(kelly.half_kelly)) * Decimal(100)):.1f}%",
                )
            )
        final_cap_pct = _decimal_pct(candidate.signal.get("final_position_cap_pct"))
        volatility_pct = _decimal_pct(candidate.signal.get("volatility_position_pct"))
        if final_cap_pct > 0:
            caps.append(
                (
                    final_cap_pct / Decimal(100),
                    "final_position_cap",
                    str(candidate.signal.get("position_cap_reason") or "综合仓位上限控制"),
                )
            )
        elif volatility_pct > 0:
            caps.append(
                (
                    volatility_pct / Decimal(100),
                    "volatility_atr",
                    str(candidate.signal.get("position_cap_reason") or "按 ATR 波动率控制仓位"),
                )
            )
        validation_scale = _validation_position_scale(candidate.signal)
        if validation_scale is not None:
            caps.append(
                (
                    self.max_position_pct * validation_scale,
                    "validation_phase",
                    str(candidate.signal.get("validation_phase_reason") or "按策略验证阶段控制仓位"),
                )
            )
        cap, source, reason = min(caps, key=lambda item: item[0])
        return max(Decimal("0"), cap), source, reason


def _current_price(signal: dict[str, Any]) -> Decimal:
    for key in ("latest_price", "current_price", "last_price", "price"):
        try:
            value = Decimal(str(signal.get(key) or "0"))
        except Exception:
            value = Decimal("0")
        if value > 0:
            return value
    return Decimal("0")


def _round_lot_decimal(raw_quantity: Decimal) -> int:
    return int(raw_quantity // Decimal(100) * 100)


def _decimal_positions(values: dict[str, Decimal | float | int | str]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for symbol, value in values.items():
        try:
            result[str(symbol)] = Decimal(str(value or "0"))
        except Exception:
            result[str(symbol)] = Decimal("0")
    return result


def _decimal_pct(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")


def _validation_position_scale(signal: dict[str, Any]) -> Decimal | None:
    if "validation_position_scale" not in signal:
        return None
    try:
        value = Decimal(str(signal.get("validation_position_scale")))
    except Exception:
        return Decimal("0")
    return max(Decimal("0"), min(value, Decimal("1")))


def _strategy_key(signal: dict[str, Any]) -> str:
    value = signal.get("strategy_key")
    if value:
        return str(value)
    strategy_keys = signal.get("strategy_keys") or []
    if isinstance(strategy_keys, list) and strategy_keys:
        return str(strategy_keys[0])
    return ""


def _reason(candidate: AdmissionResult, *, strategy_key: str) -> str:
    title = candidate.signal.get("strategy_title") or strategy_key or "优先级榜信号"
    return f"自动调入: {title}，调度分{candidate.priority_score:.0f}"
