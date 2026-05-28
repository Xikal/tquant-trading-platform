from __future__ import annotations

from typing import Any


def walk_forward_readiness(
    *,
    daily: dict[str, Any],
    strategies: dict[str, Any],
    min_trade_days: int,
    min_daily_coverage_pct: float,
) -> dict[str, Any]:
    candidates = [
        item for item in strategies.get("items", [])
        if item.get("governance_state") in {"positive_expectancy_candidate", "high_return_high_drawdown", "research_candidate"}
        and int(item.get("filled_count") or 0) >= 30
    ]
    blocked_reasons = []
    if float(daily.get("coverage_pct") or 0.0) < min_daily_coverage_pct:
        blocked_reasons.append("daily_24m_coverage_below_threshold")
    if int(daily.get("trade_day_count") or 0) < min_trade_days:
        blocked_reasons.append("trade_days_below_walk_forward_threshold")
    if not candidates:
        blocked_reasons.append("no_candidate_strategy_after_governance")
    windows = _monthly_walk_forward_windows(
        list(daily.get("trade_dates") or []),
        train_months=12,
        validation_months=3,
        oos_months=3,
    )
    return {
        "status": "ready" if not blocked_reasons else "blocked_by_data",
        "recommended_scheme": "12m_train_3m_validation_3m_oos_monthly_roll",
        "time_series_split": "required_time_ordered_only_no_random_split",
        "random_split_allowed": False,
        "train_months": 12,
        "validation_months": 3,
        "oos_months": 3,
        "rolling_step": "monthly",
        "window_count": len(windows),
        "windows": windows,
        "candidate_strategy_count": len(candidates),
        "candidate_strategies": [
            {"strategy_key": item["strategy_key"], "strategy_title": item["strategy_title"], "state": item["governance_state"]}
            for item in candidates
        ],
        "blocked_reasons": blocked_reasons,
        "controlled_parameter_grid": _bounded_parameter_grid(),
        "stability_checks": _stability_checks(),
        "overfit_risk_required": ["PBO_or_equivalent", "Deflated_Sharpe_or_equivalent", "parameter_stability_pm_10_20pct"],
        "promotion_blockers": [
            "任何 blocking 数据门禁失败时禁止参数晋级",
            "样本外 PF/Calmar/平均单笔/胜率未通过时禁止晋级",
            "最大回撤、止损率、交易频率显著恶化时禁止晋级",
            "PBO/Deflated Sharpe 或参数稳定性显示高过拟合风险时禁止晋级",
        ],
        "promotion_rule": "OOS PF/Calmar/avg trade/win rate pass and drawdown/stop-loss do not worsen; then paper observe before production",
    }


def controlled_parameter_policy() -> dict[str, Any]:
    return {
        "allowed": [
            "min_score",
            "max_holding_days",
            "stop_loss",
            "take_profit",
            "trailing_pullback",
            "single_position_pct",
            "market_state_switch",
            "sector_strength_threshold",
            "liquidity_amount_threshold",
        ],
        "forbidden": [
            "unbounded_grid_search",
            "random_time_series_split",
            "production_param_write_from_backtest",
            "model_direct_order",
            "hard_stop_cancel_or_loosen",
        ],
        "objective": [
            "Profit Factor",
            "Calmar",
            "avg_trade_return",
            "win_rate",
            "max_drawdown",
            "stop_loss_rate",
            "trade_frequency",
            "stability",
            "OOS_pass_rate",
        ],
    }


def _bounded_parameter_grid() -> list[dict[str, Any]]:
    return [
        {"name": "min_score", "values": ["current", "+3", "+5"]},
        {"name": "max_holding_days", "values": [2, 3, 5]},
        {"name": "stop_loss", "values": ["current", "-2.5pct", "ATR_1.0"]},
        {"name": "take_profit", "values": ["3.0pct", "4.0pct", "5.0pct"]},
        {"name": "trailing_pullback", "values": ["1.0pct", "1.5pct", "2.0pct"]},
        {"name": "single_position_pct", "values": ["0.5x", "current"]},
        {"name": "market_state_switch", "values": ["current", "reduce_weak", "block_retreat"]},
        {"name": "sector_strength_threshold", "values": ["current", "+10pct", "+20pct"]},
        {"name": "liquidity_amount_threshold", "values": ["current", "+20pct", "+50pct"]},
    ]


def _monthly_walk_forward_windows(
    trade_dates: list[str],
    *,
    train_months: int,
    validation_months: int,
    oos_months: int,
) -> list[dict[str, Any]]:
    dates = sorted(item for item in trade_dates if item)
    if not dates:
        return []
    months = sorted({_month_key(item) for item in dates})
    span = train_months + validation_months + oos_months
    windows = []
    for start_index in range(0, max(len(months) - span + 1, 0)):
        train_keys = months[start_index : start_index + train_months]
        validation_keys = months[start_index + train_months : start_index + train_months + validation_months]
        oos_keys = months[start_index + train_months + validation_months : start_index + span]
        if len(oos_keys) < oos_months:
            continue
        windows.append(
            {
                "window_id": len(windows) + 1,
                "train_start": _first_trade_date(dates, train_keys),
                "train_end": _last_trade_date(dates, train_keys),
                "validation_start": _first_trade_date(dates, validation_keys),
                "validation_end": _last_trade_date(dates, validation_keys),
                "oos_start": _first_trade_date(dates, oos_keys),
                "oos_end": _last_trade_date(dates, oos_keys),
                "train_trade_days": _count_trade_days(dates, train_keys),
                "validation_trade_days": _count_trade_days(dates, validation_keys),
                "oos_trade_days": _count_trade_days(dates, oos_keys),
                "split_order": "train_before_validation_before_oos",
            }
        )
    return windows


def _stability_checks() -> list[dict[str, Any]]:
    return [
        {"key": "parameter_stability_pm_10pct", "description": "最优参数附近 -10%/+10% 仍需保持 OOS 期望不显著恶化。"},
        {"key": "parameter_stability_pm_20pct", "description": "关键阈值 -20%/+20% 压力测试用于识别尖峰最优。"},
        {"key": "pbo_or_equivalent", "description": "用 IS 排名到 OOS 排名退化比例估算过拟合概率。"},
        {"key": "deflated_sharpe_or_equivalent", "description": "对多参数尝试后的 Sharpe 做保守修正或等价降噪评估。"},
        {"key": "market_state_pass_rate", "description": "按市场状态分组检查 OOS 通过率，弱市/退潮不得隐藏总样本里。"},
    ]


def _month_key(value: str) -> str:
    return value[:7]


def _first_trade_date(dates: list[str], months: list[str]) -> str:
    allowed = set(months)
    return next((item for item in dates if _month_key(item) in allowed), "")


def _last_trade_date(dates: list[str], months: list[str]) -> str:
    allowed = set(months)
    return next((item for item in reversed(dates) if _month_key(item) in allowed), "")


def _count_trade_days(dates: list[str], months: list[str]) -> int:
    allowed = set(months)
    return sum(1 for item in dates if _month_key(item) in allowed)
