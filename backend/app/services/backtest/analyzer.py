from __future__ import annotations

from math import isfinite, sqrt
from typing import Any

from app.services.backtest.portfolio import PortfolioSnapshot, RealizedTrade
from app.services.finance.performance_math import (
    annualized_sharpe_ratio,
    annualized_sortino_ratio,
    risk_free_rate_from_params,
    sequence_max_drawdown_pct,
)
from app.services.quant.runtime_parameters import get_backtest_execution


class BacktestAnalyzer:
    def analyze(
        self,
        *,
        initial_cash: float,
        equity_curve: list[PortfolioSnapshot],
        trades: list[RealizedTrade],
        orders: list[Any],
    ) -> dict[str, Any]:
        final_equity = equity_curve[-1].total_equity if equity_curve else initial_cash
        returns = _equity_returns(equity_curve)
        benchmark_returns = _benchmark_returns(equity_curve)
        risk_free_rate = risk_free_rate_from_params(get_backtest_execution())
        total_return_pct = (final_equity - initial_cash) / max(initial_cash, 0.01) * 100
        max_drawdown_pct = _max_drawdown_pct(equity_curve)
        benchmark_return_pct = _compound_return_pct(benchmark_returns)
        winning_trades = [trade for trade in trades if trade.net_pnl > 0]
        losing_trades = [trade for trade in trades if trade.net_pnl < 0]
        gross_gain = sum(trade.net_pnl for trade in winning_trades)
        gross_loss = abs(sum(trade.net_pnl for trade in losing_trades))
        directional_stats = _directional_trade_stats(trades)
        filled_orders = [order for order in orders if getattr(order, "status", "") == "filled"]
        rejected_orders = [order for order in orders if getattr(order, "status", "") == "rejected"]
        return {
            "initial_cash": round(initial_cash, 2),
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return_pct, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "sharpe_ratio": round(_sharpe_ratio(returns, risk_free_rate), 4),
            "sortino_ratio": round(_sortino_ratio(returns, risk_free_rate), 4),
            "risk_free_rate_annual_pct": round(risk_free_rate, 4),
            "calmar_ratio": round(_calmar_ratio(total_return_pct, max_drawdown_pct, len(returns)), 4),
            "benchmark_return_pct": round(benchmark_return_pct, 4),
            "benchmark_alpha_pct": round(total_return_pct - benchmark_return_pct, 4),
            "information_ratio": round(_information_ratio(returns, benchmark_returns), 4),
            "trade_count": len(trades),
            "filled_order_count": len(filled_orders),
            "rejected_order_count": len(rejected_orders),
            "win_rate_pct": round(len(winning_trades) / max(len(trades), 1) * 100, 4),
            "profit_factor": round(gross_gain / gross_loss, 4) if gross_loss > 0 else None,
            "long_win_rate_pct": directional_stats["long"]["win_rate_pct"],
            "long_profit_factor": directional_stats["long"]["profit_factor"],
            "long_win_loss_ratio": directional_stats["long"]["win_loss_ratio"],
            "short_win_rate_pct": directional_stats["short"]["win_rate_pct"],
            "short_profit_factor": directional_stats["short"]["profit_factor"],
            "short_win_loss_ratio": directional_stats["short"]["win_loss_ratio"],
            "directional_stats": directional_stats,
            "avg_trade_return_pct": round(
                sum(trade.return_pct for trade in trades) / max(len(trades), 1),
                4,
            ),
            "by_strategy": _by_strategy(trades),
            "reject_reasons": _reject_reasons(rejected_orders),
        }


def _equity_returns(equity_curve: list[PortfolioSnapshot]) -> list[float]:
    values = [item.total_equity for item in equity_curve]
    return [
        (values[index] - values[index - 1]) / max(values[index - 1], 0.01)
        for index in range(1, len(values))
    ]


def _benchmark_returns(equity_curve: list[PortfolioSnapshot]) -> list[float]:
    values = [
        _as_float(
            getattr(item, "benchmark_equity", None)
            if getattr(item, "benchmark_equity", None) is not None
            else getattr(item, "benchmark_nav", None)
        )
        for item in equity_curve
    ]
    numeric_values = [item for item in values if item is not None and item > 0]
    if len(numeric_values) == len(values) and len(numeric_values) >= 2:
        return [
            (numeric_values[index] - numeric_values[index - 1]) / numeric_values[index - 1]
            for index in range(1, len(numeric_values))
        ]

    percentage_returns = [
        _as_float(getattr(item, "benchmark_return_pct", None))
        for item in equity_curve[1:]
    ]
    if any(item is not None for item in percentage_returns):
        return [((item or 0.0) / 100) for item in percentage_returns]
    return []


def _max_drawdown_pct(equity_curve: list[PortfolioSnapshot]) -> float:
    return sequence_max_drawdown_pct(item.total_equity for item in equity_curve)


def _compound_return_pct(returns: list[float]) -> float:
    value = 1.0
    for item in returns:
        value *= 1 + item
    return (value - 1) * 100


def _sharpe_ratio(returns: list[float], risk_free_rate_annual_pct: float) -> float:
    return annualized_sharpe_ratio(returns, risk_free_rate_annual_pct=risk_free_rate_annual_pct)


def _sortino_ratio(returns: list[float], risk_free_rate_annual_pct: float) -> float:
    return annualized_sortino_ratio(returns, risk_free_rate_annual_pct=risk_free_rate_annual_pct)


def _calmar_ratio(total_return_pct: float, max_drawdown_pct: float, periods: int) -> float:
    if periods <= 0 or max_drawdown_pct >= 0:
        return 0.0
    total_return = total_return_pct / 100
    if total_return <= -1:
        annualized_return_pct = -100.0
    else:
        annualized_return_pct = ((1 + total_return) ** (252 / periods) - 1) * 100
    return annualized_return_pct / abs(max_drawdown_pct)


def _information_ratio(returns: list[float], benchmark_returns: list[float]) -> float:
    if len(returns) < 2 or len(benchmark_returns) < 2:
        return 0.0
    pairs = list(zip(returns, benchmark_returns))
    active_returns = [strategy - benchmark for strategy, benchmark in pairs]
    avg = sum(active_returns) / len(active_returns)
    variance = sum((item - avg) ** 2 for item in active_returns) / (len(active_returns) - 1)
    if variance <= 0:
        return 0.0
    return avg / sqrt(variance) * sqrt(252)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _directional_trade_stats(trades: list[RealizedTrade]) -> dict[str, dict[str, float | None]]:
    grouped: dict[str, list[RealizedTrade]] = {"long": [], "short": []}
    for trade in trades:
        direction = str(getattr(trade, "direction", "") or getattr(trade, "side", "") or "long").lower()
        grouped["short" if "short" in direction else "long"].append(trade)
    return {direction: _trade_stats(items) for direction, items in grouped.items()}


def _trade_stats(trades: list[RealizedTrade]) -> dict[str, float | None]:
    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    gross_gain = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    avg_win = sum(trade.return_pct for trade in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(trade.return_pct for trade in losses) / len(losses)) if losses else 0.0
    return {
        "trade_count": len(trades),
        "win_rate_pct": round(len(wins) / max(len(trades), 1) * 100, 4),
        "profit_factor": round(gross_gain / gross_loss, 4) if gross_loss > 0 else None,
        "win_loss_ratio": round(avg_win / avg_loss, 4) if avg_win > 0 and avg_loss > 0 else None,
    }


def _by_strategy(trades: list[RealizedTrade]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[RealizedTrade]] = {}
    for trade in trades:
        grouped.setdefault(trade.strategy_key or "unknown", []).append(trade)
    return {
        strategy: {
            "trade_count": len(items),
            "net_pnl": round(sum(item.net_pnl for item in items), 2),
            "win_rate_pct": round(sum(1 for item in items if item.net_pnl > 0) / max(len(items), 1) * 100, 4),
            "avg_return_pct": round(sum(item.return_pct for item in items) / max(len(items), 1), 4),
        }
        for strategy, items in grouped.items()
    }


def _reject_reasons(orders: list[Any]) -> dict[str, int]:
    output: dict[str, int] = {}
    for order in orders:
        reason = str(getattr(order, "reject_reason", "") or "unknown")
        output[reason] = output.get(reason, 0) + 1
    return output
