from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdmissionResult:
    passed: bool
    symbol: str
    priority_score: float
    reason: str
    signal: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.signal.get("name") or self.symbol)


@dataclass(frozen=True)
class AdmissionReport:
    passed: list[AdmissionResult] = field(default_factory=list)
    filtered: list[AdmissionResult] = field(default_factory=list)
    summary: str = "无优先级信号"


class AdmissionFilter:
    """Filter priority-board signals before paper auto-trading.

    This module is deliberately pure: callers pass current positions, today's
    orders and market direction in. It does not touch the database or market
    data, so it remains cheap and easy to test.
    """

    def __init__(self, *, min_score: int = 75) -> None:
        self.min_score = int(min_score)

    def evaluate(
        self,
        *,
        signals: list[dict[str, Any]],
        existing_positions: list[dict[str, Any]],
        today_orders: list[dict[str, Any]],
        market_direction: str | None,
    ) -> AdmissionReport:
        if not signals:
            return AdmissionReport(summary="无优先级信号")

        positions = _positions_by_symbol(existing_positions)
        orders = _orders_by_symbol(today_orders)
        direction = _normalize_direction(market_direction)
        passed: list[AdmissionResult] = []
        filtered: list[AdmissionResult] = []

        for signal in _sort_signals(signals):
            result = self._evaluate_one(signal=signal, positions=positions, orders=orders, direction=direction)
            if result.passed:
                passed.append(result)
            else:
                filtered.append(result)

        return AdmissionReport(
            passed=passed,
            filtered=filtered,
            summary=f"通过 {len(passed)} 条，过滤 {len(filtered)} 条",
        )

    def _evaluate_one(
        self,
        *,
        signal: dict[str, Any],
        positions: dict[str, dict[str, Any]],
        orders: dict[str, list[dict[str, Any]]],
        direction: str,
    ) -> AdmissionResult:
        symbol = str(signal.get("symbol") or "").strip()
        score = _float(signal.get("priority_score"))
        reason = self._reject_reason(symbol=symbol, score=score, signal=signal, positions=positions, orders=orders, direction=direction)
        return AdmissionResult(
            passed=reason == "",
            symbol=symbol,
            priority_score=score,
            reason=reason or "通过",
            signal=signal,
        )

    def _reject_reason(
        self,
        *,
        symbol: str,
        score: float,
        signal: dict[str, Any],
        positions: dict[str, dict[str, Any]],
        orders: dict[str, list[dict[str, Any]]],
        direction: str,
    ) -> str:
        if not symbol:
            return "缺少证券代码"
        if signal.get("is_actionable") is False:
            return "信号仅供观察，未通过可执行门槛"
        if score < self.min_score:
            return f"调度分{_score_text(score)}<阈值{self.min_score}"
        if bool(signal.get("is_suspended")) or str(signal.get("risk_tier") or "") == "block":
            return "标的停牌或风险阻断"

        position = positions.get(symbol)
        if position:
            position_pct = _float(position.get("position_pct"))
            hold_days = int(_float(position.get("hold_days")))
            if position_pct >= 40:
                return f"已持有{position_pct:.1f}%，不再加仓"
            if hold_days < 1:
                return "当日已买入，T+1 锁定"

        symbol_orders = orders.get(symbol, [])
        if _has_filled_buy_order(symbol_orders):
            return "今日已买入，不重复下单"
        if _has_cancelled_order(symbol_orders):
            return "今日已撤单，不重复下单"
        if direction == "negative_t":
            return "市场退潮，暂停所有买入"
        if direction == "neutral" and score < 85:
            return f"观望日+信号偏弱({score:.0f}<85)"
        if str(signal.get("buy_signal_state") or "") not in {"buy_now", "soft_buy_now"}:
            return "信号未到买入级别"
        return ""


def _sort_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(signals, key=lambda item: _float(item.get("priority_score")), reverse=True)


def _positions_by_symbol(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("symbol") or "").strip(): row for row in rows if row.get("symbol")}


def _orders_by_symbol(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        if symbol:
            grouped.setdefault(symbol, []).append(row)
    return grouped


def _has_cancelled_order(rows: list[dict[str, Any]]) -> bool:
    return any(str(row.get("status") or "") == "cancelled" for row in rows)


def _has_filled_buy_order(rows: list[dict[str, Any]]) -> bool:
    return any(str(row.get("status") or "") == "filled" and str(row.get("side") or "buy") == "buy" for row in rows)


def _normalize_direction(value: str | None) -> str:
    if value in {"positive_t", "negative_t", "neutral"}:
        return value
    return "neutral"


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _score_text(score: float) -> str:
    return str(int(score)) if score.is_integer() else f"{score:.1f}"
