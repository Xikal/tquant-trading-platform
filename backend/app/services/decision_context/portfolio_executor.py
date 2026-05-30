from __future__ import annotations

from typing import Any

from scripts.low_buy_market_backtest_reporting import TradeOutcome, portfolio_backtest_metrics


DEFAULT_PORTFOLIO_EXECUTION_NOTES = [
    "组合执行预览复用 24M 报告的 portfolio_backtest_metrics 口径。",
    "约束包含 max5/max10、同票持仓不重复、同策略每日上限、同板块上限、弱市仓位上限、退潮不开新仓。",
    "该预览只做纸面组合模拟，不触发实盘或自动下单。",
]


def run_portfolio_execution(
    outcomes: list[TradeOutcome],
    *,
    states: set[str] | None = None,
    max_positions: int = 5,
    sort_by_production_score: bool = False,
    max_daily_per_strategy: int | None = 2,
    max_per_sector: int | None = 2,
    weak_market_position_cap_pct: float | None = 40.0,
    block_retreat_new_positions: bool = True,
    extra_cost_bps: float = 0.0,
) -> dict[str, Any]:
    """Thin adapter over the single audited portfolio implementation."""

    return portfolio_backtest_metrics(
        outcomes,
        states=states,
        max_positions=max_positions,
        sort_by_production_score=sort_by_production_score,
        max_daily_per_strategy=max_daily_per_strategy,
        max_per_sector=max_per_sector,
        weak_market_position_cap_pct=weak_market_position_cap_pct,
        block_retreat_new_positions=block_retreat_new_positions,
        extra_cost_bps=extra_cost_bps,
    )


def run_portfolio_execution_preview(
    outcomes: list[TradeOutcome],
    *,
    states: set[str] | None = None,
    sort_by_production_score: bool = False,
    max_daily_per_strategy: int | None = 2,
    max_per_sector: int | None = 2,
    weak_market_position_cap_pct: float | None = 40.0,
    block_retreat_new_positions: bool = True,
    extra_cost_bps: float = 0.0,
) -> dict[str, Any]:
    max_5 = run_portfolio_execution(
        outcomes,
        states=states,
        max_positions=5,
        sort_by_production_score=sort_by_production_score,
        max_daily_per_strategy=max_daily_per_strategy,
        max_per_sector=max_per_sector,
        weak_market_position_cap_pct=weak_market_position_cap_pct,
        block_retreat_new_positions=block_retreat_new_positions,
        extra_cost_bps=extra_cost_bps,
    )
    max_10 = run_portfolio_execution(
        outcomes,
        states=states,
        max_positions=10,
        sort_by_production_score=sort_by_production_score,
        max_daily_per_strategy=max_daily_per_strategy,
        max_per_sector=max_per_sector,
        weak_market_position_cap_pct=weak_market_position_cap_pct,
        block_retreat_new_positions=block_retreat_new_positions,
        extra_cost_bps=extra_cost_bps,
    )
    return {
        "capital_model_label": "真实组合执行预览",
        "max_5": max_5,
        "max_10": max_10,
        "skip_reason_counts": _merge_skip_counts(max_5.get("skip_reason_counts"), max_10.get("skip_reason_counts")),
        "notes": list(DEFAULT_PORTFOLIO_EXECUTION_NOTES),
    }


def _merge_skip_counts(left: Any, right: Any) -> dict[str, int]:
    merged: dict[str, int] = {}
    for values in (left, right):
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return {key: merged[key] for key in sorted(merged, key=lambda item: (-merged[item], item))}
