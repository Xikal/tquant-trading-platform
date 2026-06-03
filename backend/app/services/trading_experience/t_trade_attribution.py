from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.trading_experience import repository
from app.services.trading_experience.key_level_context import key_level_missing_evidence, load_stock_key_level_context
from app.services.trading_experience.schemas import TTradeAttributionItem


def build_attribution(
    db: Session,
    *,
    account_id: int | None = None,
    user_id: int | None = None,
    days: int = 30,
) -> tuple[int | None, list[TTradeAttributionItem]]:
    account = repository.active_paper_account(db, account_id, user_id=user_id)
    if not account:
        return account_id, []
    trades = repository.paper_trades(db, account.id, days=days)
    by_symbol: dict[str, list[object]] = defaultdict(list)
    for trade in trades:
        by_symbol[trade.symbol].append(trade)
    as_of = datetime.now()
    items: list[TTradeAttributionItem] = []
    for symbol, symbol_trades in by_symbol.items():
        completeness_issues = _completeness_issues(symbol_trades)
        sells = [trade for trade in symbol_trades if _side(trade) == "sell"]
        buys = [trade for trade in symbol_trades if _side(trade) == "buy"]
        coverage = repository.minute_coverage(db, symbol, days=days)
        key_level = load_stock_key_level_context(db, symbol)
        if completeness_issues:
            data_quality = "insufficient"
        elif coverage < 0.6:
            data_quality = "no_data"
        else:
            data_quality = "ok"
        t_count = min(len(sells), len(buys))
        realized_delta = _realized_cost_delta(symbol_trades)
        comparison = _paired_cashflow_delta(symbol_trades)
        items.append(
            TTradeAttributionItem(
                account_id=account.id,
                symbol=symbol,
                period=f"{days}d",
                t_trade_count=t_count,
                realized_cost_delta=round(realized_delta, 4),
                win_rate=round(_win_rate(sells), 4),
                sell_fly_count=sum(1 for trade in sells if str(getattr(trade, "exit_reason", "")).lower() == "sell_fly"),
                vs_no_t_trade_return_delta=round(comparison, 4) if data_quality == "ok" and comparison is not None else None,
                minute_data_coverage=round(coverage, 4),
                completeness_issues=completeness_issues,
                comparison_method="paired_cashflow_vs_hold",
                key_level_state=_key_level_state(key_level),
                discipline_notes=_discipline_notes(symbol, key_level, completeness_issues, coverage),
                data_quality=data_quality,  # type: ignore[arg-type]
                as_of=as_of,
            )
        )
    return account.id, items


def _realized_cost_delta(trades: list[object]) -> float:
    buy_cost = sum(float(getattr(trade, "net_amount", 0.0) or 0.0) for trade in trades if _side(trade) == "buy")
    sell_cash = sum(float(getattr(trade, "net_amount", 0.0) or 0.0) for trade in trades if _side(trade) == "sell")
    if buy_cost <= 0:
        return 0.0
    return (sell_cash - buy_cost) / buy_cost * 100.0


def _win_rate(sells: list[object]) -> float:
    if not sells:
        return 0.0
    wins = sum(1 for trade in sells if float(getattr(trade, "net_amount", 0.0) or 0.0) > 0)
    return wins / len(sells)


def _completeness_issues(trades: list[object]) -> list[str]:
    issues: list[str] = []
    for trade in trades:
        trade_id = getattr(trade, "id", "?")
        if _side(trade) not in {"buy", "sell"}:
            issues.append(f"trade:{trade_id}:side_missing")
        if float(getattr(trade, "price", 0.0) or 0.0) <= 0:
            issues.append(f"trade:{trade_id}:price_missing")
        if int(getattr(trade, "quantity", 0) or 0) <= 0:
            issues.append(f"trade:{trade_id}:quantity_missing")
        if getattr(trade, "trade_time", None) is None:
            issues.append(f"trade:{trade_id}:time_missing")
    return issues


def _paired_cashflow_delta(trades: list[object]) -> float | None:
    ordered = sorted(trades, key=lambda trade: getattr(trade, "trade_time", datetime.min) or datetime.min)
    buys = [trade for trade in ordered if _side(trade) == "buy"]
    sells = [trade for trade in ordered if _side(trade) == "sell"]
    if not buys or not sells:
        return None
    paired_quantity = min(
        sum(int(getattr(trade, "quantity", 0) or 0) for trade in buys),
        sum(int(getattr(trade, "quantity", 0) or 0) for trade in sells),
    )
    if paired_quantity <= 0:
        return None
    buy_avg = _weighted_average_price(buys)
    sell_avg = _weighted_average_price(sells)
    if buy_avg <= 0 or sell_avg <= 0:
        return None
    baseline_cashflow = paired_quantity * buy_avg
    actual_cashflow = paired_quantity * (sell_avg - buy_avg)
    return actual_cashflow / baseline_cashflow * 100.0 if baseline_cashflow > 0 else None


def _weighted_average_price(trades: list[object]) -> float:
    quantity = sum(int(getattr(trade, "quantity", 0) or 0) for trade in trades)
    if quantity <= 0:
        return 0.0
    return sum(float(getattr(trade, "price", 0.0) or 0.0) * int(getattr(trade, "quantity", 0) or 0) for trade in trades) / quantity


def _key_level_state(key_level) -> str:  # noqa: ANN001
    if key_level is None:
        return "insufficient"
    if key_level.support_broken:
        return "support_broken"
    if key_level.near_support:
        return "near_support"
    if key_level.near_resistance:
        return "near_resistance"
    return "neutral"


def _discipline_notes(symbol: str, key_level, completeness_issues: list[str], coverage: float) -> list[str]:  # noqa: ANN001
    notes: list[str] = []
    if completeness_issues:
        notes.append("成交字段不完整，归因降级为 insufficient")
    if coverage < 0.6:
        notes.append("分钟数据覆盖不足，归因降级为 no_data")
    if key_level is None:
        notes.extend(key_level_missing_evidence(symbol))
    elif key_level.support_broken:
        notes.extend([*key_level.evidence, "AKeyLevel 显示支撑破位，仅用于纪律归因"])
    else:
        notes.extend(key_level.evidence[:3])
    return notes


def _side(trade: object) -> str:
    return str(getattr(trade, "side", "") or "").lower()
