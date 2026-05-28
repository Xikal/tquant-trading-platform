from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from statistics import mean
from typing import Any

try:
    from .low_buy_market_backtest_reporting import CONFIRMED_STATES, StrategyBacktestStats, backtest_performance_metrics
except ImportError:
    from low_buy_market_backtest_reporting import CONFIRMED_STATES, StrategyBacktestStats, backtest_performance_metrics


def strategy_detail(strategy_key: str, stat: StrategyBacktestStats) -> dict[str, Any]:
    outcomes = stat.outcomes
    filled = [item for item in outcomes if item.execution_status == "filled"]
    metrics = backtest_performance_metrics(outcomes, states=None)
    confirmed_metrics = backtest_performance_metrics(outcomes, states=set(CONFIRMED_STATES))
    return {
        "strategy_key": strategy_key,
        "strategy_title": stat.strategy_title,
        "strategy_family": stat.strategy_family,
        "strategy_family_text": stat.strategy_family_text,
        "sample_count": len(outcomes),
        "filled_count": len(filled),
        "unfilled_count": len(outcomes) - len(filled),
        "unfilled_rate_pct": pct(len(outcomes) - len(filled), len(outcomes)),
        "total_return_pct": metrics["total_return_pct"],
        "annualized_return_pct": metrics["annualized_return_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "win_rate_pct": metrics["win_rate_pct"],
        "profit_loss_ratio": metrics["profit_loss_ratio"],
        "profit_factor": metrics["profit_factor"],
        "avg_trade_return_pct": avg([item.net_return_pct for item in filled]),
        "stop_loss_rate_pct": stop_loss_rate(filled),
        "avg_holding_days": metrics["avg_holding_days"],
        "median_holding_days": metrics["median_holding_days"],
        "exit_reason_distribution": reason_counts(filled),
        "unfilled_reason_distribution": reason_counts([item for item in outcomes if item.execution_status != "filled"]),
        "pending_reason_distribution": dict(stat.pending_reason_counts),
        "signal_state_counts": dict(stat.signal_state_counts),
        "state_breakdown": signal_state_breakdown(outcomes),
        "quarter_breakdown": group_breakdown(outcomes, lambda item: quarter(item.signal_date)),
        "market_state_breakdown": group_breakdown(outcomes, lambda item: item.market_state or "unknown"),
        "confirmed_only_metrics": confirmed_metrics,
        "status": strategy_status(len(outcomes), len(filled), metrics),
        "notes": strategy_notes(stat, metrics),
    }


def group_breakdown(outcomes: list[Any], key_fn, title_lookup=None) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for outcome in outcomes:
        grouped[str(key_fn(outcome) or "unknown")].append(outcome)
    rows = []
    for key, items in sorted(grouped.items()):
        filled = [item for item in items if item.execution_status == "filled"]
        metrics = backtest_performance_metrics(items, states=None)
        rows.append(
            {
                "key": key,
                "title": title_lookup(key) if title_lookup else key,
                "sample_count": len(items),
                "filled_count": len(filled),
                "unfilled_rate_pct": pct(len(items) - len(filled), len(items)),
                "total_return_pct": metrics["total_return_pct"],
                "annualized_return_pct": metrics["annualized_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "win_rate_pct": metrics["win_rate_pct"],
                "profit_factor": metrics["profit_factor"],
                "avg_trade_return_pct": avg([item.net_return_pct for item in filled]),
                "stop_loss_rate_pct": stop_loss_rate(filled),
                "avg_holding_days": metrics["avg_holding_days"],
                "exit_reason_distribution": reason_counts(filled),
                "unfilled_reason_distribution": reason_counts([item for item in items if item.execution_status != "filled"]),
            }
        )
    return rows


def signal_state_breakdown(outcomes: list[Any]) -> list[dict[str, Any]]:
    rows = group_breakdown(outcomes, lambda item: item.buy_signal_state or "unknown")
    confirmed_items = [item for item in outcomes if item.buy_signal_state in CONFIRMED_STATES]
    return group_breakdown(confirmed_items, lambda _item: "confirmed") + rows if confirmed_items else rows


def rank_strategies(strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in strategies:
        rows.append(
            {
                "rank": 0,
                "strategy_key": item["strategy_key"],
                "strategy_title": item["strategy_title"],
                "score": ranking_score(item),
                "sample_count": item["sample_count"],
                "filled_count": item["filled_count"],
                "win_rate_pct": item["win_rate_pct"],
                "profit_factor": item["profit_factor"],
                "avg_trade_return_pct": item["avg_trade_return_pct"],
                "max_drawdown_pct": item["max_drawdown_pct"],
                "status": item["status"],
            }
        )
    rows.sort(key=lambda row: (row["score"], row["filled_count"], row["profit_factor"]), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def abnormal_strategies(strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in strategies:
        reasons: list[str] = []
        if item["sample_count"] == 0:
            reasons.append("无可评估样本")
        if item["filled_count"] == 0 and item["sample_count"] > 0:
            reasons.append("有样本但无成交")
        if item["filled_count"] < 30:
            reasons.append("成交样本不足 30")
        if float(item["profit_factor"] or 0.0) < 1.0 and item["filled_count"] > 0:
            reasons.append("Profit Factor < 1")
        if float(item["max_drawdown_pct"] or 0.0) <= -50.0:
            reasons.append("最大回撤超过 50%")
        if float(item["avg_trade_return_pct"] or 0.0) < 0:
            reasons.append("平均单笔收益为负")
        if reasons:
            rows.append({k: item[k] for k in ("strategy_key", "strategy_title", "sample_count", "filled_count")} | {"reasons": reasons})
    return rows


def parameter_suggestions(strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions = []
    for item in strategies:
        combos: list[dict[str, Any]] = []
        if item["stop_loss_rate_pct"] >= 25.0:
            combos.append({"name": "收紧入场过滤", "params": {"min_execution_quality_score": "+5", "max_distribution_risk_score": "-0.3"}})
        if item["unfilled_rate_pct"] >= 20.0:
            combos.append({"name": "放宽成交区或降低追踪样本", "params": {"entry_zone_width_pct": "+0.3", "scan_limit": "保持不变先复测"}})
        if item["avg_trade_return_pct"] < 0:
            combos.append({"name": "降低持有与止盈等待", "params": {"max_holding_days": "min(current,3)", "first_take_profit_pct": "3.0-5.0 grid"}})
        if item["filled_count"] < 30:
            combos.append({"name": "扩大观察样本", "params": {"states": "near_entry,buy_now,soft_buy_now", "window": "补齐24m后复测"}})
        if combos:
            suggestions.append(
                {
                    "strategy_key": item["strategy_key"],
                    "strategy_title": item["strategy_title"],
                    "reason": "仅输出建议，不修改生产参数。",
                    "parameter_combinations_for_second_backtest": combos,
                }
            )
    return suggestions


def ranking_score(item: dict[str, Any]) -> float:
    sample_penalty = 20.0 if int(item["filled_count"]) < 30 else 0.0
    return round(
        float(item["avg_trade_return_pct"])
        + float(item["profit_factor"]) * 2.0
        + float(item["win_rate_pct"]) * 0.04
        + float(item["sharpe_ratio"]) * 0.5
        + float(item["max_drawdown_pct"]) * 0.04
        - sample_penalty,
        4,
    )


def strategy_status(sample_count: int, filled_count: int, metrics: dict[str, Any]) -> str:
    if sample_count == 0:
        return "no_sample"
    if filled_count == 0:
        return "no_fill"
    if filled_count < 30:
        return "insufficient_sample"
    if metrics["profit_factor"] < 1.0 or metrics["avg_holding_days"] <= 0:
        return "weak"
    if metrics["max_drawdown_pct"] <= -50.0:
        return "high_drawdown"
    return "observe_candidate"


def strategy_notes(stat: StrategyBacktestStats, metrics: dict[str, Any]) -> list[str]:
    notes = []
    if not stat.outcomes:
        notes.append("无可评估样本。")
    if stat.pending_count:
        notes.append(f"{stat.pending_count} 个样本因未来窗口不足或缺数据 pending。")
    if metrics["profit_factor"] < 1.0 and metrics["trade_count"] > 0:
        notes.append("收益因子低于 1，需降权或复核入场过滤。")
    return notes


def reason_counts(outcomes: list[Any]) -> dict[str, int]:
    counts = Counter(str(item.execution_exit_reason or "未标注原因") for item in outcomes)
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def stop_loss_rate(filled: list[Any]) -> float:
    return pct(sum(1 for item in filled if "止损" in str(item.execution_exit_reason)), len(filled))


def quarter(trade_date: str) -> str:
    if not trade_date:
        return "unknown"
    value = date.fromisoformat(str(trade_date))
    return f"{value.year}Q{(value.month - 1) // 3 + 1}"


def avg(values) -> float:
    values = [float(item or 0.0) for item in values]
    return round(mean(values), 4) if values else 0.0


def pct(part: int, total: int) -> float:
    return round(part / total * 100.0, 2) if total else 0.0
