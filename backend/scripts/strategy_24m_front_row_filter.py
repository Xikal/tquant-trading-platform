from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from app.services.low_buy.front_row_filter import FrontRowFilterConfig
    from .low_buy_market_backtest_reporting import StrategyBacktestStats, backtest_performance_metrics
    from .strategy_24m_report_metrics import group_breakdown, pct, quarter
except ImportError:
    from app.services.low_buy.front_row_filter import FrontRowFilterConfig
    from low_buy_market_backtest_reporting import StrategyBacktestStats, backtest_performance_metrics
    from strategy_24m_report_metrics import group_breakdown, pct, quarter


def front_row_filter_ab_summary(
    *,
    baseline_stats: dict[str, StrategyBacktestStats],
    front_row_stats: dict[str, StrategyBacktestStats],
    config: FrontRowFilterConfig,
) -> dict[str, Any]:
    baseline_outcomes = _all_outcomes(baseline_stats)
    front_row_outcomes = _all_outcomes(front_row_stats)
    baseline_metrics = _metric_snapshot(baseline_stats, baseline_outcomes)
    front_row_metrics = _metric_snapshot(front_row_stats, front_row_outcomes)
    delta = _metric_delta(baseline_metrics, front_row_metrics)
    notes = _risk_notes(baseline_metrics, front_row_metrics, delta)
    return {
        "status": "research_only",
        "enabled_variant": "front_row_only",
        "production_parameter_change_allowed": False,
        "sorting_effect": "none",
        "metric_basis": "same_signal_day_candidates_baseline_vs_front_row_filter",
        "config": {
            "enabled": bool(config.enabled),
            "max_leader_strength_rank": config.max_leader_strength_rank,
            "min_leader_strength_score": config.min_leader_strength_score,
            "allow_secondary_hot": config.allow_secondary_hot,
            "block_retreat_states": config.block_retreat_states,
        },
        "anti_future_function_policy": {
            "signal_uses_future_data": False,
            "baseline_and_variant_share_signal_time": True,
            "post_signal_return_starts_after_signal": True,
            "random_split_allowed": False,
            "production_gate": "shadow_only_until_walk_forward_and_settled_shadow_pass",
        },
        "baseline": baseline_metrics,
        "front_row_only": front_row_metrics,
        "delta": delta,
        "by_strategy": _strategy_comparisons(baseline_stats, front_row_stats),
        "by_market_state": _breakdown_comparisons(
            baseline_outcomes,
            front_row_outcomes,
            lambda item: item.market_state or "unknown",
        ),
        "by_quarter": _breakdown_comparisons(
            baseline_outcomes,
            front_row_outcomes,
            lambda item: quarter(item.signal_date),
        ),
        "notes": notes,
        "decision": _decision(front_row_metrics, delta, notes),
    }


def _all_outcomes(stats: dict[str, StrategyBacktestStats]) -> list[Any]:
    return [outcome for stat in stats.values() for outcome in stat.outcomes]


def _metric_snapshot(stats: dict[str, StrategyBacktestStats], outcomes: list[Any]) -> dict[str, Any]:
    metrics = backtest_performance_metrics(outcomes, states=None)
    filled = [item for item in outcomes if item.execution_status == "filled"]
    front_row_rejections = Counter()
    for stat in stats.values():
        front_row_rejections.update(stat.front_row_filter_counts)
    return {
        "strategy_count": len(stats),
        "sample_count": len(outcomes),
        "filled_count": len(filled),
        "signal_days": metrics["signal_days"],
        "avg_trades_per_signal_day": metrics["avg_trades_per_signal_day"],
        "total_return_pct": metrics["total_return_pct"],
        "daily_signal_equal_weight_compound_return_pct": metrics.get("daily_signal_equal_weight_compound_return_pct", metrics["total_return_pct"]),
        "annualized_return_pct": metrics["annualized_return_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "win_rate_pct": metrics["win_rate_pct"],
        "profit_factor": metrics["profit_factor"],
        "avg_trade_return_pct": metrics["avg_net_return_pct"],
        "avg_holding_days": metrics["avg_holding_days"],
        "front_row_rejected_count": sum(front_row_rejections.values()),
        "front_row_rejection_reasons": dict(
            sorted(front_row_rejections.items(), key=lambda item: (-item[1], item[0]))
        ),
    }


def _metric_delta(baseline: dict[str, Any], front_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_count_delta": int(front_row["sample_count"]) - int(baseline["sample_count"]),
        "sample_retention_rate_pct": pct(int(front_row["sample_count"]), int(baseline["sample_count"])),
        "filled_count_delta": int(front_row["filled_count"]) - int(baseline["filled_count"]),
        "filled_retention_rate_pct": pct(int(front_row["filled_count"]), int(baseline["filled_count"])),
        "signal_days_delta": int(front_row["signal_days"]) - int(baseline["signal_days"]),
        "signal_day_retention_rate_pct": pct(int(front_row["signal_days"]), int(baseline["signal_days"])),
        "total_return_pct_delta": round(float(front_row["total_return_pct"]) - float(baseline["total_return_pct"]), 4),
        "daily_signal_equal_weight_compound_return_pct_delta": round(
            float(front_row["daily_signal_equal_weight_compound_return_pct"])
            - float(baseline["daily_signal_equal_weight_compound_return_pct"]),
            4,
        ),
        "annualized_return_pct_delta": round(float(front_row["annualized_return_pct"]) - float(baseline["annualized_return_pct"]), 4),
        "win_rate_pct_delta": round(float(front_row["win_rate_pct"]) - float(baseline["win_rate_pct"]), 4),
        "profit_factor_delta": round(float(front_row["profit_factor"]) - float(baseline["profit_factor"]), 4),
        "avg_trade_return_pct_delta": round(
            float(front_row["avg_trade_return_pct"]) - float(baseline["avg_trade_return_pct"]),
            4,
        ),
        "max_drawdown_reduction_pct": round(
            abs(float(baseline["max_drawdown_pct"])) - abs(float(front_row["max_drawdown_pct"])),
            4,
        ),
    }


def _strategy_comparisons(
    baseline_stats: dict[str, StrategyBacktestStats],
    front_row_stats: dict[str, StrategyBacktestStats],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_key in sorted(set(baseline_stats) | set(front_row_stats)):
        baseline_stat = baseline_stats.get(strategy_key)
        front_row_stat = front_row_stats.get(strategy_key)
        baseline = _metric_snapshot({strategy_key: baseline_stat}, baseline_stat.outcomes) if baseline_stat else _empty_snapshot()
        front_row = _metric_snapshot({strategy_key: front_row_stat}, front_row_stat.outcomes) if front_row_stat else _empty_snapshot()
        delta = _metric_delta(baseline, front_row)
        rows.append(
            {
                "strategy_key": strategy_key,
                "strategy_title": (baseline_stat or front_row_stat).strategy_title if (baseline_stat or front_row_stat) else strategy_key,
                "baseline": baseline,
                "front_row_only": front_row,
                "delta": delta,
            }
        )
    rows.sort(
        key=lambda item: (
            item["delta"]["avg_trade_return_pct_delta"],
            item["front_row_only"]["filled_count"],
            item["delta"]["profit_factor_delta"],
        ),
        reverse=True,
    )
    return rows


def _breakdown_comparisons(baseline_outcomes: list[Any], front_row_outcomes: list[Any], key_fn) -> list[dict[str, Any]]:
    baseline_rows = {row["key"]: row for row in group_breakdown(baseline_outcomes, key_fn)}
    front_row_rows = {row["key"]: row for row in group_breakdown(front_row_outcomes, key_fn)}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(baseline_rows) | set(front_row_rows)):
        baseline = baseline_rows.get(key, _empty_breakdown(key))
        front_row = front_row_rows.get(key, _empty_breakdown(key))
        rows.append(
            {
                "key": key,
                "baseline": baseline,
                "front_row_only": front_row,
                "delta": {
                    "sample_retention_rate_pct": pct(int(front_row["sample_count"]), int(baseline["sample_count"])),
                    "filled_retention_rate_pct": pct(int(front_row["filled_count"]), int(baseline["filled_count"])),
                    "win_rate_pct_delta": round(float(front_row["win_rate_pct"]) - float(baseline["win_rate_pct"]), 4),
                    "profit_factor_delta": round(float(front_row["profit_factor"]) - float(baseline["profit_factor"]), 4),
                    "avg_trade_return_pct_delta": round(
                        float(front_row["avg_trade_return_pct"]) - float(baseline["avg_trade_return_pct"]),
                        4,
                    ),
                },
            }
        )
    return rows


def _risk_notes(baseline: dict[str, Any], front_row: dict[str, Any], delta: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if delta["sample_retention_rate_pct"] < 30.0:
        notes.append("样本留存低于 30%，存在推荐明显减少或长时间无票风险。")
    if delta["signal_day_retention_rate_pct"] < 60.0:
        notes.append("有信号交易日留存低于 60%，需要监控连续空窗天数。")
    if int(front_row["filled_count"]) < 300:
        notes.append("前排过滤后成交样本不足 300，不能直接作为生产放行依据。")
    if delta["avg_trade_return_pct_delta"] <= 0 and delta["profit_factor_delta"] <= 0:
        notes.append("平均单笔和 PF 未同时改善，不建议作为默认生产过滤。")
    if delta["daily_signal_equal_weight_compound_return_pct_delta"] < 0:
        notes.append("每日信号等权复利收益下降，说明过滤可能牺牲了有效后排机会。")
    if not notes:
        notes.append("收益质量改善且样本留存可观察，但仍需 shadow 与 walk-forward 验证。")
    return notes


def _decision(metrics: dict[str, Any], delta: dict[str, Any], notes: list[str]) -> str:
    if delta["sample_retention_rate_pct"] < 20.0 or delta["signal_day_retention_rate_pct"] < 50.0:
        return "reject_for_sample_loss"
    if int(metrics["filled_count"]) < 300:
        return "research_only_insufficient_sample"
    if delta["avg_trade_return_pct_delta"] > 0 and delta["profit_factor_delta"] > 0:
        return "shadow_validation_candidate"
    if any("每日信号等权复利收益下降" in item for item in notes):
        return "research_only_profit_tradeoff"
    return "research_only"


def _empty_snapshot() -> dict[str, Any]:
    return {
        "strategy_count": 0,
        "sample_count": 0,
        "filled_count": 0,
        "signal_days": 0,
        "avg_trades_per_signal_day": 0.0,
        "total_return_pct": 0.0,
        "daily_signal_equal_weight_compound_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": 0.0,
        "profit_factor": 0.0,
        "avg_trade_return_pct": 0.0,
        "avg_holding_days": 0.0,
        "front_row_rejected_count": 0,
        "front_row_rejection_reasons": {},
    }


def _empty_breakdown(key: str) -> dict[str, Any]:
    return {
        "key": key,
        "title": key,
        "sample_count": 0,
        "filled_count": 0,
        "unfilled_rate_pct": 0.0,
        "total_return_pct": 0.0,
        "daily_signal_equal_weight_compound_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "win_rate_pct": 0.0,
        "profit_factor": 0.0,
        "avg_trade_return_pct": 0.0,
        "stop_loss_rate_pct": 0.0,
        "avg_holding_days": 0.0,
        "exit_reason_distribution": {},
        "unfilled_reason_distribution": {},
    }
