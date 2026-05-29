"""Walk-forward acceptance matrix for candidate strategy parameters."""

from __future__ import annotations

from typing import Any


PURGED_GAP_DAYS = 10


def walk_forward_matrix(
    *,
    strategy_key: str,
    governance: dict[str, Any],
    walk_forward: dict[str, Any],
    recommendation: str,
) -> dict[str, Any]:
    grid = governance.get("parameter_grid_allowed") or []
    windows = walk_forward.get("windows") or []
    executable = bool(grid) and walk_forward.get("status") == "ready"
    return {
        "strategy_key": strategy_key,
        "status": "acceptance_plan_ready_not_executed" if executable else "not_executable",
        "candidate_passed": False,
        "production_eligible": False,
        "shadow_only": True,
        "recommended_action": recommendation,
        "scheme": walk_forward.get("recommended_scheme"),
        "window_count": walk_forward.get("window_count", len(windows)),
        "windows": _window_summary(windows),
        "purged_gap_days": PURGED_GAP_DAYS,
        "purged_gap_passed": False,
        "random_split_allowed": False,
        "parameter_grid": grid,
        "objective": [
            "profit_factor",
            "calmar_or_drawdown",
            "avg_trade_return_pct",
            "win_rate_pct",
            "max_drawdown_pct",
            "stop_loss_rate_pct",
            "trade_count",
            "consecutive_loss_count",
            "market_state_oos_pass_rate",
        ],
        "stability_checks": walk_forward.get("stability_checks", []),
        "overfit_checks_required": walk_forward.get("overfit_risk_required", []),
        "promotion_rule": walk_forward.get("promotion_rule"),
        "promotion_blockers": _promotion_blockers(
            executable=executable,
            recommendation=recommendation,
            walk_forward=walk_forward,
        ),
        "oos_metrics": _not_executed_metrics(),
    }


def _window_summary(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "window_id": item.get("window_id"),
            "train_start": item.get("train_start"),
            "train_end": item.get("train_end"),
            "validation_start": item.get("validation_start"),
            "validation_end": item.get("validation_end"),
            "oos_start": item.get("oos_start"),
            "oos_end": item.get("oos_end"),
            "purged_gap_days": PURGED_GAP_DAYS,
            "split_order": item.get("split_order"),
        }
        for item in windows
    ]


def _promotion_blockers(
    *,
    executable: bool,
    recommendation: str,
    walk_forward: dict[str, Any],
) -> list[str]:
    blockers = list(walk_forward.get("promotion_blockers") or [])
    if not executable:
        blockers.append("candidate_parameter_grid_or_walk_forward_not_ready")
    if recommendation in {"pause_or_downgrade", "downgrade_to_factor_or_research_only"}:
        blockers.append("strategy_governance_not_promotion_candidate")
    blockers.extend(
        [
            "candidate_grid_not_recomputed_on_24m_windows",
            "purged_gap_not_executed_for_candidate_grid",
            "shadow_settled_sample_not_accumulated",
        ]
    )
    return sorted(set(blockers))


def _not_executed_metrics() -> dict[str, Any]:
    return {
        "status": "not_executed",
        "total_return_pct": None,
        "annualized_return_pct": None,
        "win_rate_pct": None,
        "avg_trade_return_pct": None,
        "profit_loss_ratio": None,
        "profit_factor": None,
        "max_drawdown_pct": None,
        "sharpe_ratio": None,
        "trade_count": None,
        "stop_loss_rate_pct": None,
        "consecutive_loss_count": None,
        "max_single_loss_pct": None,
        "max_single_gain_pct": None,
    }
