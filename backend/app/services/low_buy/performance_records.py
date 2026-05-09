from __future__ import annotations

from app.services.low_buy.execution_simulation import DailyExecutionBar, simulate_candidate_execution
from app.services.low_buy.performance_stats import daily_bar_index, filled_close_return, retracement_bucket
from app.services.low_buy.shared import Any, LowBuyCandidateOut, PERFORMANCE_FORWARD_DAYS


def build_performance_record(
    *,
    row: Any,
    candidate: LowBuyCandidateOut,
    bars: list[DailyExecutionBar],
    payload_json: str,
    target_profit_pct: float,
) -> dict[str, Any] | None:
    signal_index = daily_bar_index(bars, row.latest_trade_date)
    if signal_index is None:
        return None
    forward = bars[signal_index + 1 : signal_index + 1 + PERFORMANCE_FORWARD_DAYS]
    if len(forward) < PERFORMANCE_FORWARD_DAYS:
        return None

    execution = simulate_candidate_execution(
        candidate=candidate.model_copy(update={"confirmed_trade_date": row.latest_trade_date}),
        rows=bars,
    )
    filled = execution.status == "filled"
    return {
        "symbol": candidate.symbol,
        "sector_name": candidate.sector_name or "未分类",
        "retracement_bucket": retracement_bucket(candidate.retracement_days),
        "market_state": candidate.market_state if '"market_state"' in payload_json else "历史未标注",
        "industry_tier": candidate.industry_tier if '"industry_tier"' in payload_json else "历史未标注",
        "filled": filled,
        "not_filled": execution.status == "not_filled",
        "stop_loss": filled and "止损" in execution.exit_reason,
        "net_return": execution.net_return_pct if filled else 0.0,
        "return_1d": filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 1) if filled else 0.0,
        "return_2d": filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 2) if filled else 0.0,
        "return_3d": filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 3) if filled else 0.0,
        "return_4d": filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 4) if filled else 0.0,
        "return_5d": filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 5) if filled else 0.0,
        "max_gain_5d": execution.max_gain_pct if filled else 0.0,
        "max_drawdown_5d": execution.max_drawdown_pct if filled else 0.0,
        "legacy_target_hit": filled and execution.max_gain_pct >= target_profit_pct,
        "hit": filled and execution.net_return_pct > 0,
    }
