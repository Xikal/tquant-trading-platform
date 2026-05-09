from __future__ import annotations

import json
from datetime import datetime, timedelta
from math import floor
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.timezone import BEIJING_TZ, beijing_now
from app.models.entities import PaperAgentRun, PaperPosition, RiskEvent
from app.services.low_buy.holding_policy import strategy_holding_policy
from app.services.paper.sizing import SizedOrder
from app.services.quant.runtime_parameters import get_market_sector_etf_t0


def _sized_order_summary(order: SizedOrder) -> dict[str, Any]:
    return {
        "symbol": order.symbol,
        "name": order.name,
        "score": order.signal_snapshot.get("priority_score", 0),
        "quantity": order.quantity,
        "price": float(order.current_price),
        "strategy_key": order.strategy_key,
        "reason": order.reason,
    }


def _sized_order_summary_list(orders: list[SizedOrder]) -> list[dict[str, Any]]:
    return [_sized_order_summary(item) for item in orders]


def _planned_order_summary(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": order.get("symbol", ""),
        "name": order.get("name", ""),
        "quantity": int(order.get("quantity") or 0),
        "price": float(order.get("price") or 0.0),
        "source": order.get("source", ""),
        "strategy_key": order.get("strategy_key", ""),
        "reason": order.get("reason", ""),
        "signal_snapshot": order.get("signal_snapshot", {}),
    }


def _position_values_by_symbol(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        str(row.get("symbol") or ""): float(row.get("market_value") or 0)
        for row in rows
        if row.get("symbol")
    }


class _CycleAggregate:
    def __init__(self) -> None:
        self.accounts = 0
        self.passed = 0
        self.filtered = 0
        self.executed = 0
        self.skipped = 0

    def add(self, result: dict[str, Any]) -> None:
        self.accounts += 1
        self.passed += int(result.get("passed") or 0)
        self.filtered += int(result.get("filtered") or 0)
        self.executed += len(result.get("executed") or [])
        self.skipped += len(result.get("skipped") or [])

    def summary(self) -> str:
        return f"处理 {self.accounts} 个模拟账户，执行 {self.executed} 条，跳过 {self.skipped} 条。"


def _exit_quantity(row: PaperPosition, *, price: float, now: datetime) -> int:
    available = int(row.available_quantity or 0)
    if available < 100 or price <= 0:
        return 0
    cost = float(row.cost_basis or 0)
    if cost <= 0:
        return 0
    pnl_pct = (price - cost) / cost * 100
    hold_days = max((now - row.opened_at).days, 0) if row.opened_at else 0
    if _is_sector_etf_t0_position(row):
        params = _sector_etf_t0_params()
        if pnl_pct >= _float_param(params, "paper_auto_take_profit_pct", 1.2):
            return _round_lot(available)
        if pnl_pct <= _float_param(params, "paper_auto_stop_loss_pct", -0.8):
            return _round_lot(available)
        if hold_days >= 1 and pnl_pct < _float_param(params, "paper_auto_time_exit_min_pct", 0.4):
            return _round_lot(available)
        return 0
    if pnl_pct <= -3.0:
        return _round_lot(available)
    if _time_stop_triggered(row, pnl_pct=pnl_pct, hold_days=hold_days):
        return _round_lot(available)
    if hold_days >= 3 and pnl_pct < 0:
        return _round_lot(available)
    if pnl_pct >= 5.0:
        return _round_lot(max(100, floor(available * 0.7)))
    return 0


def _exit_reason(row: PaperPosition, *, price: float, now: datetime) -> str:
    cost = float(row.cost_basis or 0)
    pnl_pct = (price - cost) / cost * 100 if cost > 0 else 0.0
    hold_days = max((now - row.opened_at).days, 0) if row.opened_at else 0
    if _is_sector_etf_t0_position(row):
        params = _sector_etf_t0_params()
        if pnl_pct >= _float_param(params, "paper_auto_take_profit_pct", 1.2):
            return f"ETF T+0 自动止盈: 浮盈{pnl_pct:.2f}%，兑现板块价差"
        if pnl_pct <= _float_param(params, "paper_auto_stop_loss_pct", -0.8):
            return f"ETF T+0 自动止损: 浮亏{pnl_pct:.2f}%，停止试错"
        if hold_days >= 1 and pnl_pct < _float_param(params, "paper_auto_time_exit_min_pct", 0.4):
            return f"ETF T+0 时间退出: 隔日未达价差目标，先退出"
        return "ETF T+0 自动退出计划"
    if pnl_pct <= -3.0:
        return f"自动退出: 跌破模拟止损线，浮亏{pnl_pct:.2f}%"
    if _time_stop_triggered(row, pnl_pct=pnl_pct, hold_days=hold_days):
        policy = strategy_holding_policy(_primary_strategy_from_position(row))
        return f"自动退出: 已持有{hold_days}天，超过{policy.brief}验证窗口，按时间规则退出"
    if hold_days >= 3 and pnl_pct < 0:
        return f"自动退出: 持有{hold_days}天仍未转强，按时间止损"
    if pnl_pct >= 5.0:
        return f"自动止盈: 浮盈{pnl_pct:.2f}%，先兑现大部分仓位"
    return "自动退出计划"


def _round_lot(quantity: int | float) -> int:
    return int(floor(float(quantity) / 100) * 100)


def _time_stop_triggered(row: PaperPosition, *, pnl_pct: float, hold_days: int) -> bool:
    strategy = _primary_strategy_from_position(row)
    policy = strategy_holding_policy(strategy)
    if hold_days < int(policy.max_holding_days):
        return False
    return pnl_pct < 2.0


def _primary_strategy_from_position(row: PaperPosition) -> str:
    try:
        values = json.loads(row.strategy_sources or "[]")
    except Exception:
        values = []
    if isinstance(values, list) and values:
        return str(values[0] or "")
    if isinstance(values, str):
        return values
    return ""


def _is_sector_etf_t0_position(row: PaperPosition) -> bool:
    return _primary_strategy_from_position(row) == "sector_etf_t0"


def _sector_etf_t0_params() -> dict[str, Any]:
    from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS

    values = get_market_sector_etf_t0()
    return {**MARKET_SECTOR_ETF_T0_DEFAULTS, **values} if isinstance(values, dict) else dict(MARKET_SECTOR_ETF_T0_DEFAULTS)


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)


def _today_order_symbols(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("symbol") or "").strip()
        for row in rows
        if row.get("symbol") and str(row.get("status") or "") in {"pending", "filled", "partial"}
    }


def _is_database_busy(exc: OperationalError) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database is busy" in message or "lock wait timeout" in message


def _blocking_account_ids(db: Session, account_ids: list[int]) -> set[int]:
    if not account_ids:
        return set()
    rows = db.execute(
        select(RiskEvent.account_id).where(
            RiskEvent.account_id.in_(account_ids),
            RiskEvent.status == "open",
            RiskEvent.severity.in_(["high", "critical"]),
        )
    ).scalars().all()
    return {int(account_id) for account_id in rows if account_id is not None}


def _blocking_reason(db: Session, account_id: int) -> str:
    row = (
        db.execute(
            select(RiskEvent)
            .where(
                RiskEvent.account_id == account_id,
                RiskEvent.status == "open",
                RiskEvent.severity.in_(["high", "critical"]),
            )
            .order_by(RiskEvent.triggered_at.desc(), RiskEvent.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    return str(row.message or "").strip() if row is not None else ""


def _should_persist_blocked_run(db: Session, *, account_id: int, blocking_reason: str) -> bool:
    since = _beijing_now_naive() - timedelta(minutes=15)
    recent_runs = (
        db.execute(
            select(PaperAgentRun)
            .where(
                PaperAgentRun.account_id == account_id,
                PaperAgentRun.run_type == "auto_trade_cycle",
                PaperAgentRun.status == "skipped",
                PaperAgentRun.created_at >= since,
            )
            .order_by(PaperAgentRun.id.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    if not recent_runs:
        return True
    for run in recent_runs:
        try:
            payload = json.loads(run.response_json or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        skipped = payload.get("skipped")
        if not isinstance(skipped, list):
            continue
        for item in skipped:
            if isinstance(item, dict) and str(item.get("reason") or "").strip() == blocking_reason:
                return False
    return True


def _normalize_beijing_datetime(value: datetime | None = None) -> datetime:
    if value is None:
        return _beijing_now_naive()
    if value.tzinfo is not None:
        return value.astimezone(BEIJING_TZ).replace(tzinfo=None)
    return value


def _beijing_now_naive() -> datetime:
    return beijing_now().replace(tzinfo=None)
