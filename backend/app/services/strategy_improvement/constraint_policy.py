from __future__ import annotations

from typing import Any


BASE_REQUIRED_CONSTRAINTS = {
    "data_quality_non_fresh_no_strong_buy",
    "st_stopped_delisted_no_entry",
    "limit_up_down_nearby_no_entry_or_downgrade",
    "liquidity_amount_floor",
    "sector_concentration_position_cap",
    "consecutive_stop_loss_strategy_pause",
    "last_20_trades_negative_net_win_rate_downgrade",
}

RISK_REQUIRED_CONSTRAINTS = {
    "weak_market_block_or_reduce",
    "market_breadth_poor_reduce",
    "sector_strength_floor",
    "trailing_profit_pullback_limit",
}


def constraint_policy_audit(strategies: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    coverage: dict[str, int] = {}
    for item in strategies.get("items", []):
        constraints = set(item.get("constraints_to_test") or [])
        for key in constraints:
            coverage[key] = coverage.get(key, 0) + 1
        issues.extend(_strategy_constraint_issues(item, constraints))
    return {
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues[:80],
        "required_base_constraints": sorted(BASE_REQUIRED_CONSTRAINTS),
        "required_risk_constraints": sorted(RISK_REQUIRED_CONSTRAINTS),
        "constraint_coverage": dict(sorted(coverage.items())),
        "production_effect": "audit_only_no_parameter_write",
        "notes": [
            "约束增强审计只读，不修改生产参数、订单、持仓或账本。",
            "弱策略不得获得生产晋级动作；样本不足策略不得进入调参网格。",
            "高回撤和弱策略必须包含弱市/市场宽度/板块强度/退出回吐约束。",
        ],
    }


def _strategy_constraint_issues(item: dict[str, Any], constraints: set[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    state = str(item.get("governance_state") or "")
    missing_base = sorted(BASE_REQUIRED_CONSTRAINTS - constraints)
    if missing_base:
        issues.append(_issue(item, "missing_base_constraints", missing_base))
    if state in {"weak_strategy", "high_return_high_drawdown"}:
        missing_risk = sorted(RISK_REQUIRED_CONSTRAINTS - constraints)
        if missing_risk:
            issues.append(_issue(item, "missing_risk_constraints", missing_risk))
    if state == "insufficient_sample" and item.get("parameter_grid_allowed"):
        issues.append(_issue(item, "insufficient_sample_has_parameter_grid", ["parameter_grid_allowed"]))
    if state == "weak_strategy" and item.get("recommended_action") != "pause_or_downgrade_production_weight":
        issues.append(_issue(item, "weak_strategy_not_paused", [str(item.get("recommended_action") or "")]))
    if state == "high_return_high_drawdown" and item.get("recommended_action") != "add_market_state_position_exit_constraints":
        issues.append(_issue(item, "high_drawdown_missing_constraint_action", [str(item.get("recommended_action") or "")]))
    return issues


def _issue(item: dict[str, Any], key: str, values: list[str]) -> dict[str, Any]:
    return {
        "key": key,
        "strategy_key": item.get("strategy_key", ""),
        "strategy_title": item.get("strategy_title", ""),
        "governance_state": item.get("governance_state", ""),
        "values": values,
    }
