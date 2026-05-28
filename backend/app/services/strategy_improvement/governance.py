from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.low_buy_screener import PLAYBOOKS


def strategy_inventory(existing_report: dict[str, Any], source_report: str) -> dict[str, Any]:
    inventory = existing_report.get("inventory") or {}
    return {
        "low_buy_playbook_count": len(PLAYBOOKS),
        "low_buy_playbooks": [{"strategy_key": key, "title": value.get("title", key)} for key, value in PLAYBOOKS.items()],
        "reported_groups": inventory.get("implemented_strategy_groups", []),
        "source_report": source_report,
    }


def strategy_governance(existing_report: dict[str, Any]) -> dict[str, Any]:
    rows = [_governance_row(item) for item in existing_report.get("all_strategies") or []]
    counts = Counter(row["governance_state"] for row in rows)
    return {
        "status": "available" if rows else "missing_backtest_report",
        "strategy_count": len(rows),
        "state_counts": dict(counts),
        "items": rows,
        "ranking": sorted(rows, key=lambda row: row["governance_score"], reverse=True),
        "production_weight_changes": "not_applied",
        "notes": [
            "治理状态来自只读回测报告，不自动修改生产参数或策略权重。",
            "PF<1、平均单笔为负或样本不足策略不得晋级生产权重。",
        ],
    }


def _governance_row(item: dict[str, Any]) -> dict[str, Any]:
    filled = int(item.get("filled_count") or 0)
    pf = float(item.get("profit_factor") or 0.0)
    avg = float(item.get("avg_trade_return_pct") or 0.0)
    dd = float(item.get("max_drawdown_pct") or 0.0)
    stop = float(item.get("stop_loss_rate_pct") or 0.0)
    win = float(item.get("win_rate_pct") or 0.0)
    state, action = _state_and_action(filled=filled, pf=pf, avg=avg, drawdown=dd)
    score = round(pf * 2.0 + avg + win * 0.03 + dd * 0.03 - stop * 0.02 - (20 if filled < 30 else 0), 4)
    return {
        "strategy_key": item.get("strategy_key", ""),
        "strategy_title": item.get("strategy_title", ""),
        "strategy_family": item.get("strategy_family", ""),
        "sample_count": int(item.get("sample_count") or 0),
        "filled_count": filled,
        "win_rate_pct": win,
        "profit_factor": pf,
        "avg_trade_return_pct": avg,
        "max_drawdown_pct": dd,
        "stop_loss_rate_pct": stop,
        "governance_state": state,
        "recommended_action": action,
        "governance_score": score,
        "constraints_to_test": constraints_to_test(item, state),
        "parameter_grid_allowed": parameter_grid_allowed(state),
    }


def _state_and_action(*, filled: int, pf: float, avg: float, drawdown: float) -> tuple[str, str]:
    if filled < 30:
        return "insufficient_sample", "observe_only_expand_sample"
    if pf < 1.0 or avg < 0:
        return "weak_strategy", "pause_or_downgrade_production_weight"
    if drawdown <= -50.0:
        return "high_return_high_drawdown", "add_market_state_position_exit_constraints"
    if pf >= 1.25 and avg > 0 and drawdown > -50.0:
        return "positive_expectancy_candidate", "walk_forward_then_paper_observe"
    return "research_candidate", "second_backtest_with_constraints"


def constraints_to_test(item: dict[str, Any], state: str) -> list[str]:
    constraints = [
        "data_quality_non_fresh_no_strong_buy",
        "st_stopped_delisted_no_entry",
        "limit_up_down_nearby_no_entry_or_downgrade",
        "liquidity_amount_floor",
        "sector_concentration_position_cap",
        "consecutive_stop_loss_strategy_pause",
        "last_20_trades_negative_net_win_rate_downgrade",
    ]
    if state in {"weak_strategy", "high_return_high_drawdown"}:
        constraints.extend(["weak_market_block_or_reduce", "market_breadth_poor_reduce", "sector_strength_floor", "trailing_profit_pullback_limit"])
    if float(item.get("stop_loss_rate_pct") or 0.0) >= 25.0:
        constraints.append("entry_quality_score_raise")
    return constraints


def parameter_grid_allowed(state: str) -> list[dict[str, Any]]:
    if state == "insufficient_sample":
        return []
    return [
        {"name": "min_score", "values": ["current", "+3", "+5"]},
        {"name": "max_holding_days", "values": ["2", "3", "5"]},
        {"name": "stop_loss_pct", "values": ["current", "-2.5", "ATR_1.0"]},
        {"name": "first_take_profit_pct", "values": ["3.0", "4.0", "5.0"]},
        {"name": "trailing_pullback_pct", "values": ["1.0", "1.5", "2.0"]},
        {"name": "single_position_pct", "values": ["0.5x", "current"]},
        {"name": "market_state_switch", "values": ["block_retreat", "reduce_weak", "current"]},
        {"name": "liquidity_amount_floor", "values": ["current", "+20%", "+50%"]},
    ]
