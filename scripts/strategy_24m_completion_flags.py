"""Completion gates for the 24-month strategy optimization report."""

from __future__ import annotations

from typing import Any


TRADE_EXTREME_KEYS = (
    "consecutive_loss_count",
    "max_single_loss_pct",
    "max_single_gain_pct",
)


def missing_required_metrics(
    before_metrics: dict[str, Any],
    sector_breakdown: dict[str, Any] | None = None,
    walk_forward_validation: dict[str, Any] | None = None,
) -> list[str]:
    missing: list[str] = []
    for key in TRADE_EXTREME_KEYS:
        value = before_metrics.get(key)
        if isinstance(value, dict) and value.get("required_before_production"):
            missing.append(key)
    if not has_static_sector_breakdown(sector_breakdown):
        missing.append("sector_breakdown")
    if not _has_walk_forward_acceptance_plan(walk_forward_validation):
        missing.append("candidate_walk_forward_oos_metrics")
    return missing


def sector_breakdown_or_missing(item: dict[str, Any]) -> dict[str, Any]:
    breakdown = item.get("sector_breakdown")
    if isinstance(breakdown, dict) and breakdown.get("rows"):
        return breakdown | {
            "required_before_production": False,
            "production_caveat": (
                breakdown.get("production_caveat")
                or "当前为静态行业归因；生产放行仍需要历史行业/概念口径。"
            ),
        }
    return {
        "status": "not_available_in_existing_24m_strategy_report",
        "required_before_production": True,
        "reason": "现有24个月策略源报告未输出板块/行业分层表现。",
    }


def has_missing_trade_extremes(strategy_items: list[dict[str, Any]]) -> bool:
    for item in strategy_items:
        before = item.get("before_metrics") or {}
        for key in TRADE_EXTREME_KEYS:
            value = before.get(key)
            if isinstance(value, dict) and value.get("required_before_production"):
                return True
    return False


def blocking_data_gates(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        gate
        for gate in gates
        if gate.get("status") == "fail"
        and (gate.get("blocking") is True or gate.get("severity") == "blocking")
    ]


def has_static_sector_breakdown(sector_breakdown: dict[str, Any] | None) -> bool:
    if not isinstance(sector_breakdown, dict):
        return False
    if sector_breakdown.get("status") != "static_instrument_sector_only":
        return False
    return bool(sector_breakdown.get("rows"))


def has_missing_sector_breakdown(strategy_items: list[dict[str, Any]]) -> bool:
    return any(not has_static_sector_breakdown(item.get("sector_breakdown")) for item in strategy_items)


def has_missing_walk_forward_plan(strategy_items: list[dict[str, Any]]) -> bool:
    return any(
        not _has_walk_forward_acceptance_plan(item.get("walk_forward_validation"))
        for item in strategy_items
    )


def unfinished_items(strategy_items: list[dict[str, Any]]) -> list[str]:
    items = [
        "P1 first_board/volume_shrink 窄网格已完成；继续补 purged-gap、Shadow settled 样本和剩余重点策略信号闸门。",
        "补齐 ETF 24个月分钟级数据、bid/ask spread、溢折价、跟踪指数和流动性分层元数据。",
        "让主力模型和退出模型积累线上 Shadow settled 样本后再评估生产晋级。",
    ]
    if has_missing_walk_forward_plan(strategy_items):
        items.insert(0, "补齐候选参数 walk-forward/purged gap 验收矩阵。")
    else:
        items.insert(0, "执行候选参数网格的按月滚动 walk-forward、purged gap 和参数稳定性实算。")
    if has_missing_sector_breakdown(strategy_items):
        items.append("补充策略按板块/行业的24个月分层表现，当前聚合报告未提供该字段。")
    if has_missing_trade_extremes(strategy_items):
        items.append(
            "逐笔连续亏损和最大单笔盈亏指标代码已补齐；当前 strategy-24m 源报告尚未刷新。"
        )
    return items


def _has_walk_forward_acceptance_plan(value: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(value.get("windows")) and bool(value.get("parameter_grid"))
