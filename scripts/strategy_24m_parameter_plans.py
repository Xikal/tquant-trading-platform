"""Candidate parameter plans for the 24-month strategy review."""

from __future__ import annotations

from typing import Any


def candidate_param_plan(
    *,
    original: dict[str, Any],
    governance: dict[str, Any],
    suggestion: dict[str, Any],
) -> dict[str, Any]:
    changed = flatten_parameter_changes(suggestion, original)
    return {
        "status": "candidate_only_not_applied",
        "production_config_change_recommended": False,
        "current_values": original,
        "optimized_values_for_production": original,
        "candidate_overrides_for_shadow_or_walk_forward": changed,
        "search_range": governance.get("constraints_to_test")
        or governance.get("parameter_grid_allowed")
        or [],
        "reason": (
            "已有报告只允许研究/观察；参数必须先通过时序 walk-forward、purged gap、"
            "稳定性和 Shadow 样本门槛，不能从回测直接写入生产。"
        ),
    }


def flatten_parameter_changes(
    suggestion: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for item in suggestion.get("suggestions", []) or []:
        _merge_params(
            changes,
            item.get("parameter_combo") or {},
            reason=item.get("reason"),
            combination_name=item.get("name"),
            original=original,
        )
    for combo in suggestion.get("parameter_combinations_for_second_backtest", []) or []:
        _merge_params(
            changes,
            combo.get("params") or {},
            reason=suggestion.get("reason"),
            combination_name=combo.get("name"),
            original=original,
        )
    return changes


def _merge_params(
    changes: dict[str, Any],
    params: dict[str, Any],
    *,
    reason: Any,
    combination_name: Any,
    original: dict[str, Any],
) -> None:
    for key, value in params.items():
        locations = _runtime_locations(str(key), original)
        changes[str(key)] = {
            "candidate_value": value,
            "reason": reason,
            "combination_name": combination_name,
            "status": "shadow_or_walk_forward_only",
            "runtime_key_status": "mapped" if locations else "not_mapped_to_current_runtime_defaults",
            "runtime_locations": locations,
        }


def _runtime_locations(key: str, original: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    for scope in ("prefilter", "execution"):
        if key in (original.get(scope) or {}):
            locations.append(scope)
    return locations
