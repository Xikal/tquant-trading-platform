from __future__ import annotations

import math
from statistics import mean, median
from typing import Any

CONFIRMED_STATES = {"buy_now", "soft_buy_now"}
OBSERVE_CONFIRMED_STATE = "observe_confirmed"
NEAR_ENTRY_STATE = "near_entry"
EVALUATED_STATES = CONFIRMED_STATES | {OBSERVE_CONFIRMED_STATE, NEAR_ENTRY_STATE}
SIGNAL_GROUPS = {
    "confirmed": ("确定买入", CONFIRMED_STATES),
    "observe_confirmed": ("观察确认", {OBSERVE_CONFIRMED_STATE}),
    "near_entry": ("接近买点", {NEAR_ENTRY_STATE}),
}


def signal_group_stats(
    *,
    outcomes: list[Any],
    states: set[str],
    target_profit_pct: float,
) -> dict[str, Any]:
    scoped = [item for item in outcomes if item.buy_signal_state in states]
    evaluated = len(scoped)
    returns_by_day = {
        1: [item.return_1d for item in scoped],
        2: [item.return_2d for item in scoped],
        3: [item.return_3d for item in scoped],
        4: [item.return_4d for item in scoped],
        5: [item.return_5d for item in scoped],
    }
    spike_returns_by_day = {
        1: [item.spike_return_1d for item in scoped],
        2: [item.spike_return_2d for item in scoped],
        3: [item.spike_return_3d for item in scoped],
        4: [item.spike_return_4d for item in scoped],
        5: [item.spike_return_5d for item in scoped],
    }
    returns_5d = returns_by_day[5]
    gains_5d = [item.max_gain_5d for item in scoped]
    drawdowns_5d = [item.max_drawdown_5d for item in scoped]
    filled = [item for item in scoped if item.execution_status == "filled"]
    not_filled = [item for item in scoped if item.execution_status == "not_filled"]
    net_winners = [item for item in filled if item.net_return_pct > 0]
    net_wins = [item.net_return_pct for item in net_winners]
    net_losses = [abs(item.net_return_pct) for item in filled if item.net_return_pct < 0]
    stop_losses = [item for item in filled if "止损" in item.execution_exit_reason]
    wins_5d = [value for value in returns_5d if value > 0]
    losses_5d = [abs(value) for value in returns_5d if value < 0]
    holding_days = _holding_day_stats(returns_by_day)
    spike_holding_days = _holding_day_stats(spike_returns_by_day)
    performance = _performance_metrics(scoped)
    return {
        "label": signal_group_label(states),
        "states": sorted(states),
        "evaluated_count": evaluated,
        "filled_count": len(filled),
        "not_filled_count": len(not_filled),
        "not_filled_rate": pct(len(not_filled), evaluated),
        "net_win_rate": pct(len(net_winners), len(filled)),
        "avg_net_return_pct": avg([item.net_return_pct for item in filled]),
        "stop_loss_rate": pct(len(stop_losses), len(filled)),
        "execution_profit_factor": profit_factor(net_wins, net_losses),
        "hit_count": sum(1 for item in scoped if item.max_gain_5d >= target_profit_pct),
        "hit_rate": pct(sum(1 for item in scoped if item.max_gain_5d >= target_profit_pct), evaluated),
        "win_rate_1d": pct(sum(1 for value in returns_by_day[1] if value > 0), evaluated),
        "win_rate_2d": pct(sum(1 for value in returns_by_day[2] if value > 0), evaluated),
        "win_rate_3d": pct(sum(1 for value in returns_by_day[3] if value > 0), evaluated),
        "win_rate_4d": pct(sum(1 for value in returns_by_day[4] if value > 0), evaluated),
        "win_rate_5d": pct(len(wins_5d), evaluated),
        "avg_return_1d": avg(returns_by_day[1]),
        "avg_return_2d": avg(returns_by_day[2]),
        "avg_return_3d": avg(returns_by_day[3]),
        "avg_return_4d": avg(returns_by_day[4]),
        "avg_return_5d": avg(returns_5d),
        "holding_days": holding_days,
        "best_holding_day": best_holding_day(holding_days),
        "spike_win_rate_1d": pct(sum(1 for value in spike_returns_by_day[1] if value > 0), evaluated),
        "spike_win_rate_2d": pct(sum(1 for value in spike_returns_by_day[2] if value > 0), evaluated),
        "spike_win_rate_3d": pct(sum(1 for value in spike_returns_by_day[3] if value > 0), evaluated),
        "spike_win_rate_4d": pct(sum(1 for value in spike_returns_by_day[4] if value > 0), evaluated),
        "spike_win_rate_5d": pct(sum(1 for value in spike_returns_by_day[5] if value > 0), evaluated),
        "avg_spike_return_1d": avg(spike_returns_by_day[1]),
        "avg_spike_return_2d": avg(spike_returns_by_day[2]),
        "avg_spike_return_3d": avg(spike_returns_by_day[3]),
        "avg_spike_return_4d": avg(spike_returns_by_day[4]),
        "avg_spike_return_5d": avg(spike_returns_by_day[5]),
        "spike_holding_days": spike_holding_days,
        "best_spike_holding_day": best_holding_day(spike_holding_days),
        "median_return_5d": median_value(returns_5d),
        "avg_max_gain_5d": avg(gains_5d),
        "avg_max_drawdown_5d": avg(drawdowns_5d),
        "t1_high_3_hit_rate": pct(sum(1 for item in scoped if item.t1_hit_3_pct), evaluated),
        "t1_high_5_hit_rate": pct(sum(1 for item in scoped if item.t1_hit_5_pct), evaluated),
        "t1_fade_to_entry_rate": pct(sum(1 for item in scoped if item.t1_fade_to_entry), evaluated),
        "avg_t1_high_return_pct": avg([item.t1_high_return_pct for item in scoped]),
        "avg_t1_close_return_pct": avg([item.t1_close_return_pct for item in scoped]),
        "avg_t1_spike_fade_pct": avg([item.t1_spike_fade_pct for item in scoped]),
        "avg_t2_high_return_pct": avg([item.t2_high_return_pct for item in scoped]),
        "avg_t2_close_return_pct": avg([item.t2_close_return_pct for item in scoped]),
        "profit_factor_5d": profit_factor(wins_5d, losses_5d),
        "performance": performance,
        "trade_count": performance["trade_count"],
        "total_return_pct": performance["total_return_pct"],
        "annualized_return_pct": performance["annualized_return_pct"],
        "max_drawdown_pct": performance["max_drawdown_pct"],
        "drawdown_recovery_status": performance["drawdown_recovery_status"],
        "drawdown_recovery_trades": performance["drawdown_recovery_trades"],
        "sharpe_ratio": performance["sharpe_ratio"],
        "profit_loss_ratio": performance["profit_loss_ratio"],
        "avg_holding_days": performance["avg_holding_days"],
        "median_holding_days": performance["median_holding_days"],
    }


def signal_group_label(states: set[str]) -> str:
    for label, group_states in SIGNAL_GROUPS.values():
        if states == group_states:
            return label
    return "合计"


def conclusion_source(*groups: dict[str, Any]) -> dict[str, Any]:
    for group in groups:
        if int(group.get("evaluated_count", 0) or 0) > 0:
            return group
    return groups[0] if groups else {}


def avg(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def median_value(values: list[float]) -> float:
    return round(median(values), 4) if values else 0.0


def pct(part: int, total: int) -> float:
    return round(part / total * 100, 2) if total else 0.0


def profit_factor(wins: list[float], losses: list[float]) -> float:
    if not losses:
        return round(float(bool(wins)), 4)
    value = sum(wins) / sum(losses)
    return round(value if math.isfinite(value) else 0.0, 4)


def _performance_metrics(outcomes: list[Any]) -> dict[str, Any]:
    filled = [item for item in outcomes if item.execution_status == "filled"]
    returns = [float(item.net_return_pct or 0.0) for item in filled]
    equity_curve = _equity_curve(returns)
    drawdown = _drawdown_stats(equity_curve)
    holding_days = [_holding_days(item) for item in filled if _holding_days(item) > 0]
    wins = [value for value in returns if value > 0]
    losses = [abs(value) for value in returns if value < 0]
    total_return = round((equity_curve[-1] - 1.0) * 100, 4) if equity_curve else 0.0
    return {
        "trade_count": len(filled),
        "total_return_pct": total_return,
        "annualized_return_pct": _annualized_return(total_return, filled),
        "max_drawdown_pct": drawdown["max_drawdown_pct"],
        "drawdown_recovery_trades": drawdown["drawdown_recovery_trades"],
        "drawdown_recovery_status": drawdown["drawdown_recovery_status"],
        "sharpe_ratio": _sharpe_ratio(returns),
        "profit_loss_ratio": round((mean(wins) / mean(losses)), 4) if wins and losses else 0.0,
        "avg_holding_days": round(mean(holding_days), 2) if holding_days else 0.0,
        "median_holding_days": round(median(holding_days), 2) if holding_days else 0.0,
    }


def _equity_curve(returns_pct: list[float]) -> list[float]:
    equity = 1.0
    curve: list[float] = []
    for value in returns_pct:
        equity *= max(0.0, 1.0 + value / 100.0)
        curve.append(equity)
    return curve


def _drawdown_stats(equity_curve: list[float]) -> dict[str, Any]:
    if not equity_curve:
        return {"max_drawdown_pct": 0.0, "drawdown_recovery_trades": 0, "drawdown_recovery_status": "无成交"}
    peak = 1.0
    max_drawdown = 0.0
    trough_index = 0
    recovered = True
    recovery_trades = 0
    for index, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
        drawdown = equity / max(peak, 0.000001) - 1.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            trough_index = index
            recovered = False
            recovery_trades = 0
        elif not recovered and equity >= peak:
            recovered = True
            recovery_trades = index - trough_index
    if max_drawdown == 0.0:
        status = "未发生回撤"
    elif recovered:
        status = f"最大回撤后 {recovery_trades} 笔交易恢复"
    else:
        status = "截至回测结束尚未恢复最大回撤"
        recovery_trades = len(equity_curve) - trough_index - 1
    return {
        "max_drawdown_pct": round(max_drawdown * 100.0, 4),
        "drawdown_recovery_trades": recovery_trades,
        "drawdown_recovery_status": status,
    }


def _annualized_return(total_return_pct: float, filled: list[Any]) -> float:
    dates = sorted({str(item.signal_date) for item in filled if getattr(item, "signal_date", "")})
    if len(dates) < 2:
        return 0.0
    try:
        from datetime import date

        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[-1])
    except ValueError:
        return 0.0
    days = max((end - start).days, 1)
    total_multiple = max(0.0, 1.0 + total_return_pct / 100.0)
    if total_multiple <= 0:
        return -100.0
    return round((total_multiple ** (365.0 / days) - 1.0) * 100.0, 4)


def _sharpe_ratio(returns_pct: list[float]) -> float:
    if len(returns_pct) < 2:
        return 0.0
    avg_return = mean(returns_pct)
    variance = sum((value - avg_return) ** 2 for value in returns_pct) / (len(returns_pct) - 1)
    stddev = math.sqrt(variance)
    if stddev <= 0:
        return 0.0
    return round((avg_return / stddev) * math.sqrt(252), 4)


def _holding_days(item: Any) -> int:
    entry = str(getattr(item, "entry_trade_date", "") or "")
    exit_date = str(getattr(item, "exit_trade_date", "") or "")
    if not entry or not exit_date:
        return 0
    try:
        from datetime import date

        return max((date.fromisoformat(exit_date) - date.fromisoformat(entry)).days, 0)
    except ValueError:
        return 0


def best_holding_day(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if int(row.get("evaluated_count", 0) or 0) > 0]
    if not eligible:
        return {"day": 0, "win_rate": 0.0, "avg_return": 0.0, "reason": "无可评估样本"}
    best = max(
        eligible,
        key=lambda row: (
            float(row.get("avg_return", 0.0) or 0.0),
            float(row.get("win_rate", 0.0) or 0.0),
            -int(row.get("day", 0) or 0),
        ),
    )
    return {
        "day": best["day"],
        "win_rate": best["win_rate"],
        "avg_return": best["avg_return"],
        "profit_factor": best["profit_factor"],
        "reason": f"{best['day']}日平均收益最高",
    }


def _holding_day_stats(returns_by_day: dict[int, list[float]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in sorted(returns_by_day):
        values = returns_by_day[day]
        wins = [value for value in values if value > 0]
        losses = [abs(value) for value in values if value < 0]
        rows.append(
            {
                "day": day,
                "evaluated_count": len(values),
                "win_rate": pct(len(wins), len(values)),
                "avg_return": avg(values),
                "median_return": median_value(values),
                "profit_factor": profit_factor(wins, losses),
            }
        )
    return rows
