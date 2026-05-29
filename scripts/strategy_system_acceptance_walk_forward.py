from __future__ import annotations

from typing import Any

from app.services.low_buy.strategy_families import STRATEGY_FAMILY_LABELS, resolve_strategy_family


_BASE_MISSING = (
    "true_strategy_family_walk_forward_not_executed",
    "purged_gap_not_executed",
    "online_shadow_settled_sample_lt_required",
)


def family_walk_forward_evidence(sources: dict[str, Any]) -> dict[str, Any]:
    focus = sources.get("focus_parameter_walk_forward") or {}
    plan = sources.get("focus_walk_forward_plan") or {}
    exit_wf = sources.get("exit_parameter_walk_forward") or {}
    guard = sources.get("market_state_guard_walk_forward") or {}
    aggregate = focus.get("aggregate_findings") or {}
    rows: dict[str, dict[str, Any]] = {}

    for key in (focus.get("scope") or {}).get("strategy_keys") or []:
        _add_strategy(rows, key, "focus_parameter_walk_forward")
    for key in (plan.get("scope") or {}).get("strategy_keys") or []:
        _add_strategy(rows, key, "focus_walk_forward_plan")

    shadow_candidates = set(aggregate.get("strategy_specific_shadow_candidates") or [])
    retest_only = set(aggregate.get("research_only_or_retest") or [])
    pass_counts = aggregate.get("strategy_pass_counts") or {}
    for row in rows.values():
        strategy_keys = row["strategy_keys"]
        row["strategy_pass_counts"] = {key: pass_counts[key] for key in strategy_keys if key in pass_counts}
        row["strategy_specific_shadow_candidate"] = any(key in shadow_candidates for key in strategy_keys)
        row["research_only_or_retest"] = [key for key in strategy_keys if key in retest_only]
        row["exit_parameter_shadow_candidate"] = exit_wf.get("shadow_candidate") is True
        row["exit_parameter_windows"] = exit_wf.get("window_count")
        row["market_state_guard_pass_rate_pct"] = guard.get("pass_rate_pct")
        row["production_ready"] = False
        row["missing_for_production"] = _missing_for_production(row)
        row["evidence_sources"] = sorted(row["evidence_sources"])

    families = sorted(rows.values(), key=lambda item: item["family_key"])
    return {
        "status": "partial_evidence_only",
        "production_ready": False,
        "covered_family_count": len(families),
        "covered_strategy_count": sum(len(item["strategy_keys"]) for item in families),
        "families": families,
    }


def walk_forward_evidence_check(sources: dict[str, Any]) -> dict[str, Any]:
    focus = sources.get("focus_parameter_walk_forward") or {}
    exit_wf = sources.get("exit_parameter_walk_forward") or {}
    guard = sources.get("market_state_guard_walk_forward") or {}
    plan = sources.get("focus_walk_forward_plan") or {}
    purged_gap = sources.get("focus_purged_gap_audit") or {}
    aggregate = focus.get("aggregate_findings") or {}
    family_evidence = family_walk_forward_evidence(sources)
    complete = (
        int((focus.get("scope") or {}).get("total_matrix_window_count") or 0) >= 21
        and aggregate.get("production_eligible") is False
        and exit_wf.get("shadow_candidate") is True
        and exit_wf.get("production_eligible") is False
        and guard.get("production_eligible") is False
        and (plan.get("scope") or {}).get("new_backtest_started") is False
        and family_evidence.get("covered_family_count", 0) >= 4
        and family_evidence.get("production_ready") is False
    )
    return {
        "key": "walk_forward_evidence_snapshot",
        "title": "局部 walk-forward 证据",
        "status": "pass" if complete else "fail",
        "complete": bool(complete),
        "summary": "已接入 P1 窄网格、退出参数和市场状态 guard 的 OOS 窗口证据；仍只允许 Shadow/研究观察。",
        "evidence": {
            "focus_parameter_scope": focus.get("scope"),
            "focus_parameter_findings": aggregate,
            "exit_parameter": _exit_evidence(exit_wf),
            "market_state_guard": _guard_evidence(guard),
            "focus_plan_scope": plan.get("scope"),
            "purged_gap_audit": _purged_gap_evidence(purged_gap),
            "family_evidence": family_evidence,
        },
    }


def _add_strategy(rows: dict[str, dict[str, Any]], strategy_key: str, source: str) -> None:
    family_key = resolve_strategy_family(strategy_key)
    row = rows.setdefault(
        family_key,
        {
            "family_key": family_key,
            "family_text": STRATEGY_FAMILY_LABELS.get(family_key, family_key),
            "strategy_keys": [],
            "evidence_sources": set(),
        },
    )
    if strategy_key not in row["strategy_keys"]:
        row["strategy_keys"].append(strategy_key)
    row["evidence_sources"].add(source)


def _missing_for_production(row: dict[str, Any]) -> list[str]:
    missing = list(_BASE_MISSING)
    if "focus_parameter_walk_forward" not in row["evidence_sources"]:
        missing.append("strategy_parameter_windows_not_executed")
    if not row["strategy_specific_shadow_candidate"]:
        missing.append("strategy_specific_shadow_candidate_not_ready")
    return missing


def _exit_evidence(exit_wf: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_count": exit_wf.get("window_count"),
        "passed_window_count": exit_wf.get("passed_window_count"),
        "pass_rate_pct": exit_wf.get("pass_rate_pct"),
        "shadow_candidate": exit_wf.get("shadow_candidate"),
        "production_eligible": exit_wf.get("production_eligible"),
        "promotion_blockers": exit_wf.get("promotion_blockers"),
    }


def _guard_evidence(guard: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_count": guard.get("window_count"),
        "passed_window_count": guard.get("passed_window_count"),
        "pass_rate_pct": guard.get("pass_rate_pct"),
        "production_eligible": guard.get("production_eligible"),
        "promotion_blockers": guard.get("promotion_blockers"),
    }


def _purged_gap_evidence(purged_gap: dict[str, Any]) -> dict[str, Any]:
    smoke = purged_gap.get("rerun_smoke") or {}
    full = purged_gap.get("rerun_full") or {}
    daily = purged_gap.get("daily_data_coverage") or {}
    return {
        "status": purged_gap.get("status"),
        "total_matrix_window_count": purged_gap.get("total_matrix_window_count"),
        "temporal_order_passed": purged_gap.get("temporal_order_passed"),
        "explicit_train_validation_split_present": purged_gap.get("explicit_train_validation_split_present"),
        "explicit_purged_gap_encoded": purged_gap.get("explicit_purged_gap_encoded"),
        "proposed_split_plan_present": purged_gap.get("proposed_split_plan_present"),
        "purged_gap_plan_ready": purged_gap.get("purged_gap_plan_ready"),
        "purged_gap_passed": purged_gap.get("purged_gap_passed"),
        "production_blockers": purged_gap.get("production_blockers"),
        "rerun_manifest_database_url": (purged_gap.get("rerun_manifest") or {}).get("database_url"),
        "daily_data_status": daily.get("status"),
        "daily_data_total_trade_dates": daily.get("total_trade_dates"),
        "daily_data_first_trade_date": daily.get("first_trade_date"),
        "daily_data_last_trade_date": daily.get("last_trade_date"),
        "daily_data_manifest_window_count": daily.get("manifest_window_count"),
        "daily_data_covered_window_count": daily.get("covered_window_count"),
        "daily_data_min_window_trade_dates": daily.get("min_window_trade_dates"),
        "daily_data_max_window_trade_dates": daily.get("max_window_trade_dates"),
        "rerun_manifest_status": (purged_gap.get("rerun_manifest") or {}).get("status"),
        "rerun_command_count": (purged_gap.get("rerun_manifest") or {}).get("command_count"),
        "rerun_smoke_status": smoke.get("status"),
        "rerun_smoke_matrix_count": smoke.get("matrix_count"),
        "rerun_smoke_output_structure_passed": smoke.get("output_structure_passed"),
        "rerun_smoke_data_sample_available": smoke.get("data_sample_available"),
        "rerun_smoke_partial_coverage_only": smoke.get("partial_coverage_only"),
        "rerun_smoke_total_evaluated_count": smoke.get("total_evaluated_count"),
        "rerun_smoke_total_filled_count": smoke.get("total_filled_count"),
        "rerun_full_status": full.get("status"),
        "rerun_full_complete": full.get("complete"),
        "rerun_full_matrix_count": full.get("matrix_count"),
        "rerun_full_failed_count": full.get("failed_count"),
        "rerun_full_total_evaluated_count": full.get("total_evaluated_count"),
        "rerun_full_total_filled_count": full.get("total_filled_count"),
        "rerun_full_partial_coverage_only": full.get("partial_coverage_only"),
    }
