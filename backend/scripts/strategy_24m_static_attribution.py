from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.models.entities import Instrument

try:
    from .low_buy_market_backtest_reporting import backtest_performance_metrics
    from .strategy_24m_report_metrics import avg, pct, reason_counts, stop_loss_rate
except ImportError:
    from low_buy_market_backtest_reporting import backtest_performance_metrics
    from strategy_24m_report_metrics import avg, pct, reason_counts, stop_loss_rate


def load_static_sector_map(db) -> dict[str, str]:
    rows = db.execute(
        select(Instrument.symbol, Instrument.sector_name).where(
            Instrument.instrument_type == "stock",
            Instrument.sector_name.is_not(None),
            Instrument.sector_name != "",
        )
    ).all()
    return {str(symbol): str(sector_name).strip() for symbol, sector_name in rows if sector_name}


def static_sector_breakdown(
    outcomes: list[Any],
    sector_by_symbol: dict[str, str],
    *,
    limit: int | None = 20,
) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    mapped = 0
    for outcome in outcomes:
        sector = sector_by_symbol.get(str(outcome.symbol), "")
        if sector:
            mapped += 1
        grouped[sector or "未分类"].append(outcome)
    rows = [_bucket_row(key, items) for key, items in grouped.items()]
    rows.sort(key=lambda item: (item["filled_count"], item["sample_count"]), reverse=True)
    if limit is not None:
        rows = rows[:limit]
    return {
        "status": "static_instrument_sector_only" if outcomes else "no_outcomes",
        "attribution_basis": "instruments.sector_name",
        "history_scope": "静态行业字段，只用于研究归因；生产级历史回测仍需 instrument_industry_history。",
        "sample_count": len(outcomes),
        "mapped_count": mapped,
        "mapped_rate_pct": pct(mapped, len(outcomes)),
        "required_before_production": False,
        "production_caveat": "不能用当前静态行业字段替代历史行业/概念口径做生产放行。",
        "rows": rows,
    }


def attach_static_sector_breakdowns(
    strategies: list[dict[str, Any]],
    stats_by_strategy: dict[str, Any],
    sector_by_symbol: dict[str, str],
) -> list[dict[str, Any]]:
    for item in strategies:
        key = str(item.get("strategy_key") or "")
        stat = stats_by_strategy.get(key)
        outcomes = list(getattr(stat, "outcomes", []) or [])
        item["sector_breakdown"] = static_sector_breakdown(outcomes, sector_by_symbol)
    return strategies


def _bucket_row(key: str, items: list[Any]) -> dict[str, Any]:
    filled = [item for item in items if item.execution_status == "filled"]
    metrics = backtest_performance_metrics(items, states=None)
    return {
        "key": key,
        "title": key,
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
        "consecutive_loss_count": metrics["max_consecutive_loss_count"],
        "max_single_loss_pct": metrics["max_single_loss_pct"],
        "max_single_gain_pct": metrics["max_single_gain_pct"],
        "avg_holding_days": metrics["avg_holding_days"],
        "exit_reason_distribution": reason_counts(filled),
    }
